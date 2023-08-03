import matplotlib.pyplot as plt
import os, time, sys, socket

from lusee_common import LuSEE_COMMON
from lusee_comm import LuSEE_COMMS
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_HK:
    def __init__(self):
        #self.lusee = LuSEE_COMMON()
        self.comm = LuSEE_COMMS()
        self.connection = LuSEE_ETHERNET()
        self.fpga_read   = 0x21
        self.fpga_bank1  = 0x22
        self.fpga_bank2  = 0x23
        self.i2c_control = 0x24
        self.i2c_address = 0x25
        self.i2c_data    = 0x26
        self.i2c_status  = 0x27

        self.hk_adc_conv    = 8.05644e-4

    # initialize I2C
    def init_i2c(self):
        self.write_i2c(0x20, 0x2, 0x6, 0x0)
        
    def write_i2c_mux(self, val):
        self.write_i2c(0x20, 0x2, 0x2, val)
        resp = self.read_i2c(0x20, 0x2, 0x2) & 0xFFFF
        if (resp == val):
            print(f"I2C mux written to {resp:x}")
        else:
            print(f"Error: I2C mux was supposed to be written to {val:x}, but was read back as {resp:x}")
        
    def check_i2c_status(self):
        while True:
            val=self.connection.read_reg(self.i2c_status)
            if (((val>>31)&0x1)==1):
                print ('Core busy')
                time.sleep (0.001)
            elif (((val>>30)&0x0)==1):
                print ('Device Unavailable')
                time.sleep (0.001)
            else:
                break

    # write I2C register
    def write_i2c(self, dev_address, num_bytes, i2c_address, i2c_data):
        self.check_i2c_status()

        # prepare write operation
        value = (dev_address << 16) + num_bytes
        self.connection.write_reg(self.i2c_control, value)
        # write i2c address
        self.connection.write_reg(self.i2c_address, i2c_address)
        # write i2c data
        self.connection.write_reg(self.i2c_data, i2c_data)
        
        # start write operation
        wdata = value | (1<<30)
        self.connection.write_reg(self.i2c_control, wdata)
        self.connection.write_reg(self.i2c_control, value)
        
    def read_i2c(self, dev_address, num_bytes, i2c_address):
        self.check_i2c_status()
        self.write_i2c(dev_address, 0x0, i2c_address, 0x0)
        self.check_i2c_status()
        
        # prepare write operation
        value = (dev_address << 16) + num_bytes
        self.connection.write_reg(self.i2c_control, value)
        # write i2c address
        self.connection.write_reg(self.i2c_address, i2c_address)
        
        # start write operation
        wdata = value | (1<<31)
        self.connection.write_reg(self.i2c_control, wdata)
        self.connection.write_reg(self.i2c_control, value)
        resp = self.connection.read_reg(self.i2c_status)
        return resp
        
    def setup_fpga_internal(self):
    	self.connection.write_reg(self.fpga_read, 0xFF)
    
    def read_fpga_voltage(self):
    	result1 = self.connection.read_reg(self.fpga_bank1)
    	result2 = self.connection.read_reg(self.fpga_bank2)
    	
    	bank1v = self.convert_volt(result1 >> 16)
    	bank1_8v = self.convert_volt(result1 & 0xFFFF)
    	bank2_5v = self.convert_volt(result2 >> 16)
    	
    	return bank1v, bank1_8v, bank2_5v
    	
    def read_fpga_temp(self):
        result2 = self.connection.read_reg(self.fpga_bank2)
        temp = self.convert_temp(result2 & 0xFFFF)
        
        return temp
    	
    def convert_volt(self, val):
    	if (val > 0xFFFF):
    	    print(f"Error: Only pass 16 bit values into this voltage function. You passed {hex(val)}")
    	    return 0
    	else:
    	    sign = val >> 15
    	    whole = (val & 0x7FFF) >> 3
    	    fraction = val & 0x7
    	    number = whole + (fraction * 0.125)
    	    if (sign):
    	        number = number * -1
    	    return number
    	    
    def convert_temp(self, val):
    	if (val > 0xFFFF):
    	    print(f"Error: Only pass 16 bit values into this temp function. You passed {hex(val)}")
    	    return 0
    	else:
    	    sign = val >> 15
    	    whole = (val & 0x7FFF) >> 4
    	    fraction = val & 0xF
    	    number = whole + (fraction * 0.0625)
    	    if (sign):
    	        number = number * -1
    	    return number
    	    
    def convert_adc(self, val):
        return (val * 0.805644)/16

    def convert_adc2(self, val):
        part1 = val & 0xFF
        part2 = val >> 8
        total = (part1 << 8) + part2
        return (total * 0.805644)/16
    	    
    # read HK data
    def read_hk_data(self):
        #Long sequence copied from Jack's Labview
        self.write_i2c(0x1D, 0x1, 0x8, 0x60)
        self.write_i2c(0x1D, 0x1, 0x7, 0x01)
        self.write_i2c(0x1D, 0x1, 0xB, 0x01)
        self.write_i2c(0x1D, 0x1, 0x0, 0x08)
        self.write_i2c(0x1D, 0x1, 0x9, 0x01)
        time.sleep(0.025)
        self.write_i2c(0x1D, 0x0, 0x9, 0x00)
        
        adc0 = self.read_i2c(0x1D, 0x2, 0x20) & 0xFFFF
        adc4 = self.read_i2c(0x1D, 0x2, 0x24) & 0xFFFF
        temp = self.read_i2c(0x1D, 0x2, 0x27) & 0xFFFF
        
        return self.convert_adc(adc0), self.convert_adc(adc4), self.convert_adc(temp)

if __name__ == "__main__":
    #arg = sys.argv[1]
    hk = LuSEE_HK()
    #hk.comm.setup_adc()
    #hk.comm.write_adc_reg(adc_id = 1, reg = 0x45, data = 0x84)
    #print ('sleeping')
    #time.sleep(10)
    
    hk.setup_fpga_internal()
    bank1v, bank1_8v, bank2_5v = hk.read_fpga_voltage()
    print(f"1V Bank Voltage is {bank1v} mV")
    print(f"1.8V Bank Voltage is {bank1_8v} mV")
    print(f"2.5V Bank Voltage is {bank2_5v} mV")
    
    temp = hk.read_fpga_temp()
    print(f"Temperature is {temp} C")
    
    hk.init_i2c()
    hk.write_i2c_mux(0x0001)
    
    adc0, adc4, temp = hk.read_hk_data()
    print(f"ADC0 response is {adc0}")
    print(f"ADC4 response is {adc4}")
    print(f"Temp response is {temp}")
