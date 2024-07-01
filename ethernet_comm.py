import time
import os,sys
import struct
import csv
import socket
import binascii

class LuSEE_ETHERNET:
    def __init__(self):
        self.version = 1.15

        self.UDP_IP = "192.168.121.1"
        self.PC_IP = "192.168.121.50"
        self.udp_timeout = 1

        self.FEMB_PORT_WREG = 32000
        self.FEMB_PORT_RREG = 32001
        self.FEMB_PORT_RREGRESP = 32002
        self.PORT_HSDATA = 32003
        self.PORT_HK = 32003
        self.BUFFER_SIZE = 9014

        self.KEY1 = 0xDEAD
        self.KEY2 = 0xBEEF
        self.FOOTER = 0xFFFF

        self.wait_time = 0.01

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

        self.RESET_UC = 0xBFFFFF
        self.SEND_PROGRAM_TO_DCB = 0xB00009
        self.UC_REG = 0x100
        self.BL_RESET = 0x0
        self.BL_JUMP = 0x1
        self.BL_PROGRAM_CHECK = 0x2
        self.BL_PROGRAM_VERIFY = 0x3

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

    def toggle_cdi_latch(self):
        self.write_cdi_reg(self.latch_register, 1)
        time.sleep(self.wait_time)
        attempt = 0
        while True:
            if ((self.read_cdi_reg(self.latch_register)) >> 31):
                break
            else:
                attempt += 1
            if (attempt > 10):
                sys.exit(f"Python Ethernet --> Error in writing to DCB emulator. Register 1 is {hex(self.read_cdi_reg(self.latch_register))}")

    def write_reg(self, reg, data):
        for i in range(10):
            if (i > 0):
                print(f"Python Ethernet --> Re-attempt {i}")
            regVal = int(reg)
            dataVal = int(data)
            #Splits the register up, since both halves need to go through socket.htons seperately
            dataValMSB = ((dataVal >> 16) & 0xFFFF)
            dataValLSB = dataVal & 0xFFFF

            dataMSB = self.first_data_pack + dataValMSB
            self.write_cdi_reg(self.write_register, dataMSB)
            time.sleep(self.wait_time)
            self.toggle_cdi_latch()

            dataLSB = self.second_data_pack + dataValLSB
            self.write_cdi_reg(self.write_register, dataLSB)
            time.sleep(self.wait_time)
            self.toggle_cdi_latch()

            address_value = self.address_write + reg
            self.write_cdi_reg(self.write_register, address_value)
            time.sleep(self.wait_time)
            self.toggle_cdi_latch()

            time.sleep(self.wait_time * 10) #Some registers need a longer wait before reading back for some reason
            readback = self.read_reg(reg)
            if (readback == data):
                break
            elif (reg in self.exception_registers):
                break
            else:
                print(f"Python Ethernet --> Tried to write {hex(data)} to register {hex(reg)} but read back {hex(readback)}")

    def read_reg(self, reg):
        address_value = self.address_read + reg
        self.write_cdi_reg(self.write_register, address_value)
        time.sleep(self.wait_time)
        self.toggle_cdi_latch()

        resp = self.read_cdi_reg(self.readback_register)
        return int(resp)

    def write_cdi_reg(self, reg, data):
        regVal = int(reg)
        dataVal = int(data)
        #Splits the register up, since both halves need to go through socket.htons seperately
        dataValMSB = ((dataVal >> 16) & 0xFFFF)
        dataValLSB = dataVal & 0xFFFF
        WRITE_MESSAGE = struct.pack('HHHHHHHHH',socket.htons( self.KEY1  ), socket.htons( self.KEY2 ),
                                    socket.htons(regVal),socket.htons(dataValMSB),
                                    socket.htons(dataValLSB),socket.htons( self.FOOTER ), 0x0, 0x0, 0x0  )

        #Set up socket for IPv4 and UDP, attach the correct PC IP
        sock_write = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock_write.bind((self.PC_IP, 0))
        except:
            print("IP: {}".format(self.PC_IP))
        sock_write.sendto(WRITE_MESSAGE,(self.UDP_IP, self.FEMB_PORT_WREG ))

        #print ("Sent FEMB data from")
        #print (sock_write.getsockname())
        sock_write.close()
        #print ("Python Ethernet --> Write: reg=%x,value=%x"%(reg,data))
        #time.sleep(self.wait_time)

    #Read a full register from the FEMB FPGA.  Returns the 32 bits in an integer form
    def read_cdi_reg(self, reg):
        regVal = int(reg)
        for i in range(10):
            #Set up listening socket before anything else - IPv4, UDP
            sock_readresp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #Allows us to quickly access the same socket and ignore the usual OS wait time betweeen accesses
            sock_readresp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_readresp.bind((self.PC_IP, self.FEMB_PORT_RREGRESP ))
            sock_readresp.settimeout(self.udp_timeout)

            #First send a request to read out this sepecific register at the read request port for the board
            READ_MESSAGE = struct.pack('HHHHHHHHH',socket.htons(self.KEY1), socket.htons(self.KEY2),socket.htons(regVal),0,0,socket.htons(self.FOOTER),0,0,0)
            sock_read = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock_read.setblocking(0)
            sock_read.bind((self.PC_IP, 0))
            sock_read.sendto(READ_MESSAGE,(self.UDP_IP,self.FEMB_PORT_RREG))

            #print ("Sent read request from")
            #print (sock_read.getsockname())
            sock_read.close()

            #try to receive response packet from board, store in hex
            data = []
            try:
                data = sock_readresp.recv(self.BUFFER_SIZE)
            except socket.timeout:
                if (i > 9):
                    print ("Python Ethernet --> Error read_cdi_reg: No read packet received from board, quitting")
                    print ("Waited for CDI response on")
                    print (sock_readresp.getsockname())
                    sock_readresp.close()
                    return None
                else:
                    print (f"Python Ethernet --> Didn't get a readback response for {hex(reg)}, trying again...")

            #print ("Waited for FEMB response on")
            #print (sock_readresp.getsockname())
            sock_readresp.close()
            if (data != []):
                break

        #Goes from binary data to hexidecimal (because we know this is host order bits)
        dataHex = []
        try:
            dataHex = binascii.hexlify(data)
            #If reading, say register 0x290, you may get back
            #029012345678
            #The first 4 bits are the register you requested, the next 8 bits are the value
            #Looks for those first 4 bits to make sure you read the register you're looking for
            if int(dataHex[0:4],16) != regVal :
                print ("Python Ethernet --> Error read_cdi_reg: Invalid response packet")
                return None

            #Return the data part of the response in integer form (it's just easier)
            dataHexVal = int(dataHex[4:12],16)
            #print ("FEMB_UDP--> Read: reg=%x,value=%x"%(reg,dataHexVal))
            return dataHexVal
        except TypeError:
            print (f"Python Ethernet --> Error trying to parse CDI Register readback. Data was {data}")

    def start(self):
        self.write_reg(self.start_tlm_data, 1)
        self.write_reg(self.start_tlm_data, 0)

    def request_sw_packet(self):
        self.write_reg(self.tlm_reg, 1)
        self.write_reg(self.tlm_reg, 0)

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

    #Unpack the header files into a dictionary, this is common for all CDI responses
    def organize_header(self, formatted_data):
        header_dict = {}

        header_dict["udp_packet_num"] = hex((formatted_data[0] << 16) + formatted_data[1])
        header_dict["header_user_info"] = hex((formatted_data[2] << 48) + (formatted_data[3] << 32) + (formatted_data[4] << 16) + formatted_data[5])
        header_dict["system_status"] = hex((formatted_data[6] << 16) + formatted_data[7])
        header_dict["message_id"] = hex(formatted_data[8] >> 10)

        header_dict["message_spare"] = hex(formatted_data[9])
        header_dict["ccsds_version"] = hex(formatted_data[10] >> 13)
        header_dict["ccsds_packet_type"] = hex((formatted_data[10] >> 12) & 0x1)
        header_dict["ccsds_secheaderflag"] = hex((formatted_data[10] >> 11) & 0x1)
        header_dict["ccsds_appid"] = hex(formatted_data[10] & 0x7FF)
        header_dict["ccsds_groupflags"] = hex(formatted_data[11] >> 14)
        header_dict["ccsds_sequence_cnt"] = hex(formatted_data[11] & 0x3FFF)

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
                    print("Packets stopped coming")
                    break
                sock_readresp.close()
        sock_readresp.close()

        if (keep_listening):
            self.unpack_hex_readback(data)
        else:
            try:
                unpacked = self.check_data_bootloader(data)
                return unpacked
            except TypeError as e:
                print(e)
                print (f"Python Ethernet --> Error trying to parse CDI Register readback. Data was {data}")

    #Not implemented/finished yet because this function is still under construction in the bootloader
    def unpack_hex_readback(self, data):
        data_packet = bytearray()
        header_dict = {}
        num = 0
        for i in data:
            print(num)
            num += 1
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)
            header_dict[num] = self.organize_header(formatted_data)

            #The header is 13 bytes (26 hex byte characters) and the payload starts after as 32 bit ints
            data_packet.extend(i[26:])

        data_size = int(len(data_packet)/4)
        formatted_data2 = struct.unpack_from(f">{data_size}I",data_packet)
        #But the payload is reversed 2 bytes by 2 bytes
        formatted_data3 = [(j >> 16) + ((j & 0xFFFF) << 16) for j in formatted_data2]
        fm3 = [hex(i) for i in formatted_data3]
        print(fm3)
        #With the formatted payload, get all relevant info
        bootloader_resp = self.unpack_bootloader_packet(formatted_data3)

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
        bootloader_dict['BL_end'] = hex(packet[7])

        if (packet[0] == 1):
            resp = self.unpack_program_jump(packet[8:])
            bootloader_dict.update(resp)
        elif (packet[0] == 2):
            resp = self.unpack_program_info(packet[8:])
            bootloader_dict.update(resp)

        return bootloader_dict

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

    #This is the format for the response packet when the client requested to jump into the loaded program
    def unpack_program_jump(self, packet):
        program_info_dict = {}
        program_info_dict["region_jumped_to"] = hex(packet[0])
        program_info_dict["default_vals_loaded"] = packet[1]
        return program_info_dict

if __name__ == "__main__":
    #arg = sys.argv[1]
    luseeEthernet = LuSEE_ETHERNET()

    print(luseeEthernet.read_cdi_reg(0x120))
