import socket
import struct

class VULCAN_ETHERNET:
    def __init__(self):
        self.VULCAN_IP = "10.10.2.200"
        self.PC_IP = "10.10.2.1"
        self.udp_timeout = 1

        self.VULCAN_PORT = 25012
        self.LISTEN_PORT = 32005
        self.BUFFER_SIZE = 9014

        self.wait_time = 0.01

    def write_test(self):
        # Example ASCII string
        ascii_string = "NSR"

        # Pack the string into bytes
        # The 's' format character is used for a string
        packed_data = struct.pack(f'{len(ascii_string)}s', ascii_string.encode('ascii'))
        # need = so that things don't get padded with 2 byte boundary'
        WRITE_MESSAGE = struct.pack('=BBHBH',0x2,0x6, 0x0, 0x0, 0xFFFF)
        print(WRITE_MESSAGE)

        total = packed_data+WRITE_MESSAGE

        #Set up socket for IPv4 and UDP, attach the correct PC IP
        sock_write = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock_write.bind((self.PC_IP, self.LISTEN_PORT))
        except:
            print("IP: {}".format(self.PC_IP))
        print(sock_write)
        sock_write.sendto(total,(self.VULCAN_IP, self.VULCAN_PORT))

        try:
            data = sock_write.recv(self.BUFFER_SIZE)
        except socket.timeout:
            if (i > 9):
                print ("Python Ethernet --> Error read_cdi_reg: No read packet received from board, quitting")
                print ("Waited for CDI response on")
                print (sock_write.getsockname())
                sock_write.close()
                return None
            else:
                print (f"Python Ethernet --> Didn't get a readback response for {hex(reg)}, trying again...")

        print(data)
        sock_write.close()

        #print ("Sent FEMB data from")
        #print (sock_write.getsockname())
        sock_write.close()
        #print ("Python Ethernet --> Write: reg=%x,value=%x"%(reg,data))
        #time.sleep(self.wait_time)

if __name__ == "__main__":
    e = VULCAN_ETHERNET()
    e.write_test()
