import time
import sys
import pandas as pd

from lusee_hk_eric import LuSEE_HK
from lusee_comm import LuSEE_COMMS
from lusee_measure import LuSEE_MEASURE

#A class for each test so we can easily loop through them pick out these properties
class POWER_TEST:
    def __init__(self, name, uc_disable, adc_disable, spe_enable):
        self.name = name
        self.uc_disable = uc_disable
        self.adc_disable = adc_disable
        self.spe_enable = spe_enable

class LuSEE_POWER:
    def __init__(self, name):
        self.version = 1.01
        self.hk = LuSEE_HK()
        self.measure = LuSEE_MEASURE()
        self.name = name
        
        #Input voltages on cable, used for LDO power consumption
        self.cable_5p  = 5.5
        self.cable_5n  = -5.5
        self.cable_3_3 = 3.6
        self.cable_2_5 = 3.6
        self.cable_1_8 = 2.3
        self.cable_1_5 = 2.3
        self.cable_1_0 = 1.5



        #Correction for voltage losses through multiplexer chain
        self.correct_m = 1.035
        self.correct_b = 0.00872 / 2

        #Resistor sizes for the current monitors for each branch
        self.r75 = 1     #5VP
        self.r74 = 1     #5VN
        self.r73 = 0.390 #1.8VA
        self.r72 = 0.390 #1.8VAD

        self.r160 = 0.01 #1.0V
        self.r161 = 0.01 #1.5V
        self.r172 = 0.01 #1.8V
        self.r175 = 0.01 #2.5V
        self.r176 = 0.01 #3.3V

        #Wait this many seconds after changing power settings for stabilization
        self.delay = 5

        #Various registers and disable bits for part of the spectrometer
        self.uc_disable      = 0x100
        self.adc_disable     = 0x301
        self.spe_enable     = 0x401

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

        #Tests are run sequentially, the settings are applied, then power data is collected
        #Each listing needs a name and what to set the 3 "disable spectrometer" registers to
        self.tests = []
        self.tests.append(POWER_TEST(name = "DDR on", uc_disable = 0x5, adc_disable = 0x3, spe_enable = 0x0))

        #When power data is collected, it happens in this order
        #Each listing needs the value to set the multiplexer chain to to bring the reading to the HK ADC
        self.configurations = {
                               "FPGA Thermistor (Kelvin)":0x14,
                               "ADC0 Thermistor (Kelvin)":0x15,
                               "ADC1 Thermistor (Kelvin)":0x16,

                               "+5V Output Voltage":0,
                               "+5V Output Current":1,
                               "-5V Output Voltage":2,
                               "-5V Output Current":3,

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
                               "1.0VD Output Current":0x13,
                               }

        #Needed to translate the ADC readings for the current configurations to actual current
        self.resistors      = {"+5V Output Current": self.r75,
                               "-5V Output Current": self.r74,

                               "1.8VA Output Current": self.r73,
                               "1.8VAD Output Current": self.r72,

                               "3.3VD Output Current": self.r176,

                               "2.5VD Output Current": self.r175,
                               "1.8VD Output Current": self.r172,

                               "1.5VD Output Current": self.r161,
                               "1.0VD Output Current": self.r160
                               }

        #These are branches which usually have such low current that the "voltage correction" will do more harm than good
        self.no_correct    = ["3.3VD Output Current", "2.5VD Output Current", "1.8VD Output Current", "1.5VD Output Current"]

        #Laying out the first column so far
        self.initial_df = ["Internal FPGA Voltages", "FPGA 1V", "FPGA 1.8V", "FPGA 2.5V", "FPGA Temp (Kelvin)", "", "PCB Measurements"]
        key_list = list(self.configurations.keys())
        key_list_pwr = []

        #This assumes the tests come in batches of Voltage and then Current
        #After current, it adds a row for the eventual power calculation
        #And after every batch, it adds a spacer row before inserting the next batch
        for num,i in enumerate(key_list):
            if ((num > 0) and ("Voltage" in i)):
                key_list_pwr.append("")
            key_list_pwr.append(i)
            if ("Current" in i):
                power_string = i.replace("Current", "Power (W)")
                key_list_pwr.append(power_string)
                cable_voltage = self.get_cable_voltage(branch = i)
                key_list_pwr.append(f"Dissipation through {cable_voltage} LDO input (W)")

        #Adds the rest of that first colums with all these indicators for the rows
        self.initial_df.extend(key_list_pwr)
        self.df = pd.DataFrame(self.initial_df, columns=[f"{self.name}"])

    def sequence(self):
        self.measure.set_analog_mux(0, 0, 4, 0)
        self.measure.set_analog_mux(1, 1, 4, 0)
        self.measure.set_analog_mux(2, 2, 4, 0)
        self.measure.set_analog_mux(3, 3, 4, 0)
        x = self.measure.get_adc1_data()
        self.measure.plot(self.measure.twos_comp(x, 14))
        x = self.measure.get_adc2_data()
        self.measure.plot(self.measure.twos_comp(x, 14))
        x = self.measure.get_adc3_data()
        self.measure.plot(self.measure.twos_comp(x, 14))
        x = self.measure.get_adc4_data()
        self.measure.plot(self.measure.twos_comp(x, 14))

        self.measure.get_calibrator_data()
        self.measure.get_pfb_data_sw()

        print("Setting up internal FPGA voltage readings")
        self.hk.setup_fpga_internal()
        print("Setting up I2C Mux")
        self.hk.init_i2c_mux()
        print("Setting up I2C ADC")
        self.hk.init_i2c_adc()

        print(f"Started the spectrometer and PCB settings, waiting {self.delay} seconds for power to stabilize")
        time.sleep(self.delay)

        print("Taking power data")
        #Will eventually need the name of the full row of columns in order to add rows later
        #This accumulates them as the test goes on
        all_indexes = [self.name]

        #Each test sets the hardware configuration for it, and then conducts the measurements
        for i in self.tests:
            #self.prepare_test(i)
            self.power_sequence(i.name)
            all_indexes.append(i.name)

        #print(all_indexes)

        #Loop through the left most column with all the indicators and note where the "Power" columns are
        power_columns = []
        ldo_columns = []
        for num,i in enumerate(self.df[self.name]):
            if ("Power" in i):
                power_columns.append(num)
            elif ("LDO" in i):
                ldo_columns.append(num)

        #When all the columns are in place, we want to calculate total power
        #I initialize a row that will hold all the total power values
        print("Calculating total power for each configuration")
        power_row = ["Total PCB Power (W)"]
        total_row = ["Total Power with LDO dissipation (W)"]
        for num,i in enumerate(self.df):
            #The first column just has the indexes, no values
            if (num > 0):
                #From there just add up all the power values indicated in the column and add the total to the above row
                total_power = 0
                total_ldo_power = 0
                for j in power_columns:
                    #print(j)
                    total_power += self.df[i][j]
                    #print(self.df[i][j])
                for j in ldo_columns:
                    total_ldo_power += self.df[i][j]
                #print(f"Total power for {self.df[i][0]}is {total_power}")
                power_row.append(total_power)
                total_row.append(total_ldo_power + total_power)

        #First create an empty row to space the new power row
        empty_row = pd.Series([""] * len(all_indexes), index=all_indexes)
        #Then the power row
        power_df = pd.Series(power_row, index = all_indexes)
        total_df = pd.Series(total_row, index = all_indexes)
        #And concatenate these new rows into the spreadsheet
        self.df = pd.concat([self.df, pd.DataFrame([empty_row]), pd.DataFrame([power_df]), pd.DataFrame([total_df])], ignore_index = True)
        #print(self.df)

        #Create a pandas.ExcelWriter object
        writer = pd.ExcelWriter(f"{self.name}.xlsx", engine='xlsxwriter')

        #Write the data frame to Excel
        self.df.to_excel(writer, index=False, sheet_name='Sheet1')

        #Get the XlsxWriter workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        #Adjust the column widths based on the content
        for i, col in enumerate(self.df.columns):
            width = max(self.df[col].apply(lambda x: len(str(x))).max(), len(col))
            worksheet.set_column(i, i, width)

        #Save the Excel file
        writer._save()
        print(f"Wrote {self.name}.xlsx")

    #Just writes the registers that enable/disable parts of the spectrometer and waits for power to settle
    def prepare_test(self, test):
        print(f"Preparing test {test.name}")
        #self.comm.connection.write_reg(self.uc_disable, test.uc_disable)
        #self.comm.connection.write_reg(self.adc_disable, test.adc_disable)
        #self.comm.connection.write_reg(self.spe_enable, test.spe_enable)
        #print(f"Waiting {self.delay} seconds for power to stabilize")
        #time.sleep(self.delay)
        #print(self.comm.connection.read_reg(0))

    #Measures all the desired tests. The name argument is just the name of the configuration, "FFT off" for example
    def power_sequence(self, name):
        print(f"Taking power data for the {name} configuration\n")

        #The internal measurements are quick, so I do them every time just to have them
        bank1v, bank1_8v, bank2_5v = self.hk.read_fpga_voltage()
        fpga_temp = int(self.hk.read_fpga_temp())

        #Resets the running list which will eventually be the full column that is appended to the spreadsheet.
        #Has appropriate spaces to account for the labels on the first column
        running_list = ["", round(bank1v/1000, 3), round(bank1_8v/1000, 3), round(bank2_5v/1000, 3), round(fpga_temp, 3), ""]
        print(f"1V is {bank1v} mV, 1.8V is {bank1_8v} mV, 2.5V is {bank2_5v} mV, temp is {fpga_temp} Kelvin\n")

        #Loops through all desired measurements, 3.3V branch, 1.8V branch, etc...
        for key,val in self.configurations.items():
            print(f"Measuring the {key} branch...")

            #Assuming each batch starts with voltage, add the space before a new batch
            if "Voltage" in key or "FPGA Thermistor" in key:
                running_list.extend([""])

            #A 0 means that the mux was confirmed to be written
            #The write_i2c_mux will print an error and return a 1 if the readback is incorrect also
            resp = 1
            while (resp != 0):
                resp = self.hk.write_i2c_mux(val)

            #Once the mux is set, this reads the ADC which the mux is pointing to
            #The ADC0 channel measures the voltage directly
            #The ADC4 channel measures the voltage after going through a 1/2 voltage divider, anticipating having to read any higher voltages than the ADC reference
            #temp is the ADC's internal temperature, probably not useful
            adc0, adc4, temp = self.hk.read_hk_data()
            #print(f"ADC0 is {adc0} and ADC4 {adc4}")

            #Most voltage/current branches need some correction because of the current drop across the mux chain
            #If they're in the "no_correct" list this skips. Otherwise, it applies a rough y = mx+b correction I figured out empirically
            # if (key not in self.no_correct):
            #     adc0 = (self.correct_m * adc0) + self.correct_b
            #     adc4 = (self.correct_m * adc4) + self.correct_b
            #     #print(f"Corrected ADC0 is {adc0} and ADC4 {adc4}")

            #The ADC just measures whatever voltage was at the input
            #If we know we used the mux to redirect a current measurement from the INA901 chip, then we need to convert that voltage to the actual current
            #Assuming that Current is measured after Voltage, for every current, I calculate the power from the two, using the previous ADC reading
            #Use absolute value with prev_adc0 because it could be negative for the -5.5V branch
            if "Current" in key:
                adc0, adc4 = self.hk.convert_current(resistance = self.resistors[key], val1 = adc0, val2 = adc4)
                p = round(adc0 * abs(prev_adc0), 3)
                cable_voltage = self.get_cable_voltage(branch = key)
                print(f"cable voltage is {cable_voltage} and voltage was {prev_adc0} and this current is {adc0}")
                p_ldo = round(abs(cable_voltage - prev_adc0) * adc0, 3)

            #+5V and -5V voltage measurements go through an op-amp divider, so they have a unique calculation to get the actual voltage
            elif "+5V Output Voltage" in key:
                adc0 = adc0 * 5
                adc4 = adc4 * 5
            elif "-5V Output Voltage" in key:
                adc0 = adc0 * -1 * (4 + (1/6))
                adc4 = adc4 * -1 * (4 + (1/6))

            elif "Thermistor" in key:
                adc0, adc4 = self.hk.convert_thermistor(adc0, adc4)

            adc0 = round(adc0, 3)
            adc4 = round(adc4, 3)
            print(f"ADC0 is {adc0} and ADC4 {adc4}\n")
            #print("\n")
            #Save the values in case this is a voltage that we want to multiply by the next current to get power
            prev_adc0 = adc0
            prev_adc4 = adc4

            #If we did calculate power because it was a current add that to the column, if not, just the voltage
            if "Current" in key:
                running_list.extend([adc0, p, p_ldo])
            else:
                running_list.extend([adc0])
            #input("Is this ok?")
        #With the full column, we can now add it to the Pandas Dataframe with the configuration title
        #print(self.df)
        #print(running_list)
        self.df[f"{name}"] = running_list
        
    def get_cable_voltage(self, branch):
        cable_voltage = None
        if (branch == "+5V Output Current"):
            cable_voltage = self.cable_5p
        elif (branch == "-5V Output Current"):
            cable_voltage = self.cable_5n
        elif (branch == "3.3VD Output Current"):
            cable_voltage = self.cable_3_3
        elif (branch == "2.5VD Output Current"):
            cable_voltage = self.cable_2_5
        elif (branch == "1.8VA Output Current"):
            cable_voltage = self.cable_1_8
        elif (branch == "1.8VD Output Current"):
            cable_voltage = self.cable_1_8
        elif (branch == "1.8VAD Output Current"):
            cable_voltage = self.cable_1_8
        elif (branch == "1.5VD Output Current"):
            cable_voltage = self.cable_1_5
        elif (branch == "1.0VD Output Current"):
            cable_voltage = self.cable_1_0
        else:
            print(f"Error, branch string is given as {branch} which does not exist in the table")
            return 0
        return cable_voltage

    def mux_test(self):
        self.hk.init_i2c_mux()
        try:
            while(1):
                resp = self.hk.write_i2c_mux(0x11)
                if (resp == 0):
                    print("correct")
                else:
                    print("incorrect")
        except KeyboardInterrupt:
            pass

        #self.comm.connection.write_reg(self.ud_ddr_disable, 0x400)
        print("switched")

        try:
            while(1):
                resp = self.hk.write_i2c_mux(0x11)
                if (resp == 0):
                    print("correct")
                else:
                    print("incorrect")
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        name = sys.argv[1]
    else:
        name = "test"

    comm = LuSEE_COMMS()
    comm.connection.write_cdi_reg(5, 69)
    resp = comm.connection.read_cdi_reg(5)
    if (resp == 69):
        print("[TEST]", "Communication to DCB Emulator is ok")
    else:
        sys.exit("[TEST] -> Communication to DCB Emulator is not ok")

    comm.connection.write_reg(0x120, 69)
    resp = comm.connection.read_reg(0x120)
    if (resp == 69):
        print("[TEST]", "Communication to Spectrometer Board is ok")
    else:
        sys.exit("[TEST] -> Communication to Spectrometer Board is not ok")

    power = LuSEE_POWER(name)
    #power.mux_test()
    power.sequence()
    print("Finished!")
