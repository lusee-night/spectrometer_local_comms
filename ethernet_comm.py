import time
import os,sys
import struct
import csv
import socket
import binascii

class LuSEE_ETHERNET:
    def __init__(self):
        self.version = 1.0

        self.UDP_IP = "192.168.121.1"
        self.PC_IP = "192.168.121.50"
        self.udp_timeout = 1

        self.FEMB_PORT_WREG = 32000
        self.FEMB_PORT_RREG = 32001
        self.FEMB_PORT_RREGRESP = 32002
        self.PORT_HSDATA = 32003
        self.BUFFER_SIZE = 9014

        self.KEY1 = 0xDEAD
        self.KEY2 = 0xBEEF
        self.FOOTER = 0xFFFF

        self.wait_time = 0.01
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

    def reset(self):
        print("Python Ethernet --> Resetting, wait a few seconds")
        self.write_reg(self.spectrometer_reset,1)
        time.sleep(3)
        self.write_reg(self.spectrometer_reset,0)
        time.sleep(2)
        self.write_cdi_reg(self.cdi_reset,1)
        time.sleep(3)
        self.write_cdi_reg(self.cdi_reset,0)
        time.sleep(2)
        self.write_cdi_reg(self.latch_register, 0)
        time.sleep(self.wait_time)

    def toggle_cdi_latch(self):
        self.write_cdi_reg(self.latch_register, 1)
        time.sleep(self.wait_time)
        self.write_cdi_reg(self.latch_register, 0)
        time.sleep(self.wait_time)

    def write_reg(self, reg, data):
        regVal = int(reg)
        dataVal = int(data)
        #Splits the register up, since both halves need to go through socket.htons seperately
        dataValMSB = ((dataVal >> 16) & 0xFFFF)
        dataValLSB = dataVal & 0xFFFF

        dataMSB = self.first_data_pack + dataValMSB
        self.write_cdi_reg(self.write_register, dataMSB)
        self.toggle_cdi_latch()

        dataLSB = self.second_data_pack + dataValLSB
        self.write_cdi_reg(self.write_register, dataLSB)
        self.toggle_cdi_latch()

        address_value = self.address_write + reg
        self.write_cdi_reg(self.write_register, address_value)
        self.toggle_cdi_latch()

    def read_reg(self, reg):
        address_value = self.address_read + reg
        self.write_cdi_reg(self.write_register, address_value)
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
                    print ("Python Ethernet --> Didn't get a readback response, trying again...")

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
        self.write_reg(self.action_register, 1)
        time.sleep(self.wait_time)
        self.write_reg(self.action_register, 0)

    def get_data_packets(self, data_type, num=1, header = False):
        if ((data_type != "adc") and (data_type != "fft")):
            print(f"Python Ethernet --> Error in 'get_data_packets': Must request 'adc' or 'fft' as 'data_type'. You requested {data_type}")
            return []
        numVal = int(num)
        #set up IPv4, UDP listening socket at requested IP
        sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_data.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_data.bind((self.PC_IP,self.PORT_HSDATA))
        sock_data.settimeout(self.udp_timeout)
        #Read a certain amount of packets
        incoming_packets = []
        self.start()
        for packet in range(0,numVal,1):
            data = []
            try:
                data = sock_data.recv(self.BUFFER_SIZE)
            except socket.timeout:
                    print ("Python Ethernet --> Error get_data_packets: No data packet received from board, quitting")
                    print ("Python Ethernet --> Socket was {}".format(sock_data))
                    return []
            except OSError:
                print ("Python Ethernet --> Error accessing socket: No data packet received from board, quitting")
                print ("Python Ethernet --> Socket was {}".format(sock_data))
                sock_data.close()
                return []
            if (data != None):
                incoming_packets.append(data)
        #print (sock_data.getsockname())
        sock_data.close()
        if (data_type == "adc"):
            formatted_data, header_dict = self.check_data_adc(incoming_packets, data_type)
        else:
            formatted_data, header_dict = self.check_data_pfb(incoming_packets, data_type)
        if (header):
            return formatted_data, header_dict
        else:
            return formatted_data

    def check_data_adc(self, data, data_type):
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
            header_dict[f"{num}"] = {}
            unpack_buffer = int((len(i))/2)
            #Unpacking into shorts in increments of 2 bytes
            formatted_data = struct.unpack_from(f">{unpack_buffer}H",i)

            #print(formatted_data)
            udp_packet_num = (formatted_data[0] << 16) + formatted_data[1]
            header_dict[f"{num}"]["header_user_info"] = (formatted_data[2] << 48) + (formatted_data[3] << 32) + (formatted_data[4] << 16) + formatted_data[5]
            header_dict[f"{num}"]["system_status"] = (formatted_data[6] << 16) + formatted_data[7]
            header_dict[f"{num}"]["message_id"] = (formatted_data[8] >> 10)


            header_dict[f"{num}"]["message_spare"] = formatted_data[9]
            header_dict[f"{num}"]["ccsds_version"] = formatted_data[10] >> 13
            header_dict[f"{num}"]["ccsds_packet_type"] = (formatted_data[10] >> 12) & 0x1
            header_dict[f"{num}"]["ccsds_secheaderflag"] = (formatted_data[10] >> 11) & 0x1
            header_dict[f"{num}"]["ccsds_appid"] = formatted_data[10] & 0x7F
            header_dict[f"{num}"]["ccsds_groupflags"] = formatted_data[11] >> 14
            ccsds_sequence_cnt = formatted_data[11] & 0x3FFF

            #ADC data is simple, it's the 16 bit shorts that were already unpacked
            added_packet_size = len(formatted_data[13:])
            data_packet.extend(formatted_data[13:])

        return data_packet, header_dict

    def check_data_pfb(self, data, data_type):
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
            header_dict[f"{num}"] = {}
            #print(f"Length is {len(i)}")
            unpack_buffer = int((len(i))/4)
            #Unpacking into shorts in increments of 2 bytes just for the header
            formatted_data = struct.unpack_from(f">{unpack_buffer*2}H",i)

            #If this is PFB data, then this packet either ends with the first 16 bits of the next sample
            #Or the last 16 bits of the previous sample. Taking these 16 bit shorts help piece it back together later
            first_val = formatted_data[13]
            last_val = formatted_data[(unpack_buffer * 2) - 1]

            #print(formatted_data)
            udp_packet_num = (formatted_data[0] << 16) + formatted_data[1]
            header_dict[f"{num}"]["header_user_info"] = (formatted_data[2] << 48) + (formatted_data[3] << 32) + (formatted_data[4] << 16) + formatted_data[5]
            header_dict[f"{num}"]["system_status"] = (formatted_data[6] << 16) + formatted_data[7]
            header_dict[f"{num}"]["message_id"] = (formatted_data[8] >> 10)


            header_dict[f"{num}"]["message_spare"] = formatted_data[9]
            header_dict[f"{num}"]["ccsds_version"] = formatted_data[10] >> 13
            header_dict[f"{num}"]["ccsds_packet_type"] = (formatted_data[10] >> 12) & 0x1
            header_dict[f"{num}"]["ccsds_secheaderflag"] = (formatted_data[10] >> 11) & 0x1
            header_dict[f"{num}"]["ccsds_appid"] = formatted_data[10] & 0x7F
            header_dict[f"{num}"]["ccsds_groupflags"] = formatted_data[11] >> 14
            ccsds_sequence_cnt = formatted_data[11] & 0x3FFF
            raw_data.extend(i[26:])

        formatted_data2 = struct.unpack_from(">2048I",raw_data)
        return formatted_data2, header_dict

if __name__ == "__main__":
    #arg = sys.argv[1]
    luseeEthernet = LuSEE_ETHERNET()

    print(luseeEthernet.read_cdi_reg(10))
