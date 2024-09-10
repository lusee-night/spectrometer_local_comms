import threading
import queue
import struct
import logging
import logging.config

class LuSEE_PROCESS_DATA:
    def __init__(self, parent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        self.parent = parent
        self.stop_event = parent.stop_event
        self.stop_signal = parent.stop_signal
        self.data_input_queue = parent.data_input_queue
        self.count_output_queue = parent.count_output_queue
        self.adc_output_queue = parent.adc_output_queue
        self.pfb_output_queue = parent.pfb_output_queue

        self.count_num = None
        self.bytes_per_packet = 0x7F8
        self.count_pkt_num = None
        self.count_apid = "0x209"
        self.adc_pkt_num = 9
        self.adc_apids = ["0x220", "0x221", "0x222", "0x223", "0x2f0", "0x2f1", "0x2f2", "0x2f3"]
        self.fft_pkt_num = 3
        self.fft_apids = ["0x210", "0x211", "0x212", "0x213", "0x214", "0x215", "0x216", "0x217", "0x218", "0x219", "0x21a", "0x21b", "0x21c", "0x21d", "0x21e", "0x21f", "0x2e0", "0x2e1", "0x2e2", "0x2e3"]

    def process_data(self):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started")
        #This will track the type of data packet we are receiving and what number packet we're on
        current_type = [None, 0]
        running_process = {"header" : {}}
        while not self.stop_event.is_set():
            data = self.data_input_queue.get()
            self.data_input_queue.task_done()
            if data is self.stop_signal:
                self.logger.debug(f"{name} has been told to stop. Exiting...")
                break

            #Packet format defined by Jack Fried in VHDL for custom CDI interface
            #Headers come in as 16 bit words
            unpack_buffer = int((len(data))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",data)
            header = self.parent.organize_header(formatted_data)
            if ((header["ccsds_appid"] in self.fft_apids) and ((current_type[0] == None) or (current_type[0] == "FFT"))):
                running_process["header"][current_type[1]] = header
                current_type[1] += 1
                self.logger.debug(f"This is packet #{current_type[1]} in an FFT sequence")
                if (current_type[1] < self.fft_pkt_num):
                    #The rest of the raw data is after the 13 * 2 byte header
                    if ("raw_data" in running_process):
                        running_process["raw_data"] += (data[26:])
                    else:
                        running_process["raw_data"] = data[26:]
                    current_type[0] = "FFT"
                elif (current_type[1] == self.fft_pkt_num):
                    self.logger.debug("Final packet for FFT")
                    running_process["raw_data"] += (data[26:])

                    #After the payload part of all the incoming packets has been concatenated, we know it's exactly 2048 bins and can unpack it appropriately
                    formatted_data2 = struct.unpack_from(">2048I",running_process["raw_data"])
                    #But each 2 byte section of the 4 byte value is reversed
                    formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]
                    final_header = {"header" : running_process["header"],
                                    "data" : formatted_data3
                                    }
                    self.pfb_output_queue.put(final_header)
                    current_type = [None, 0]
                    running_process = {"header" : {}}
                else:
                    self.logger.warning(f"Was reading FFT and packet number is {current_type[1]}")
                    current_type = [None, 0]
                    running_process = {"header" : {}}
            elif ((header["ccsds_appid"] in self.adc_apids) and ((current_type[0] == None) or (current_type[0] == "ADC"))):
                running_process["header"][current_type[1]] = header
                current_type[1] += 1
                self.logger.debug(f"This is packet #{current_type[1]} in an ADC sequence")
                if (current_type[1] < self.adc_pkt_num):
                    #The rest of the raw data is after the 13 * 2 byte header
                    #For the ADC, there's no chance of data stradding 2 packets, so it can be put in as a 16 bit value
                    if ("data" in running_process):
                        running_process["data"].extend(formatted_data[13:])
                    else:
                        running_process["data"] = list(formatted_data[13:])
                    current_type[0] = "ADC"
                elif (current_type[1] == self.adc_pkt_num):
                    self.logger.debug("Final packet for ADC")
                    running_process["data"].extend(formatted_data[13:])
                    self.adc_output_queue.put(running_process)
                    current_type = [None, 0]
                    running_process = {"header" : {}}
                else:
                    self.logger.warning(f"Was reading ADC and packet number is {current_type[1]}")
                    current_type = [None, 0]
                    running_process = {"header" : {}}
            elif ((header["ccsds_appid"] == self.count_apid) and ((current_type[0] == None) or (current_type[0] == "Count"))):
                running_process["header"][current_type[1]] = header
                current_type[1] += 1
                self.logger.debug(f"This is packet #{current_type[1]} in a Counter sequence")
                if (current_type[1] == 0):
                    if not self.count_num:
                        self.logger.error(f"Counter packet receiving state machine does not know counter size. Count size in bytes must be set")
                        continue
                    else:
                        self.count_pkt_num = (self.count_num // self.bytes_per_packet) + 1
                        running_process["data"] = list(formatted_data[13:])
                        if (self.count_pkt_num == 1):
                            self.count_output_queue.put(running_process)
                            current_type = [None, 0]
                            running_process = {"header" : {}}
                        else:
                            current_type[0] == "Count"
                elif (not self.count_pkt_num):
                    self.logger.error(f"Counter packet receiving state machine does not know counter packet num. But packet number was {current_type[1]}")
                    continue
                elif (current_type[1] < self.count_pkt_num):
                    if ("data" in running_process):
                        running_process["data"].extend(formatted_data[13:])
                    else:
                        self.logger.error(f"Counter packet receiving state machine has middle packets before first!")
                    current_type[0] = "Count"
                elif (current_type[1] == self.count_pkt_num):
                    self.logger.debug("Final packet for Counter")
                    running_process["data"].extend(formatted_data[13:])
                    self.count_output_queue.put(running_process)
                    current_type = [None, 0]
                    running_process = {"header" : {}}
                else:
                    self.logger.warning(f"Was reading Count and packet number is {current_type[1]}")
                    current_type = [None, 0]
                    running_process = {"header" : {}}
            else:
                self.logger.error(f"APID is {header['ccsds_appid']}, running type is {current_type}")

        self.logger.debug(f"{name} exited")
