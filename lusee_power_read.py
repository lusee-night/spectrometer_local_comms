import time
import sys
import pandas as pd

from lusee_hk_eric import LuSEE_HK
from lusee_comm import LuSEE_COMMS
from lusee_measure import LuSEE_MEASURE

#Current monitor
#https://www.ti.com/lit/ds/symlink/ina901-sp.pdf

class POWER_TEST:
    def __init__(self, name, reg1_val, reg2_val, reg3_val):
        self.name = name
        self.reg1_val = reg1_val
        self.reg2_val = reg2_val
        self.reg3_val = reg3_val

class LuSEE_POWER:
    def __init__(self, name):
        self.hk = LuSEE_HK()
        self.comm = LuSEE_COMMS()
        self.name = name

        self.ina_gain = 20
        self.correct_m = 1.07
        self.correct_b = 0.00872

        self.r75 = 1     #5VP
        self.r74 = 1     #5VN
        self.r73 = 0.390 #1.8VA
        self.r72 = 0.390 #1.8VAD

        self.r160 = 0.01 #1.0V
        self.r161 = 0.01 #1.5V
        self.r172 = 0.01 #1.8V
        self.r175 = 0.01 #2.5V
        self.r176 = 0.01 #3.3V

        self.delay = 5

        self.SPE_disable     = 40
        self.weight_streamer = 0b1
        self.weight_fold1    = 0b10
        self.weight_fold2    = 0b100
        self.weight_fold3    = 0b1000
        self.weight_fold4    = 0b10000
        self.sfft_12         = 0b100000
        self.sfft_34         = 0b1000000
        self.deinterlace_12  = 0b10000000
        self.deinterlace_34  = 0b100000000

        self.SPE_notch_avg_disable = 40
        self.notch_avg_1_R   = 0x010000
        self.notch_avg_1_I   = 0x020000
        self.notch_avg_2_R   = 0x040000
        self.notch_avg_2_I   = 0x080000
        self.notch_avg_3_R   = 0x100000
        self.notch_avg_3_I   = 0x200000
        self.notch_avg_4_R   = 0x400000
        self.notch_avg_4_I   = 0x800000

        self.SPE_avg_disable = 41
        self.avg_A1          = 0x0001
        self.avg_A2          = 0x0002
        self.avg_A3          = 0x0004
        self.avg_A4          = 0x0008
        self.avg_X12R        = 0x0010
        self.avg_X12I        = 0x0020
        self.avg_X13R        = 0x0040
        self.avg_X13I        = 0x0080
        self.avg_X14R        = 0x0100
        self.avg_X14I        = 0x0200
        self.avg_X23R        = 0x0400
        self.avg_X23I        = 0x0800
        self.avg_X24R        = 0x1000
        self.avg_X24I        = 0x2000
        self.avg_X34R        = 0x4000
        self.avg_X34I        = 0x8000

        self.corr_disable    = 42
        self.corr_notch_A1   = 0x0001
        self.corr_notch_A2   = 0x0002
        self.corr_notch_A3   = 0x0004
        self.corr_notch_A4   = 0x0008
        self.corr_notch_X12R = 0x0010
        self.corr_notch_X12I = 0x0020
        self.corr_notch_X13R = 0x0040
        self.corr_notch_X13I = 0x0080
        self.corr_notch_X14R = 0x0100
        self.corr_notch_X14I = 0x0200
        self.corr_notch_X23R = 0x0400
        self.corr_notch_X23I = 0x0800
        self.corr_notch_X24R = 0x1000
        self.corr_notch_X24I = 0x2000
        self.corr_notch_X34R = 0x4000
        self.corr_notch_X34I = 0x8000

        self.corr_A1         = 0x00010000
        self.corr_A2         = 0x00020000
        self.corr_A3         = 0x00040000
        self.corr_A4         = 0x00080000
        self.corr_X12R       = 0x00100000
        self.corr_X12I       = 0x00200000
        self.corr_X13R       = 0x00400000
        self.corr_X13I       = 0x00800000
        self.corr_X14R       = 0x01000000
        self.corr_X14I       = 0x02000000
        self.corr_X23R       = 0x04000000
        self.corr_X23I       = 0x08000000
        self.corr_X24R       = 0x10000000
        self.corr_X24I       = 0x20000000
        self.corr_X34R       = 0x40000000
        self.corr_X34I       = 0x80000000

        self.tests = []
        self.tests.append(POWER_TEST(name = "Everything on", reg1_val = 0x0, reg2_val = 0x0, reg3_val = 0x0))
        self.tests.append(POWER_TEST(name = "Final averager off", reg1_val = 0x0, reg2_val = 0xFFFF, reg3_val = 0x0))
        self.tests.append(POWER_TEST(name = "Notch correlator off", reg1_val = 0x0, reg2_val = 0xFFFF, reg3_val = 0xFFFF))
        self.tests.append(POWER_TEST(name = "Main correlator off", reg1_val = 0x0, reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))
        self.tests.append(POWER_TEST(name = "Notch averager off", reg1_val = 0xFF0000, reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))
        self.tests.append(POWER_TEST(name = "Deinterlacer off",
                                reg1_val = 0xFF0000 + self.deinterlace_34 + self.deinterlace_12, reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))
        self.tests.append(POWER_TEST(name = "FFT off",
                                reg1_val = 0xFF0000 + self.deinterlace_34 + self.deinterlace_12 + self.sfft_12 + self.sfft_34,
                                reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))
        self.tests.append(POWER_TEST(name = "Weight Fold off",
                                reg1_val = 0xFF0000 + self.deinterlace_34 + self.deinterlace_12 + self.sfft_12 + self.sfft_34 + self.weight_fold1 + self.weight_fold2 + self.weight_fold3 + self.weight_fold4,
                                reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))

        self.tests.append(POWER_TEST(name = "Weight Streamer off",
                                reg1_val = 0xFF0000 + self.deinterlace_34 + self.deinterlace_12 + self.sfft_12 + self.sfft_34 + self.weight_fold1 + self.weight_fold2 + self.weight_fold3 + self.weight_fold4 + self.weight_streamer,
                                reg2_val = 0xFFFF, reg3_val = 0xFFFFFFFF))

        self.configurations = {"+5V Output Voltage":0,
                               "+5V Output Current":1,
                               "-5V Output Voltage":2,
                               "-5V Output Current":3,
                               #
                               "1.8VA Output Voltage":4,
                               "1.8VA Output Current":5,
                               "1.8VAD Output Voltage":6,
                               "1.8VAD Output Current":7,

                               "3.3VD Output Voltage":0xA,
                               "3.3VD Output Current":0xB,
                               "2.5VD Output Voltage":0xC,
                               "2.5VD Output Current":0xD,

                               "1.8VD Output Voltage":0xE,
                               "1.8VD Output Current":0xF,
                               "1.5VD Output Voltage":0x10,
                               "1.5VD Output Current":0x11,
                               "1.0VD Output Voltage":0x12,
                               "1.0VD Output Current":0x13
                               }

        self.resistors      = {"+5V Output Current":1,
                               "-5V Output Current":1,

                               "1.8VA Output Current":0.390,
                               "1.8VAD Output Current":0.390,

                               "3.3VD Output Current":0.01,

                               "2.5VD Output Current":0.01,
                               "1.8VD Output Current":0.01,

                               "1.5VD Output Current":0.01,
                               "1.0VD Output Current":0.01
                               }

        self.no_correct    = ["3.3VD Output Current", "2.5VD Output Current", "1.8VD Output Current", "1.5VD Output Current"]

        self.initial_df = ["FPGA 1V", "FPGA 1.8V", "FPGA 2.5V", "FPGA Temp (Kelvin)"]
        key_list = list(self.configurations.keys())
        key_list_pwr = []
        for num,i in enumerate(key_list):
            key_list_pwr.append(i)
            if ((num % 2) != 0):
                key_list_pwr.append(f"Power")
        self.initial_df.extend(key_list_pwr)
        self.df = pd.DataFrame(self.initial_df, columns=[f"{self.name}"])

    def sequence(self):
        self.comm.reset()
        self.comm.set_chan(0, 0, 4, "low")

        self.comm.set_function("FFT1")
        self.comm.set_main_average(10)
        self.comm.set_weight_fold_shift(0xD)
        self.comm.set_pfb_delays(0x332)

        self.comm.set_notch_average(4)
        self.comm.notch_filter_on()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()

        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set these as well for each FFT you read out
        self.comm.set_index_array("A1", 0x1F, "main")
        self.comm.set_index_array("A1", 0x1F, "notch")

        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        print("Setting up internal FPGA")
        self.hk.setup_fpga_internal()
        print("Setting up I2C Mux")
        self.hk.init_i2c_mux()
        print("Setting up I2C ADC")
        self.hk.init_i2c_adc()

        print(f"Started the spectrometer, waiting {self.delay} seconds for power to stabilize")
        time.sleep(self.delay)

        print("Taking power data")
        for i in self.tests:
            self.prepare_test(i)
            self.power_sequence(i.name)

        # for i in self.df:
        #     print(i)
        #     print(self.df[i])
        #     print(type(self.df[i]))
        #     print(self.df[i][4])
        #     print(type(self.df[i][4]))
        #
        # v = None
        # i = None
        # p = None
        # for key,val in self.configurations.items():
        #     if ("Voltage" in key):
        #         v = (self.df[self.name][key])
        #     if ("Current" in key):
        #         i = (self.df[self.name][key])
        #         p = v * i

        # create a pandas.ExcelWriter object
        writer = pd.ExcelWriter(f"{self.name}.xlsx", engine='xlsxwriter')

        # write the data frame to Excel
        self.df.to_excel(writer, index=False, sheet_name='Sheet1')

        # get the XlsxWriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        # adjust the column widths based on the content
        for i, col in enumerate(self.df.columns):
            width = max(self.df[col].apply(lambda x: len(str(x))).max(), len(col))
            worksheet.set_column(i, i, width)

        # save the Excel file
        writer._save()

    def prepare_test(self, test):
        print(f"Preparing test {test.name}")
        self.comm.connection.write_reg(self.SPE_notch_avg_disable, test.reg1_val)
        self.comm.connection.write_reg(self.SPE_avg_disable, test.reg2_val)
        self.comm.connection.write_reg(self.corr_disable, test.reg3_val)
        print(f"Waiting {self.delay} seconds for power to stabilize")

    def power_sequence(self, name):
        print("Taking power data")
        bank1v, bank1_8v, bank2_5v = self.hk.read_fpga_voltage()
        fpga_temp = self.hk.read_fpga_temp()
        running_list = [bank1v, bank1_8v, bank2_5v, fpga_temp]
        print(f"1V is {bank1v}, 1.8V is {bank1_8v}, 2.5V is {bank2_5v}, temp is {fpga_temp}")
        results = []
        for key,val in self.configurations.items():
            print(key)
            resp = 1
            while (resp != 0):
                resp = self.hk.write_i2c_mux(val)
            adc0, adc4, temp = self.hk.read_hk_data()
            print(f"ADC0 is {adc0} and ADC4 {adc4}")
            if (key not in self.no_correct):
                adc0 = (self.correct_m * adc0) + self.correct_b
                adc4 = (self.correct_m * adc4) + self.correct_b
            print(f"Corrected ADC0 is {adc0} and ADC4 {adc4}")
            if "Current" in key:
                adc0, adc4 = self.convert_current(branch = key, val1 = adc0, val2 = adc4)
                p = round(adc0 * prev_adc0, 3)
            elif "+5V Output Voltage" in key:
                adc0 = adc0 * 5
                adc4 = adc4 * 5
            elif "-5V Output Voltage" in key:
                adc0 = adc0 * (4 + (1/6))
                adc4 = adc4 * (4 + (1/6))

            adc0 = round(adc0, 3)
            adc4 = round(adc4, 3)
            print(adc0, adc4)
            print("\n")
            prev_adc0 = adc0
            prev_adc4 = adc4
            if "Current" in key:
                running_list.extend([adc0, p])
            else:
                running_list.extend([adc0])

        self.df[f"{name}"] = running_list

    def convert_current(self, branch, val1, val2):
        adc0 = (val1/self.ina_gain) / (self.resistors[branch])
        adc4 = (val2/self.ina_gain) / (self.resistors[branch])
        return adc0, adc4

    def test_power(self):
        print("Testing power")
        self.comm.connection.write_reg(self.SPE_notch_avg_disable, 0xFFFFFFFF)
        self.comm.connection.write_reg(self.SPE_avg_disable, 0xFFFFFFFF)
        self.comm.connection.write_reg(self.corr_disable, 0xFFFFFFFF)
        self.comm.start_spectrometer()
        input("We good?")


    def test_function(self):
        self.comm.stop_spectrometer()
        print("Setting up internal FPGA")
        self.hk.setup_fpga_internal()
        print("Setting up I2C Mux")
        self.hk.init_i2c_mux()
        print("Setting up I2C ADC")
        self.hk.init_i2c_adc()

        for key,val in self.configurations.items():
            print(key)
            bank1v, bank1_8v, bank2_5v = self.hk.read_fpga_voltage()
            fpga_temp = self.hk.read_fpga_temp()
            print(f"1V is {bank1v}, 1.8V is {bank1_8v}, 2.5V is {bank2_5v}, temp is {fpga_temp}")

            resp = self.hk.write_i2c_mux(val)
            adc0, adc4, temp = self.hk.read_hk_data()
            print(f"ADC0 is {adc0} and ADC4 {adc4}")
            if (key not in self.no_correct):
                adc0 = (self.correct_m * adc0) + self.correct_b
                adc4 = (self.correct_m * adc4) + self.correct_b
            print(f"Corrected ADC0 is {adc0} and ADC4 {adc4}")
            if "Current" in key:
                adc0, adc4 = self.convert_current(branch = key, val1 = adc0, val2 = adc4)
            elif "+5V Output Voltage" in key:
                adc0 = adc0 * 5
                adc4 = adc4 * 5
            elif "-5V Output Voltage" in key:
                adc0 = adc0 * (4 + (1/6))
                adc4 = adc4 * (4 + (1/6))

            print(adc0, adc4)
            print("\n")

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        name = sys.argv[1]
    else:
        name = "test"

    measure = LuSEE_MEASURE()
    measure.comm.connection.write_cdi_reg(5, 69)
    resp = measure.comm.connection.read_cdi_reg(5)
    if (resp == 69):
        print("[TEST]", "Communication to DCB Emulator is ok")
    else:
        sys.exit("[TEST] -> Communication to DCB Emulator is not ok")

    measure.comm.connection.write_reg(5, 69)
    resp = measure.comm.connection.read_reg(5)
    if (resp == 69):
        print("[TEST]", "Communication to Spectrometer Board is ok")
    else:
        sys.exit("[TEST] -> Communication to Spectrometer Board is not ok")

    power = LuSEE_POWER(name)
    power.sequence()
    #power.test_power()
    #power.test_function()
