import binascii
import threading
import queue
import struct
import logging
import logging.config

#TODO: Add the register processing from the actual DCB, where the CDI header isn't stripped out.
class LuSEE_PROCESS_REG:
    def __init__(self, parent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        self.readback_register = 0xB #Didn't inherit from ethernet_comm to reduce complexity, but must match that value
        self.parent = parent
        self.stop_event = parent.stop_event
        self.stop_signal = parent.stop_signal
        self.reg_input_queue = parent.reg_input_queue
        self.reg_output_queue = parent.reg_output_queue
        self.dcb_emulator_queue = parent.dcb_emulator_queue

    def process_reg(self):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started")
        while not self.stop_event.is_set():
            data = self.reg_input_queue.get()
            self.reg_input_queue.task_done()
            if data is self.stop_signal:
                self.logger.debug(f"{name} has been told to stop. Exiting...")
                self.reg_output_queue.put(self.stop_signal)
                break
            data_packet = bytearray()
            header_dict = {}

            unpack_buffer = int((len(data))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",data)
            header_dict = self.parent.organize_header(formatted_data)
            self.logger.debug(f"Header dictionary is {header_dict}")
            response_reg = int(formatted_data[5])
            data_val = int((formatted_data[6] << 16) + formatted_data[7])

            response_dict = {"reg": response_reg,
                             "data": data_val}
            self.logger.debug(f"Received {response_dict}")
            self.reg_output_queue.put(response_dict)
        self.logger.debug(f"{name} exited")

