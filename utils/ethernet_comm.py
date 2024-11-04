import time
import os,sys
import struct
import socket
import threading
import queue
import select
import logging
import logging.config
from datetime import datetime
from utils import LuSEE_PROCESSING

class LuSEE_ETHERNET:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.debug("Class created")

            self.UDP_IP = "192.168.121.1"
            self.PC_IP = "192.168.121.50"
            self.read_timeout = 1

            self.PORT_WREG = 32000
            self.PORT_RREG = 32001
            self.PORT_RREGRESP = 32002
            self.PORT_HSDATA = 32003
            self.PORT_HK = 32004
            self.BUFFER_SIZE = 9014

            self.KEY1 = 0xDEAD
            self.KEY2 = 0xBEEF
            self.FOOTER = 0xFFFF

            self.wait_time = 0.01
            self.cdi_wait_time = 0.1

            self.start_tlm_data = 0x210
            self.tlm_reg = 0x218

            self.latch_register = 0x1
            self.write_register = 0x2
            self.action_register = 0x4
            self.readback_register = 0xB

            self.cdi_reset = 0x0
            self.spectrometer_reset = 0x0

            self.address_read = 0xA30000
            self.address_write = 0xA20000
            self.first_data_pack = 0xA00000
            self.second_data_pack = 0xA10000

            self.max_packet = 0x7FB
            self.exception_registers = [0x0, 0x200, 0x240, 0x241, 0x300, 0x303, 0x400, 0x500, 0x600, 0x700, 0x703, 0x800]

            self.stop_event = threading.Event()
            self.processing = LuSEE_PROCESSING()

            self.dummy_socket, self.dummy_socket_wakeup = socket.socketpair()
            listening_thread_settings = [("Register Response Thread", self.PORT_RREGRESP, self.processing.reg_input_queue),
                                        ("Data Thread", self.PORT_HSDATA, self.processing.data_input_queue),
                                        ("Housekeeping Thread", self.PORT_HK, self.processing.hk_input_queue)]
            self.listen_threads = []
            for listen_settings in listening_thread_settings:
                thread = threading.Thread(target=self.listener,
                            name=listen_settings[0],
                            daemon = True,
                            args=(listen_settings[1], listen_settings[2])
                            )
                thread.start()
                self.listen_threads.append(thread)

            #Set up socket for IPv4 and UDP
            self.sock_write = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.stop_signal = object()
            self.send_queue = queue.Queue()
            self.send_thread = threading.Thread(target=self.sender,
                                name="Sender Thread",
                                daemon = True)
            self.send_thread.start()

    def stop(self):
        self.logger.debug("Stopping all threads")
        self.stop_event.set()
        self.send_queue.put(self.stop_signal)
        self.logger.debug(f"Waiting for {self.send_thread.name} to join")
        self.send_thread.join()
        self.logger.debug(f"Class sees that {self.send_thread.name} is done")
        try:
            self.dummy_socket_wakeup.send(b'\x00')
        except OSError:
            pass
        for i in self.listen_threads:
            self.logger.debug(f"Waiting for {i.name} to join")
            i.join()
            self.logger.debug(f"Class sees that {i.name} is done")
        self.processing.stop()
        self.logger.info("Closed gracefully")

    def listener(self, port, q):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started, will listen at {self.PC_IP}:{port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.PC_IP, port))
        try:
            while not self.stop_event.is_set():
                #This checks the sockets at an OS level and blocks unless there's data in any of the two sockets
                #This is needed to gracefully exit when recvfrom blocks and wont get any signal in the thread
                ready, _, _ = select.select([sock, self.dummy_socket], [], [], None)
                if self.dummy_socket in ready:
                    self.logger.debug(f"{name} has been told to stop. Exiting...")
                    break
                if sock in ready:
                    try:
                        data, addr = sock.recvfrom(self.BUFFER_SIZE)
                        self.logger.debug(f"Received data in {name} from {addr}")
                        q.put(data)
                    except OSError as e:
                        self.logger.debug(f"OSError in {name}: {e}")
                        break
        except Exception as e:
            self.logger.debug(f"Exception in {name}: {e}")
        finally:
            self.logger.debug(f"{name} finally")
            if sock:
                sock.close()
            if self.dummy_socket:
                self.logger.debug(f"{name} sees dummy socket")
                self.dummy_socket.close()
            if self.dummy_socket_wakeup:
                self.dummy_socket_wakeup.close()
            self.logger.debug(f"{name} exited")

    #There needs to be only one sending thread, because with the LuSEE DCB emulator,
    #Reading back register values requires writing to be done in a specific ccsds_sequence_cnt
    #And I don't want it interrupted by concurrent writes with the other thread
    def sender(self):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started")

        while not self.stop_event.is_set():
            task = self.send_queue.get()
            self.send_queue.task_done()
            if task is self.stop_signal:
                self.logger.debug(f"{name} has been told to stop. Exiting...")
                break

            if (task["command"] == "write"):
                reg = int(task["reg"])
                val = int(task["val"])
                self.logger.debug(f"Thread is writing {hex(val)} to Register {hex(reg)}")

                #Splits the register up, since both halves need to go through socket.htons seperately
                dataValMSB = ((val >> 16) & 0xFFFF)
                dataValLSB = val & 0xFFFF

                dataMSB = self.first_data_pack + dataValMSB
                self.write_cdi_reg(self.write_register, dataMSB, self.PORT_WREG)
                time.sleep(self.wait_time)
                self.toggle_cdi_latch()

                dataLSB = self.second_data_pack + dataValLSB
                self.write_cdi_reg(self.write_register, dataLSB, self.PORT_WREG)
                time.sleep(self.wait_time)
                self.toggle_cdi_latch()

                address_value = self.address_write + reg
                self.write_cdi_reg(self.write_register, address_value, self.PORT_WREG)
                time.sleep(self.wait_time)
                self.toggle_cdi_latch()
            elif (task["command"] == "read"):
                reg = int(task["reg"])
                self.logger.debug(f"Thread is reading Register {hex(reg)}")

                address_value = self.address_read + reg
                #Tells the DCB emulator which register to read
                self.write_cdi_reg(self.write_register, address_value, self.PORT_WREG)
                time.sleep(self.wait_time)
                self.toggle_cdi_latch()
                #Tells the DCB emulator the command to read
                self.write_cdi_reg(self.readback_register, 0, self.PORT_RREG)
            elif (task["command"] == "write_bootloader"):
                self.logger.info(f"Writing {hex(task['message'])} to the bootloader")
                self.write_cdi_reg(self.write_register, task["message"])
                time.sleep(self.wait_time)
                self.toggle_cdi_latch()
            else:
                self.logger.warning(f"Unknown command in send queue: {task}")

        self.sock_write.close()
        self.logger.debug(f"{name} exited")

    def toggle_cdi_latch(self):
        self.write_cdi_reg(self.latch_register, 1, self.PORT_WREG)
        time.sleep(self.wait_time)
        self.write_cdi_reg(self.latch_register, 0, self.PORT_WREG)
        attempt = 0
        while True:
            resp = self.read_cdi_reg(self.latch_register)
            if resp is self.processing.stop_signal:
                self.logger.debug(f"toggle_cdi_latch has been told to stop. Exiting...")
                break
            if (resp["data"] >> 31):
                self.logger.debug(f"toggle_cdi_latch was successful outer loop")
                break
            else:
                attempt += 1
            if (attempt > 10):
                self.logger.warning(f"toggle_cdi_latch was unable to see the latch register complete. Returned {resp}")
                break

    def read_cdi_reg(self, reg):
        self.logger.debug(f"Reading CD Register {hex(reg)}")
        self.write_cdi_reg(int(reg), 0, self.PORT_RREG)
        while not self.stop_event.is_set():
            resp = self.processing.dcb_emulator_queue.get(True, self.read_timeout)
            self.processing.dcb_emulator_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"toggle_cdi_latch has been told to stop. Exiting...")
                break
            else:
                return resp

    def write_cdi_reg(self, reg, data, port):
        self.logger.debug(f"Writing {hex(data)} to CDI Register {hex(reg)}")
        #Splits the register up, since both halves need to go through socket.htons seperately
        dataValMSB = ((data >> 16) & 0xFFFF)
        dataValLSB = data & 0xFFFF
        WRITE_MESSAGE = struct.pack('HHHHHHHHH',socket.htons(self.KEY1), socket.htons(self.KEY2),
                                    socket.htons(reg),socket.htons(dataValMSB),
                                    socket.htons(dataValLSB),socket.htons(self.FOOTER), 0x0, 0x0, 0x0)

        self.sock_write.sendto(WRITE_MESSAGE,(self.UDP_IP, port))

    def write_reg(self, reg, val):
        write_dict = {"command": "write",
                      "reg": int(reg),
                      "val": int(val)}
        self.send_queue.put(write_dict)
        self.logger.debug(f"Writing {hex(val)} to Register {hex(reg)}")
        time.sleep(self.cdi_wait_time)

    def read_reg(self, reg):
        read_dict = {"command": "read",
                      "reg": int(reg)}
        self.send_queue.put(read_dict)
        self.logger.debug(f"Reading Register {hex(reg)}")
        while not self.stop_event.is_set():
            resp = self.processing.reg_output_queue.get(True, self.read_timeout)
            self.processing.reg_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"read_reg has been told to stop. Exiting...")
                break
            self.logger.debug(f"Read back {hex(resp['data'])}")
            if (not self.processing.reg_output_queue.empty()):
                self.logger.warning(f"Register queue still has {self.processing.reg_output_queue.qsize()} items")
            return resp["data"]

    def send_bootloader_message(self, message):
        self.write_cdi_reg(self.write_register, message, self.PORT_WREG)
        self.toggle_cdi_latch()

    def read_hk_message(self):
        while not self.stop_event.is_set():
            resp = self.processing.hk_output_queue.get()
            self.processing.hk_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"read_reg has been told to stop. Exiting...")
                break
            self.logger.debug(f"Read back {resp}")
            if (not self.processing.hk_output_queue.empty()):
                self.logger.warning(f"Housekeeping queue still has {self.processing.hk_output_queue.qsize()} items")
            return resp

    def reset(self):
        print("Python Ethernet --> Resetting, wait a few seconds")
        self.write_reg(self.spectrometer_reset,1)
        time.sleep(3)
        self.write_reg(self.spectrometer_reset,0)
        time.sleep(2)
        self.write_cdi_reg(self.cdi_reset,1)
        time.sleep(2)
        self.write_cdi_reg(self.cdi_reset,0)
        time.sleep(1)
        self.write_cdi_reg(self.latch_register, 0)
        time.sleep(self.wait_time)

    def request_fw_packet(self):
        self.write_reg(self.start_tlm_data, 1)
        self.write_reg(self.start_tlm_data, 0)

    def request_sw_packet(self):
        self.write_reg(self.tlm_reg, 1)
        self.write_reg(self.tlm_reg, 0)

    def get_adc_data(self, timeout = 1):
        self.logger.debug(f"Waiting for data")
        while not self.stop_event.is_set():
            resp = self.processing.adc_output_queue.get(True, timeout)
            self.processing.adc_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"get_adc_data has been told to stop. Exiting...")
                break
            if (not self.processing.adc_output_queue.empty()):
                self.logger.warning(f"ADC queue still has {self.processing.adc_output_queue.qsize()} items")
            return resp

    def get_count_data(self, timeout = 1):
        self.logger.debug(f"Waiting for Count data")
        while not self.stop_event.is_set():
            resp = self.processing.count_output_queue.get(True, timeout)
            self.processing.count_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"get_count_data has been told to stop. Exiting...")
                break
            if (not self.processing.count_output_queue.empty()):
                self.logger.warning(f"Count queue still has {self.processing.count_output_queue.qsize()} items")
            return resp

    def get_pfb_data(self, timeout = 1, clear = False):
        self.logger.debug(f"Waiting for PFB data")
        while not self.stop_event.is_set():
            resp = self.processing.pfb_output_queue.get(True, timeout)
            self.processing.pfb_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"get_pfb_data has been told to stop. Exiting...")
                break
            if (not self.processing.pfb_output_queue.empty()):
                self.logger.warning(f"PFB queue still has {self.processing.pfb_output_queue.qsize()} items")
                #This happens with the firmware PFB output for some reason
                if (clear):
                    self.logger.warning("Will clear queue")
                    while not self.processing.pfb_output_queue.empty():
                        self.processing.pfb_output_queue.get()
            return resp

    def get_data_packets(self, data_type, num=1, header = False):
        if ((data_type != "adc") and (data_type != "fft") and (data_type != "sw") and (data_type != "cal")):
            print(f"Python Ethernet --> Error in 'get_data_packets': Must request 'adc' or 'fft' or 'sw' as 'data_type'. You requested {data_type}")
            return []
        numVal = int(num)
        #set up IPv4, UDP listening socket at requested IP
        sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_data.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_data.bind((self.PC_IP,self.PORT_HSDATA))
        sock_data.settimeout(self.udp_timeout)
        #Read a certain amount of packets
        incoming_packets = []
        if (data_type != 'sw' and data_type != 'cal'):
            self.start()
        else:
            self.request_sw_packet()

        for packet in range(0,numVal,1):
            data = []
            try:
                data = sock_data.recv(self.BUFFER_SIZE)
            except socket.timeout:
                    print ("Python Ethernet --> Error get_data_packets: No data packet received from board, quitting")
                    print ("Python Ethernet --> Socket was {}".format(sock_data))
                    if (header):
                        return [], []
                    else:
                        return []
            except OSError:
                print ("Python Ethernet --> Error accessing socket: No data packet received from board, quitting")
                print ("Python Ethernet --> Socket was {}".format(sock_data))
                sock_data.close()
                if (header):
                    return [], []
                else:
                    return []
            if (data != None):
                incoming_packets.append(data)
        #print (sock_data.getsockname())
        sock_data.close()
        if (data_type == "adc"):
            formatted_data, header_dict = self.check_data_adc(incoming_packets)
        elif (data_type == "cal"):
            return incoming_packets
        else:
            formatted_data, header_dict = self.check_data_pfb(incoming_packets)
        if (header):
            return formatted_data, header_dict
        else:
            return formatted_data

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = '../config/config_logger.ini'
    config_path = os.path.join(script_dir, relative_path)
    logging.config.fileConfig(config_path)

    e = LuSEE_ETHERNET()
    e.write_reg(0x121, 0x69)
    resp = e.read_reg(0x121)
    if (resp != 0x69):
        e.logger.error(f"Response was {resp}")
    else:
        e.logger.info(f"Response was {resp}")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        e.logger.debug("Keyboard interrupt")
    finally:
        e.logger.debug("Main program interrupted, stopping listener...")
        e.stop()
        #e.data_queue.put((None, None))  # Optionally, signal the processing thread to exit
        e.logger.debug("Program terminated cleanly.")
