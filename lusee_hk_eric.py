import matplotlib.pyplot as plt
import os, time, sys, socket, math
import numpy as np

#from lusee_common import LuSEE_COMMON
from lusee_comm import LuSEE_COMMS
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_HK:
    def __init__(self):
        self.version = 1.01
        #self.lusee = LuSEE_COMMON()
        self.comm        = LuSEE_COMMS()
        self.connection  = LuSEE_ETHERNET()
        self.tvs_cntl    = 0x004
        self.tvs_1_0v    = 0x005
        self.tvs_1_8v    = 0x006
        self.tvs_2_5v    = 0x007
        self.tvs_temp    = 0x008

        self.i2c_control = 0x24
        self.i2c_address = 0x25
        self.i2c_data    = 0x26
        self.i2c_status  = 0x27

        #Current monitor
        #https://www.ti.com/lit/ds/symlink/ina901-sp.pdf
        #Gain of current monitor
        self.ina_gain = 20

        #Details for thermistor measurements
        #According to schematics, the part is MC65F103A, Material Type F with R25 = 10000
        #https://www.amphenol-sensors.com/hubfs/Documents/AAS-920-306C-NTC-Type-65-Series-031314-web.pdf
        #https://www.amphenol-sensors.com/hubfs/Documents/AAS-913-318C-Temperature-resistance-curves-071816-web.pdf
        self.thermistor_res = 10000
        self.thermistor_voltage = 1.8
        self.t_r25 = 10000
        self.ratio_max = 68.6
        self.temp_coefficients = {3.274: [3.3538646E-03, 2.5654090E-04, 1.9243889E-06, 1.0969244E-07],
                                  0.36036: [3.3540154E-03, 2.5627725E-04, 2.0829210E-06, 7.3003206E-08],
                                  0.06831: [3.3539264E-03, 2.5609446E-04, 1.9621987E-06, 4.6045930E-08],
                                  0.01872: [3.3368620E-03, 2.4057263E-04, -2.6687093E-06, -4.0719355E-07]}

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
        self.write_i2c(self.hk_adc_dev, 0x1, 0xB, 0x01)

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
        self.connection.write_reg(self.tvs_cntl, 0xFF)

    def read_fpga_voltage(self):
        bank1v = self.convert_volt(self.connection.read_reg(self.tvs_1_0v))
        bank1_8v = self.convert_volt(self.connection.read_reg(self.tvs_1_8v))
        bank2_5v = self.convert_volt(self.connection.read_reg(self.tvs_2_5v))
        return bank1v, bank1_8v, bank2_5v

    def read_fpga_temp(self):
        return self.convert_temp(self.connection.read_reg(self.tvs_temp))

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
        #Measured VREF is 3.323 V
        #Bits is 4096
        #Don't know why we divide by 16, for bit shift?
        return (total * (3.323/4096))/16

    #The INA901 reads the voltage across a sense resistor to measure the current
    #It has an internal gain of 20V/V, so first we get the actual voltage across the resistor
    #Then we use the value of the resistor to get the actual current
    def convert_current(self, resistance, val1, val2):
        adc0 = (val1/self.ina_gain) / resistance
        adc4 = (val2/self.ina_gain) / resistance
        return adc0, adc4

    #Convert the ADC voltage reading into a temperature
    def convert_thermistor(self, val1, val2):
        #Thermistor is read through a voltage divider, get the thermistor resistance
        r_th = self.thermistor_res * (1/((self.thermistor_voltage/val1) - 1))
        ratio = r_th/self.t_r25
        #print(f"Input voltage was {val1} and thermistor resistance was {r_th} and ratio is {ratio}")
        if (ratio > self.ratio_max):
            print(f"Error: Thermistor ratio is {ratio} which is higher than the datasheet maximum")
            return 0, 0
        coefficients = None
        for key, val in self.temp_coefficients.items():
            #print(f"coefficients are {key}, {val}")
            if (ratio > key):
                coefficients = val
                break
        if (coefficients == None):
            print(f"Error: Thermistor ratio is {ratio} which is lower than the datasheet minimum")
            return 0, 0

        #print(f"coefficients are {coefficients}")
        a = coefficients[0]
        b = coefficients[1]
        c = coefficients[2]
        d = coefficients[3]

        term = a + b * (np.log(ratio)) + c * (np.log(ratio) ** 2) + d * (np.log(ratio) ** 3)
        print(f"Temperature calculated as {1/term}")

        return int(1/term), 0

    def read_hk_data(self):
        #Do a single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x1, 0x9, 0x01)
        time.sleep(0.025)
        #Turn off single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x0, 0x9, 0x00)

        adc_ch0 = self.read_i2c(self.hk_adc_dev, 0x2, 0x20)

        #Do a single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x1, 0x9, 0x01)
        time.sleep(0.025)
        #Turn off single shot conversion
        self.write_i2c(self.hk_adc_dev, 0x0, 0x9, 0x00)

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
