import threading
import queue
import logging
import logging.config

class LuSEE_PROCESS_HK:
    def __init__(self, parent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        self.parent = parent
        self.stop_event = parent.stop_event
        self.stop_signal = parent.stop_signal
        self.hk_input_queue = parent.hk_input_queue
        self.hk_output_queue = parent.hk_output_queue

    def process_hk(self):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started")
        while not self.stop_event.is_set():
            data = self.hk_input_queue.get()
            self.hk_input_queue.task_done()
            if data is self.stop_signal:
                self.logger.debug(f"{name} has been told to stop. Exiting...")
                break

            self.hk_output_queue.put(check_data_bootloader(data))
        self.logger.debug(f"{name} exited")

    #The bootloader response has the standard CDI header, so that's formatted
    #And the payload is sent for further processing
    def check_data_bootloader(self, data):
        data_packet = bytearray()
        header_dict = {}

        unpack_buffer = int((len(data))/2)
        #Unpacking into shorts in increments of 2 bytes
        formatted_data = struct.unpack_from(f">{unpack_buffer}H",data)
        header_dict = self.parent.organize_header(formatted_data)

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

        return header_dict.update(bootloader_resp)

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

    #This is the format for the packets coming in that are reading out the loaded software in flash memory
    def unpack_program_readback(self, packet):
        readback_dict = {}
        data = []
        for num,i in enumerate(packet):
            segment = f"{i:08x}"
            data.append(segment)

        readback_dict["data"] = data
        readback_dict["lines"] = len(data)
        return readback_dict
