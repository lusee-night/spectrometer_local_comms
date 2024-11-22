import time
import os,sys
import struct
import socket
import binascii
import threading
import queue
from queue import Empty
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
        tries = 10
        for i in range(tries):
            read_dict = {"command": "read",
                        "reg": int(reg)}
            self.send_queue.put(read_dict)
            self.logger.debug(f"Reading Register {hex(reg)}")
            while not self.stop_event.is_set():
                try:
                    resp = self.processing.reg_output_queue.get(True, self.read_timeout)
                except Empty:
                    self.logger.warning(f"Register queue was empty for the {i} time. Retrying")
                    break
                self.processing.reg_output_queue.task_done()
                if resp is self.processing.stop_signal:
                    self.logger.debug(f"read_reg has been told to stop. Exiting...")
                    break
                self.logger.debug(f"Read back {hex(resp['data'])}")
                if (not self.processing.reg_output_queue.empty()):
                    self.logger.warning(f"Register queue still has {self.processing.reg_output_queue.qsize()} items")
                return resp["data"]
        self.logger.warning(f"Register tried {tries} times, but could not get a response for the register")
        return None

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
        self.write_cdi_reg(self.cdi_reset, 1, self.PORT_WREG)
        time.sleep(2)
        self.write_cdi_reg(self.cdi_reset, 0, self.PORT_WREG)
        time.sleep(1)
        self.write_cdi_reg(self.latch_register, 0, self.PORT_WREG)
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
            try:
                resp = self.processing.adc_output_queue.get(True, timeout)
            except Empty:
                self.logger.warning(f"ADC data never came")
                return None
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

    def get_calib_data(self, timeout = 10, clear = False):
        self.logger.debug(f"Waiting for Calibration data")
        while not self.stop_event.is_set():
            resp = self.processing.calib_output_queue.get(True, timeout)
            self.processing.calib_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"get_calib_data has been told to stop. Exiting...")
                break
            if (not self.processing.calib_output_queue.empty()):
                self.logger.warning(f"Calib queue still has {self.processing.calib_output_queue.qsize()} items")
                #This happens with the firmware PFB output for some reason
                if (clear):
                    self.logger.warning("Will clear queue")
                    while not self.processing.calib_output_queue.empty():
                        self.processing.calib_output_queue.get()
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

<<<<<<< HEAD
    #Unpack the header files into a dictionary, this is common for all CDI responses
    def organize_header(self, formatted_data):
        header_dict = {}

        header_dict["udp_packet_num"] = hex((formatted_data[0] << 16) + formatted_data[1])
        header_dict["header_user_info"] = hex((formatted_data[2] << 48) + (formatted_data[3] << 32) + (formatted_data[4] << 16) + formatted_data[5])
        header_dict["system_status"] = hex((formatted_data[6] << 16) + formatted_data[7])
        header_dict["message_id"] = hex(formatted_data[8] >> 10)
        header_dict["message_length"] = hex(formatted_data[8] & 0x3FF)
        header_dict["message_spare"] = hex(formatted_data[9])
        header_dict["ccsds_version"] = hex(formatted_data[10] >> 13)
        header_dict["ccsds_packet_type"] = hex((formatted_data[10] >> 12) & 0x1)
        header_dict["ccsds_secheaderflag"] = hex((formatted_data[10] >> 11) & 0x1)
        header_dict["ccsds_appid"] = hex(formatted_data[10] & 0x7FF)
        header_dict["ccsds_groupflags"] = hex(formatted_data[11] >> 14)
        header_dict["ccsds_sequence_cnt"] = hex(formatted_data[11] & 0x3FFF)
        header_dict["ccsds_packetlen"] = hex(formatted_data[12])
        return header_dict

    def check_data_adc(self, data):
        udp_packet_count = 0
        cdi_packet_count = 0
        data_packet = []
        header_dict = {}
        #Packet format defined by Jack Fried in VHDL for custom CDI interface
        #Headers come in as 16 bit words. ADC and counter payload comes in as 16 bit words
        #FFT data comes in as 32 bit words. There are 13 header bytes. That's where the problem starts.
        #These variables are to communicate state between the loops for datums that are split between packets
        even = True;
        carry_val = 0;
        for num,i in enumerate(data):
            header_dict[num] = {}
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)
            header_dict[num] = self.organize_header(formatted_data)
            #ADC data is simple, it's the 16 bit shorts that were already unpacked
            data_packet.extend(formatted_data[13:])

        return data_packet, header_dict

    def check_data_pfb(self, data):
        udp_packet_count = 0
        cdi_packet_count = 0
        header_dict = {}
        #Packet format defined by Jack Fried in VHDL for custom CDI interface
        #Headers come in as 16 bit words. ADC and counter payload comes in as 16 bit words
        #FFT data comes in as 32 bit words. There are 13 header bytes. That's where the problem starts.
        #These variables are to communicate state between the loops for datums that are split between packets
        even = True;
        carry_val = 0;
        raw_data = bytearray()
        for num,i in enumerate(data):
            header_dict[num] = {}
            #print(f"Length is {len(i)}")
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes just for the header
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)
            header_dict[num] = self.organize_header(formatted_data)
            #Payload starts at nibble 26
            raw_data.extend(i[26:])

        #After the payload part of all the incoming packets has been concatenated, we know it's exactly 2048 bins and can unpack it appropriately
        formatted_data2 = struct.unpack_from(">2048I",raw_data)
        #But each 2 byte section of the 4 byte value is reversed
        formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]
        return formatted_data3, header_dict

    def check_data_cal(self, data, data_len):
        udp_packet_count = 0
        cdi_packet_count = 0
        header_dict = {}
        #Packet format defined by Jack Fried in VHDL for custom CDI interface
        #Headers come in as 16 bit words. ADC and counter payload comes in as 16 bit words
        #FFT data comes in as 32 bit words. There are 13 header bytes. That's where the problem starts.
        #These variables are to communicate state between the loops for datums that are split between packets
        even = True;
        carry_val = 0;
        raw_data = bytearray()
        for num,i in enumerate(data):
            header_dict[num] = {}
            #print(f"Length is {len(i)}")
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes just for the header
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)
            header_dict[num] = self.organize_header(formatted_data)
            #Payload starts at nibble 26
            raw_data.extend(i[26:])

        #After the payload part of all the incoming packets has been concatenated, we know it's exactly 2048 bins and can unpack it appropriately
        formatted_data2 = struct.unpack_from(f">{data_len}I",raw_data)
        #But each 2 byte section of the 4 byte value is reversed
        formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]
        return formatted_data3, header_dict

    #Writes a bootloader command without waiting for a result
    def send_bootloader_message(self, message):
        self.write_cdi_reg(self.write_register, message)
        self.toggle_cdi_latch()

    #Sets up a socket and then writes a bootloader command to listen to a result
    #If we open the socket after writing the command, we'll miss the response
    def send_bootloader_message_response(self, message):
        #Set up listening socket - IPv4, UDP
        sock_readresp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #Allows us to quickly access the same socket and ignore the usual OS wait time betweeen accesses
        sock_readresp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_readresp.bind((self.PC_IP, self.PORT_HK))
        sock_readresp.settimeout(self.udp_timeout)

        #The command to reset the microcontroller and check for the packet that it sends out
        #is not actually a bootloader command, so it has to be done like this
        if (message == self.RESET_UC):
            self.write_reg(self.UC_REG, 1)
            self.write_reg(self.UC_REG, 0)
        else:
            self.send_bootloader_message(message)

        #Bootloader command responses are always one packet, unless we requested a readback
        #of a hex data region
        if (message == self.SEND_PROGRAM_TO_DCB):
            keep_listening = True
            data = []
        else:
            keep_listening = False

        while(True):
            try:
                if (keep_listening):
                    data.append(sock_readresp.recv(self.BUFFER_SIZE))
                else:
                    data = sock_readresp.recv(self.BUFFER_SIZE)
                    break
            except socket.timeout:
                if (not keep_listening):
                    print ("Python Ethernet --> Error read_cdi_reg: No read packet received from board, quitting")
                    print ("Waited for CDI response on")
                    print (sock_readresp.getsockname())
                    return None
                else:
                    #print("Packets stopped coming")
                    break
                sock_readresp.close()
        sock_readresp.close()

        if (keep_listening):
            return self.unpack_hex_readback(data)
        else:
            try:
                unpacked = self.check_data_bootloader(data)
                return unpacked
            except TypeError as e:
                print(e)
                print (f"Python Ethernet --> Error trying to parse CDI housekeeping readback. Data was {data}")

    #Not implemented/finished yet because this function is still under construction in the bootloader
    def unpack_hex_readback(self, data):
        header_dict = {}
        bootloader_dict = {}
        num = 0
        for i in data:
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)
            header_dict[num] = self.organize_header(formatted_data)
            #The header is 13 bytes (26 hex byte characters) and the payload starts after as 32 bit ints
            pkt = bytearray()
            pkt.extend(i[26:])

            data_size = int(len(pkt)/4)
            formatted_data2 = struct.unpack_from(f">{data_size}I",pkt)
            #But the payload is reversed 2 bytes by 2 bytes
            formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]
            #fm3 = [hex(i) for i in formatted_data3]
            #print(fm3)
            #With the formatted payload, get all relevant info
            bootloader_resp = self.unpack_bootloader_packet(formatted_data3)
            bootloader_dict[num] = bootloader_resp
            num += 1
        return header_dict, bootloader_dict

    #The bootloader response has the standard CDI header, so that's formatted
    #And the payload is sent for further processing
    def check_data_bootloader(self, data):
        data_packet = bytearray()
        header_dict = {}

        unpack_buffer = int((len(data))/2)
        #Unpacking into shorts in increments of 2 bytes
        formatted_data = struct.unpack_from(f">{unpack_buffer}H",data)
        header_dict = self.organize_header(formatted_data)

        #The header is 13 bytes (26 hex byte characters) and the payload starts after as 32 bit ints
        data_packet.extend(data[26:])
        data_size = int(len(data_packet)/4)
        formatted_data2 = struct.unpack_from(f">{data_size}I",data_packet)
        #But for every 4 byte value in the payload, the first and last 2 bytes are reversed
        formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]

        #With the formatted payload, get all relevant header info
        if (formatted_data3):
            bootloader_resp = self.unpack_bootloader_packet(formatted_data3)
        else:
            bootloader_resp = None

        return bootloader_resp, header_dict

    #This looks at the common elements of each bootloader response header
    #Depending on the type of packet response, it knows how to process it further
    def unpack_bootloader_packet(self, packet):
        bootloader_dict = {}
        bootloader_dict['BL_Message'] = hex(packet[0])
        bootloader_dict['BL_count'] = hex(packet[1])
        bootloader_dict['BL_timestamp'] = hex((packet[3] << 32) + packet[2])

        date_string = format(packet[4], 'x')
        time_string = format(packet[5], 'x')
        year = int(date_string[:4])
        month = int(date_string[4:6])
        day = int(date_string[6:])
        hour = int(time_string[:2])
        minute = int(time_string[2:4])
        second = int(time_string[4:6])
        datetime_object = datetime(year = year, month = month, day = day, hour = hour, minute = minute, second = second)
        bootloader_dict['BL_datetime'] = datetime_object
        formatted_data = datetime_object.strftime("%B %d, %Y %I:%M:%S %p")
        bootloader_dict['BL_formatted_datetime'] = formatted_data

        bootloader_dict['BL_version'] = hex(packet[6])
        bootloader_dict['BL_end'] = hex(packet[7])

        if (packet[0] == 0):
            pass
        if (packet[0] == 1):
            resp = self.unpack_program_jump(packet[8:])
            bootloader_dict.update(resp)
        elif (packet[0] == 2):
            resp = self.unpack_program_info(packet[8:])
            bootloader_dict.update(resp)
        elif (packet[0] == 3):
            resp = self.unpack_program_readback(packet[8:])
            bootloader_dict.update(resp)

        return bootloader_dict

    #This is the format for the response packet when the client requested to jump into the loaded program
    def unpack_program_jump(self, packet):
        program_info_dict = {}
        program_info_dict["region_jumped_to"] = hex(packet[0])
        program_info_dict["default_vals_loaded"] = packet[1]
        return program_info_dict

    #This is the format for the response packet when the client requested program info
    def unpack_program_info(self, packet):
        program_info_dict = {}
        for i in range(0,6):
            program_info_dict[f"Program{i+1}_metadata_size"] = hex(packet[i*3])
            program_info_dict[f"Program{i+1}_metadata_checksum"] = hex(packet[(i*3)+1])
            program_info_dict[f"Program{i+1}_calculated_checksum"] = hex(packet[(i*3)+2])
        program_info_dict["Loaded_program_size"] = hex(packet[18])
        program_info_dict["Loaded_program_checksum"] = hex(packet[19])
        return program_info_dict

    #This is the format for the packets coming in that are reading out the loaded softare in flash memory
    def unpack_program_readback(self, packet):
        bootloader_start_dict = {}
        data = []
        line = ""
        for num,i in enumerate(packet):
            segment = f"{i:08x}"
            data.append(segment)

        bootloader_start_dict["data"] = data
        bootloader_start_dict["lines"] = len(data)
        return bootloader_start_dict

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
