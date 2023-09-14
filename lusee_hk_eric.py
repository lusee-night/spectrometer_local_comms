import matplotlib.pyplot as plt
import os, time, sys, socket

#from lusee_common import LuSEE_COMMON
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

        #Device addresses for chips on the DB44 adapter board
        #https://www.nxp.com/docs/en/data-sheet/PCAL6416A.pdf
        self.hk_mux_dev = 0x20
        #https://www.ti.com/lit/ds/symlink/adc128d818.pdf
        self.hk_adc_dev = 0x1D

    def init_i2c_mux(self):
        #Sets all Port 0 pins to be outputs
        self.write_i2c(self.hk_mux_dev, 0x2, 0x6, 0x0)

    def reset_i2c_adc(self):
        #Sets to a reset state
        self.write_i2c(self.hk_adc_dev, 0x1, 0x0, 0x80)

    def init_i2c_adc(self):
        #Long sequence copied from Jack's Labview
        self.reset_i2c_adc()
        #Disables channels 1,3,5 and 6, which are unused
        self.write_i2c(self.hk_adc_dev, 0x1, 0x8, 0x6A)
        #Sets continuous conversion mode, rather than low-power
        self.write_i2c(self.hk_adc_dev, 0x1, 0x7, 0x01)
        #Uses internal VREF and sets to ADC Mode 0, each channel is the direct input with temperature monitoring
        self.write_i2c(self.hk_adc_dev, 0x1, 0xB, 0x00)

    def write_i2c_mux(self, val):
        #Val is simply the 8 bit output of Port 0, bit 0 is P0_0 and so on
        self.write_i2c(self.hk_mux_dev, 0x2, 0x2, val)
        resp = self.read_i2c(self.hk_mux_dev, 0x2, 0x2)
        if (resp == val):
            print(f"I2C mux written to {resp:x}")
            return 0
        else:
            print(f"Error: I2C mux was supposed to be written to {val:x}, but was read back as {resp:x}")
            return 1

    def check_i2c_status(self):
        while True:
            val=self.connection.read_reg(self.i2c_status)
            if (((val>>31)&0x1)==1):
                print ('LuSEE_HK --> Core busy')
                time.sleep (1.01)
            # elif (((val>>30)&0x1)==1):
            #     print ('LuSEE_HK --> Device Unavailable')
            #     time.sleep (1.01)
            else:
                break

    def write_i2c(self, dev_address, num_bytes, i2c_address, i2c_data):
        #Make sure I2C state machine is idle
        self.check_i2c_status()

        #Prepare write operation with all parameters
        value = (dev_address << 16) + num_bytes
        self.connection.write_reg(self.i2c_control, value)
        self.connection.write_reg(self.i2c_address, i2c_address)
        self.connection.write_reg(self.i2c_data, i2c_data)

        #Start write operation
        wdata = value | (1<<30)
        self.connection.write_reg(self.i2c_control, wdata)
        #Stop write operation
        self.connection.write_reg(self.i2c_control, value)

    def read_i2c(self, dev_address, num_bytes, i2c_address):
        #Make sure I2C state machine is idle
        self.check_i2c_status()
        #Mux chip requires this first
        self.write_i2c(dev_address, 0x0, i2c_address, 0x0)
        self.check_i2c_status()

        #Prepare write operation
        value = (dev_address << 16) + num_bytes
        self.connection.write_reg(self.i2c_control, value)
        self.connection.write_reg(self.i2c_address, i2c_address)

        #Start read operation
        rdata = value | (1<<31)
        self.connection.write_reg(self.i2c_control, rdata)
        #Stop read operation
        self.connection.write_reg(self.i2c_control, value)
        #FPGA top 2 bytes are other info
        resp = self.connection.read_reg(self.i2c_status)
        return resp & 0xFFFF

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
        part1 = val & 0xFF
        total = ((val & 0xFF) << 8) + (val >> 8)
        #0.000625
        return (total * 0.805644)/16

    def read_hk_data(self):
        #Do a single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x1, 0x9, 0x01)
        time.sleep(0.025)
        #Turn off single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x0, 0x9, 0x00)

        adc_ch0 = self.read_i2c(self.hk_adc_dev, 0x2, 0x20)
        adc_ch4 = self.read_i2c(self.hk_adc_dev, 0x2, 0x24)
        temp = self.read_i2c(self.hk_adc_dev, 0x2, 0x27)

        return self.convert_adc(adc_ch0), self.convert_adc(adc_ch4), self.convert_adc(temp)

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

    hk.init_i2c_mux()
    hk.write_i2c_mux(0x0001)

    adc0, adc4, temp = hk.read_hk_data()
    print(f"ADC0 response is {adc0}")
    print(f"ADC4 response is {adc4}")
    print(f"Temp response is {temp}")
