import binascii
import threading
import queue
import logging
import logging.config
import time

from utils import LuSEE_PROCESS_DATA
from utils import LuSEE_PROCESS_HK
from utils import LuSEE_PROCESS_REG

class LuSEE_PROCESSING:
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
            self.stop_event = threading.Event()
            self.stop_signal = object()

            self.reg_input_queue = queue.Queue()
            self.data_input_queue = queue.Queue()
            self.hk_input_queue = queue.Queue()

            self.dcb_emulator_queue = queue.Queue()
            self.reg_output_queue = queue.Queue()
            self.count_output_queue = queue.Queue()
            self.adc_output_queue = queue.Queue()
            self.pfb_output_queue = queue.Queue()
            self.hk_output_queue = queue.Queue()

            self.reg = LuSEE_PROCESS_REG(self)
            self.data = LuSEE_PROCESS_DATA(self)
            self.hk = LuSEE_PROCESS_HK(self)

            process_thread_settings = [(self.reg.process_reg, "Register Response Processing Thread"),
                                       (self.data.process_data, "Data Processing Thread"),
                                       (self.hk.process_hk, "Housekeeping Processing Thread")]
            self.process_threads = []
            for process_settings in process_thread_settings:
                thread = threading.Thread(target=process_settings[0],
                            name=process_settings[1],
                            daemon = True
                            )
                thread.start()
                self.process_threads.append(thread)

    def stop(self):
        self.logger.debug("Stopping all threads")
        self.stop_event.set()
        self.reg_input_queue.put(self.stop_signal)
        self.data_input_queue.put(self.stop_signal)
        self.hk_input_queue.put(self.stop_signal)
        self.hk_input_queue.put(self.stop_signal)
        for i in self.process_threads:
            self.logger.debug(f"Waiting for {i.name} to join")
            i.join()
            self.logger.debug(f"Class sees that {i.name} is done")

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
