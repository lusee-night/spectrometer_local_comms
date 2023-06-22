import serial
from serial.tools import list_ports
import time
import os,sys
import struct
import csv
import matplotlib.pyplot as plt

class LuSEE_UART:
    def __init__(self):
        #If you're not receiving the large packets, run:
        #sudo ifconfig <device name> mtu 9000
        self.port = None #None will automatically scan for Flashpro
        self.baud = 115200
        self.timeout_reg = 0.01 #In seconds
        self.timeout_data = 2 #In seconds
        self.parity = serial.PARITY_ODD

        self.header = bytes.fromhex("DEAD")
        self.write = bytes.fromhex("00")
        self.read = bytes.fromhex("01")
        self.blank_data = bytes.fromhex("00000000")
        self.footer = bytes.fromhex("BEEF")

        self.rw_tries = 10
        self.resp_bytes = 100
        self.rawbytes = 0x1FFF
        self.num_packets = 1

        #Goes by power of 2. So avg of 7 is 2^7, or 128 averages
        self.avg_main = 12
        self.avg_notch = 6
        #How many bits to shift up when taking product of two 32 bit numbers
        self.mult_array = 0x1F
        self.notch_en = 0x1
        self.weight_fold_shift = 0xD

        if (self.port == None):
            self.get_connections()
        #self.ser = serial.Serial(port=port, baudrate=baud, parity=parity, timeout=timeout)

    def get_connections(self):
        ports = list_ports.comports()
        flashpro = None
        if (len(ports) == 0):
            raise serial.SerialException("No USB connection found: Make sure FPGA is plugged into the computer!")
        else:
            for i in ports:
                print(i.manufacturer)
                if (i.manufacturer == "Microsemi"):
                    flashpro = i
                    break
        if (flashpro == None):
            raise serial.SerialException("No Microsemi Flashpro found: Make sure FPGA is plugged into the computer!")

        self.port = flashpro.device
        print(f"Found {flashpro.manufacturer} {flashpro.product}")
        print(f"Using Port {self.port}")

    def connect_usb(self, timeout=1):
        self.connection = serial.Serial(port=self.port, baudrate=self.baud, parity=self.parity, timeout=timeout)
        self.connection.flush()
        print("Connection Opened")

    def write_reg(self, reg, val, confirm = False):
        if (reg < 0 or reg > 0xFFFF):
            print(f"Error: Register value {hex(reg)} out of range! Needs to be between 0x0 and 0xFFFF")
            return
        if (reg < 0 or reg > 0xFFFF):
            print(f"Error: Data value {hex(val)} out of range! Needs to be between 0x0 and 0xFFFFFFFF")
            return

        write_string = self.header + self.write + struct.pack(">H",reg) + struct.pack(">I",val) + self.footer
        i = 0
        while i < self.rw_tries:
            try:
                self.connection.write(write_string)
                if (confirm):
                    new_val = self.read_reg(reg)
                    if (new_val != val):
                        print(f"Checked value is {hex(new_val)}, should be {hex(val)}")
                        i = i+1
                        pass
                    else:
                        break
                else:
                    break
            except Exception as e:
                print(e)
                print(f"Write failed, retrying")
                i = i+1

            if (i == self.rw_tries - 2):
                print(f"ERROR: Failed to write {hex(val)} to register {hex(reg)}")
                return
        print(f"Wrote {hex(val)} to Register {hex(reg)}")
    def read_reg(self, reg):
        if (reg < 0 or reg > 0xFFFF):
            print(f"Error: Register value {hex(reg)} out of range! Needs to be between 0x0 and 0xFFFF")
            return

        read_string = self.header + self.read + struct.pack(">H",reg) + self.blank_data + self.footer

        i = 0
        self.connection.write(read_string)
        time.sleep(0.25)
        while i < self.rw_tries:
            try:
                response = self.connection.read(self.resp_bytes)
                response_int = struct.unpack(">I", response)[0]
                break
            except Exception as e:
                print(e)
                print(f"Read failed, check this")
                try:
                    response_int = struct.unpack(">I", response[-4:])[0]
                    break
                except Exception as e:
                    print(f"Read failed, retrying")
                    i = i+1
                    self.connection.write(read_string)

            if (i == self.rw_tries - 2):
                print(f"ERROR: Failed to read register {hex(reg)}")
                return

        #print(f"Read Register {hex(reg)} as {hex(response)}")
        return response_int

    def close(self):
        self.connection.flush()
        self.connection.close()
        print("Connection Closed")

    def reset_FPGA(self):
        luseeUart.write_reg(reg = 0x00, val = 0xFFFF, confirm = False)
        luseeUart.write_reg(reg = 0x00, val = 0x0000, confirm = True)

    def reset_ADC(self):
        luseeUart.write_reg(reg = 0x03, val = 0x0200, confirm = False)
        time.sleep(.025)
        luseeUart.write_reg(reg = 0x02, val = 0x0003, confirm = True)
        time.sleep(.025)
        luseeUart.write_reg(reg = 0x02, val = 0x0000, confirm = True)
        time.sleep(.025)

    def reset_fifo(self):
        luseeUart.write_reg(reg = 0x07, val = 0x0001, confirm = True)
        luseeUart.write_reg(reg = 0x07, val = 0x0000, confirm = True)

    def load_fifo(self):
        luseeUart.write_reg(reg = 0x04, val = 0x0002, confirm = True)
        time.sleep(.025)
        luseeUart.write_reg(reg = 0x04, val = 0x0000, confirm = True)

    def read_fifo(self):
        luseeUart.write_reg(reg = 0x05, val = self.rawbytes, confirm = True)
        luseeUart.write_reg(reg = 0x06, val = 0x0001, confirm = True)
        luseeUart.write_reg(reg = 0x04, val = 0x0001, confirm = False)

    def readout_fifo(self):
        response = bytes()
        for i in range(self.num_packets):
            print("Reading new data out")
            new_data = self.connection.read(size = 0xFFFF)
            if (len(new_data) == 0):
                print("Raw data buffer empty")
                break
            else:
                response += new_data
                print(f"Received packet #{i}")
        print(f"Received {len(response)} bytes")
        return response

    def initialize(self):
        self.reset_FPGA()
        self.reset_ADC()
        self.reset_fifo()

    def read_raw_data(self):
        self.load_fifo()
        self.read_fifo()
        raw_data = self.readout_fifo()
        return raw_data

    def format_data(self, data):
        #UART payload sometimes come in with incomplete data packets
        data_len = len(data)
        #Floor division gets number of full packets
        num_packets = data_len // 32
        #Gets the number of bytes for the full packet data
        full_size = num_packets * 32
        #Divide by 4 because each FPGA data packet is 4 bytes
        total_packets = int(full_size / 4)
        #Only look at the data up til the full size
        unpacked_data = struct.unpack(f"<{total_packets}i", data[0:full_size])
        ch1 = []
        ch2 = []
        for i in unpacked_data:
            #print("--")
            #print(hex(i))
            ch1_2s = (i & 0xFFFF0000) >> 16
            #print(hex(ch1_2s))
            #print(bin(ch1_2s))
            ch1_int = self.twos_comp(ch1_2s, 14)
            #print(ch1_int)
            ch1.append(ch1_int)
            ch2_2s = i & 0x0000FFFF
            #print(hex(ch2_2s))
            #print(bin(ch2_2s))
            ch2_int = self.twos_comp(ch2_2s, 14)
            #print(ch2_int)
            ch2.append(ch2_int)

        return ch1, ch2

    def plot(self, data):
        fig, ax = plt.subplots()

        title = "ch1"
        fig.suptitle(title, fontsize = 20)
        yaxis = "raw values"
        ax.set_ylabel(yaxis, fontsize=14)
        ax.set_xlabel('ticks', fontsize=14)
        ax.plot(data)
#        print(x)
#        print(y)
#        ax.set_xlim([0,1])

        plt.show()
        plot_path = os.path.join(os.getcwd(), "plots")
        if not (os.path.exists(plot_path)):
            os.makedirs(plot_path)

        fig.savefig (os.path.join(plot_path, "plot.jpg"))

    def save_data(self, data):
        data_path = os.path.join(os.getcwd(), "data")
        if not (os.path.exists(data_path)):
            os.makedirs(data_path)
        name = os.path.join(data_path, "data.csv")
        with open(name,'w',newline='') as f:
            cw = csv.writer(f)
            cw.writerows(map(lambda x: [x], data))

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
            val = val - (1 << bits)        # compute negative value
        return val                         # return positive value as is

    def format_pfb_data(self, data):
        data_len = len(data)
        #Divide by 4 because each FPGA data packet is 4 bytes
        total_packets = int(data_len / 4)
        unpacked_data = list(struct.unpack(f"<{total_packets}i", data))
        unpacked_data.reverse()
        return unpacked_data

    def setup_params(self):
        luseeUart.write_reg(reg = 0x0B, val = self.avg_main, confirm = True)
        luseeUart.write_reg(reg = 0x08, val = self.avg_notch, confirm = True)
        luseeUart.write_reg(reg = 0x14, val = self.mult_array, confirm = True)
        luseeUart.write_reg(reg = 0x17, val = self.mult_array, confirm = True)
        luseeUart.write_reg(reg = 0x13, val = self.notch_en, confirm = True)
        luseeUart.write_reg(reg = 0x12, val = self.weight_fold_shift, confirm = True)

    def read_pfb_data(self):
        luseeUart.write_reg(reg = 0x0E, val = 0x0000, confirm = True)
        luseeUart.write_reg(reg = 0x0A, val = 0x0332, confirm = True)
        luseeUart.write_reg(reg = 0x09, val = 0x0001, confirm = True)
        luseeUart.write_reg(reg = 0x04, val = 0x0006, confirm = True)
        luseeUart.write_reg(reg = 0x06, val = 0x0003, confirm = True)
        #time.sleep(1)
        luseeUart.close()
        luseeUart.connect_usb(timeout = self.timeout_data)
        luseeUart.write_reg(reg = 0x04, val = 0x0001, confirm = False)

        raw_pfb_data = self.readout_fifo()
        pfb_data = self.format_pfb_data(raw_pfb_data)
        return pfb_data

    def plot_pfb(self, data):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data)):
            x.append(i / 2048 * 100 / 2)
        notch_word = "off" if self.notch_en==0x0 else "on"
        title = f"pfb_notch_{notch_word}_Navg_{2**self.avg_main}_Nnotch_{2**self.avg_notch}"
        fig.suptitle(title, fontsize = 20)
        yaxis = "counts"
        ax.set_ylabel(yaxis, fontsize=14)
        ax.set_yscale('log')
        ax.set_xlabel('MHz', fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(x, data)
#        print(x)
#        print(data)
#        print(x)
#        print(y)
#        ax.set_xlim([0,8])

        plt.show()
        plot_path = os.path.join(os.getcwd(), "plots")
        if not (os.path.exists(plot_path)):
            os.makedirs(plot_path)

        fig.savefig (os.path.join(plot_path, f"{title}.jpg"))

if __name__ == "__main__":
    arg = sys.argv[1]

    luseeUart = LuSEE_UART()
    luseeUart.connect_usb(timeout = luseeUart.timeout_reg)
    luseeUart.initialize()
    time.sleep(1)
    if (arg == "raw"):
        raw_data = luseeUart.read_raw_data()
        luseeUart.close()
        ch1, ch2 = luseeUart.format_data(raw_data)
        luseeUart.plot(ch1)
        luseeUart.save_data(ch1)
    elif(arg == "reg"):
     for i in range(1,20,1):
         print(f"Register {i} is {luseeUart.read_reg(i)}")
    else:
        luseeUart.setup_params()
        pfb_output = luseeUart.read_pfb_data()
        luseeUart.plot_pfb(pfb_output)
        luseeUart.save_data(pfb_output)
        luseeUart.close()
