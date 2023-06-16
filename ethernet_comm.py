import time
import os,sys
import struct
import csv
import socket
import binascii
import matplotlib.pyplot as plt

class LuSEE_ETHERNET:
    def __init__(self):
        self.UDP_IP = "192.168.121.1"
        self.PC_IP = "192.168.121.50"

        self.FEMB_PORT_WREG = 32000
        self.FEMB_PORT_RREG = 32001
        self.FEMB_PORT_RREGRESP = 32002
        self.BUFFER_SIZE = 9014

        self.KEY1 = 0xDEAD
        self.KEY2 = 0xBEEF
        self.FOOTER = 0xFFFF

        self.write_num = 0x2
        self.latch_reg = 0x1
        self.first_pack = 0xA20000
        self.second_pack = 0xA30000
        self.address_write = 0xA10000
        self.address_read = 0xA00000

    def write_reg(self, reg, data):
        regVal = int(reg)
        dataVal = int(data)
        #Splits the register up, since both halves need to go through socket.htons seperately
        dataValMSB = ((dataVal >> 16) & 0xFFFF)
        dataValLSB = dataVal & 0xFFFF

        self.write_cdi_reg(self.latch_reg, 0)
        first_value = self.first_pack + dataValMSB
        self.write_cdi_reg(self.write_num, first_value)

        self.write_cdi_reg(self.latch_reg, 1)
        self.write_cdi_reg(self.latch_reg, 0)

        second_value = self.second_pack + dataValLSB
        self.write_cdi_reg(self.write_num, second_value)

        self.write_cdi_reg(self.latch_reg, 1)
        self.write_cdi_reg(self.latch_reg, 0)

        address_value = self.address_write + reg
        self.write_cdi_reg(self.write_num, address_value)

        self.write_cdi_reg(self.latch_reg, 1)
        self.write_cdi_reg(self.latch_reg, 0)

    def read_reg(self, reg):
        address_value = self.address_read + reg
        self.write_cdi_reg(self.write_num, address_value)
        self.write_cdi_reg(self.latch_reg, 1)
        self.write_cdi_reg(self.latch_reg, 0)

        resp = self.read_cdi_reg(11)
        return resp

    def write_cdi_reg(self, reg, data):
        regVal = int(reg)
        dataVal = int(data)
        #Splits the register up, since both halves need to go through socket.htons seperately
        dataValMSB = ((dataVal >> 16) & 0xFFFF)
        dataValLSB = dataVal & 0xFFFF

        #Organize packets as described in user manual
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
        #print ("FEMB_UDP--> Write: reg=%x,value=%x"%(reg,data))

    #Read a full register from the FEMB FPGA.  Returns the 32 bits in an integer form
    def read_cdi_reg(self, reg):
        regVal = int(reg)
        for i in range(10):
            #Set up listening socket before anything else - IPv4, UDP
            sock_readresp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #Allows us to quickly access the same socket and ignore the usual OS wait time betweeen accesses
            sock_readresp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            sock_readresp.bind((self.PC_IP, self.FEMB_PORT_RREGRESP ))

            sock_readresp.settimeout(.2)

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
                    print ("FEMB_UDP--> Error read_reg: No read packet received from board, quitting")
                    print ("Waited for FEMB response on")
                    print (sock_readresp.getsockname())
                    sock_readresp.close()
                    return None
                else:
                    print ("FEMB_UDP--> Didn't get a readback response, trying again...")

            #print ("Waited for FEMB response on")
            #print (sock_readresp.getsockname())
            sock_readresp.close()

            if (data != []):
                break

        #Goes from binary data to hexidecimal (because we know this is host order bits)
        dataHex = []
        print(data)
        try:
            dataHex = binascii.hexlify(data)
            #If reading, say register 0x290, you may get back
            #029012345678
            #The first 4 bits are the register you requested, the next 8 bits are the value
            #Looks for those first 4 bits to make sure you read the register you're looking for
            if int(dataHex[0:4],16) != regVal :
                print ("FEMB_UDP--> Error read_reg: Invalid response packet")
                return None

            #Return the data part of the response in integer form (it's just easier)
            dataHexVal = int(dataHex[4:12],16)
            #print ("FEMB_UDP--> Read: reg=%x,value=%x"%(reg,dataHexVal))
            return dataHexVal
        except TypeError:
            print (data)

if __name__ == "__main__":
    #arg = sys.argv[1]


    luseeEthernet = LuSEE_ETHERNET()
    luseeEthernet.write_cdi_reg(5,69)
    x = luseeEthernet.read_cdi_reg(5)
    print(x)
    luseeEthernet.write_reg(4,69)
    x = luseeEthernet.read_reg(4)
    print(x)
