import matplotlib.pyplot as plt
import os, time, sys, socket, math
import numpy as np
import logging
import logging.config

#from lusee_common import LuSEE_COMMON
from utils import LuSEE_COMMS
from utils import LuSEE_ETHERNET

class LuSEE_HK_EMULATOR:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        self.comm        = LuSEE_COMMS()
        self.connection  = LuSEE_ETHERNET()
        self.tvs_cntl    = 0x004
        self.tvs_1_0v    = 0x005
        self.tvs_1_8v    = 0x006
        self.tvs_2_5v    = 0x007
        self.tvs_temp    = 0x008

        self.mux         = 0x06

        self.i2c         = 20
        self.i2c_address = 21
        self.i2c_din     = 22
        self.i2c_dout_status = 23

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

        #Device address AD7998BRUZ-1REEL
        #https://www.analog.com/media/en/technical-documentation/data-sheets/AD7997_7998.pdf
        self.hk_adc_dev = 0x23

    def write_i2c_mux(self, val):
        #Val is simply the 8 bit output of Port 0, bit 0 is P0_0 and so on
        self.connection.write_cdi_reg(self.mux, val, self.connection.PORT_WREG)
        time.sleep(0.1)
        return 0

    def check_i2c_status(self):
        time.sleep(0.1)
        val=self.connection.read_cdi_reg(self.i2c_dout_status)["data"]
        if (not (val & 0x40000000)):
            self.logger.info(f'ADC not detected: {hex(val)}')
        self.logger.info(f'ADC detected: {hex(val)}')
        return True

    def write_i2c(self, dev_address, num_bytes, i2c_address, i2c_data):
        #Prepare write operation with all parameters
        reg20_val = (dev_address << 16) + num_bytes
        self.connection.write_cdi_reg(self.i2c, reg20_val, self.connection.PORT_WREG)
        self.connection.write_cdi_reg(self.i2c_address, i2c_address, self.connection.PORT_WREG)
        self.connection.write_cdi_reg(self.i2c_din, i2c_data, self.connection.PORT_WREG)

        #Start write operation
        self.connection.write_cdi_reg(self.i2c, 0x40000000 + reg20_val, self.connection.PORT_WREG)
        time.sleep(0.1)
        #Stop write operation
        self.connection.write_cdi_reg(self.i2c, reg20_val, self.connection.PORT_WREG)
        time.sleep(0.1)

    def read_i2c(self, dev_address, num_bytes, i2c_address):
        #Prepare write operation
        reg20_val = (dev_address << 16) + num_bytes
        self.connection.write_cdi_reg(self.i2c, reg20_val, self.connection.PORT_WREG)
        self.connection.write_cdi_reg(self.i2c_address, i2c_address, self.connection.PORT_WREG)
        time.sleep(0.1)

        #Start read operation
        self.connection.write_cdi_reg(self.i2c, 0x80000000 + reg20_val, self.connection.PORT_WREG)
        time.sleep(0.1)
        #Stop read operation
        self.connection.write_cdi_reg(self.i2c, reg20_val, self.connection.PORT_WREG)

        time.sleep(0.1)

        #FPGA bottom 2 bytes are the actual data
        return self.connection.read_cdi_reg(self.i2c_dout_status)["data"] & 0xFFFF

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
            self.logger.error(f"Only pass 16 bit values into this voltage function. You passed {hex(val)}")
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
            self.logger.error(f"Only pass 16 bit values into this temp function. You passed {hex(val)}")
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
        total = ((val & 0xFF) << 8) + (val >> 8)
        #Bits is 4096
        #Don't know why we divide by 16, for bit shift?
        return (total * (3.3/4096))

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
        self.logger.debug(f"Input voltage was {val1} and thermistor resistance was {r_th} and ratio is {ratio}")
        if (ratio > self.ratio_max):
            self.logger.error(f"Thermistor ratio is {ratio} which is higher than the datasheet maximum")
            return 0, 0
        coefficients = None
        for key, val in self.temp_coefficients.items():
            #self.logger.debug(f"coefficients are {key}, {val}")
            if (ratio > key):
                coefficients = val
                break
        if (coefficients == None):
            self.logger.error(f"Thermistor ratio is {ratio} which is lower than the datasheet minimum")
            return 0, 0

        #self.logger.debug(f"coefficients are {coefficients}")
        a = coefficients[0]
        b = coefficients[1]
        c = coefficients[2]
        d = coefficients[3]

        term = a + b * (np.log(ratio)) + c * (np.log(ratio) ** 2) + d * (np.log(ratio) ** 3)
        self.logger.info(f"Temperature calculated as {1/term}")

        return int(1/term), 0

    def read_hk_data(self):
        #Device address is 0x23, num_bytes is 0, address and data is 0x80 to
        #First device address and num bytes to register 20, adress
        #Then read 0x23, num_bytes 2, address is 0 or don't change, toggle reg20 MSB, wait 1 ms, read reg23. Which is 32 bit value. the 16 bit LSB is the data, but byteswapped, and upper nibble is channel so mask it
        #scale is 3.3/4096

        #Set ADC to read channel 0
        self.write_i2c(self.hk_adc_dev, 0x0, 0x80, 0x0)
        #Make sure we have the right device address
        time.sleep(0.1)
        if (not self.check_i2c_status()):
            return 0,0,0
        time.sleep(0.1)
        adc_ch0 = self.read_i2c(self.hk_adc_dev, 0x2, 0x80)

        return self.convert_adc(adc_ch0), 0, 0

if __name__ == "__main__":
    #arg = sys.argv[1]
    hk = LuSEE_HK()
    #hk.comm.setup_adc()
    #hk.comm.write_adc_reg(adc_id = 1, reg = 0x45, data = 0x84)
    #hk.logger.info ('sleeping')
    #time.sleep(10)

    hk.setup_fpga_internal()
    bank1v, bank1_8v, bank2_5v = hk.read_fpga_voltage()
    hk.logger.info(f"1V Bank Voltage is {bank1v} mV")
    hk.logger.info(f"1.8V Bank Voltage is {bank1_8v} mV")
    hk.logger.info(f"2.5V Bank Voltage is {bank2_5v} mV")

    temp = hk.read_fpga_temp()
    hk.logger.info(f"Temperature is {temp} C")

    hk.init_i2c_mux()
    hk.write_i2c_mux(0x0001)

    adc0, adc4, temp = hk.read_hk_data()
    hk.logger.info(f"ADC0 response is {adc0}")
    hk.logger.info(f"ADC4 response is {adc4}")
    hk.logger.info(f"Temp response is {temp}")
