import time
import datetime
import sys
import pandas as pd
import json
import os
import logging
import logging.config

from utils import LuSEE_HK
from utils import LuSEE_HK_EMULATOR
from utils import LuSEE_COMMS
from lusee_measure import LuSEE_MEASURE

class LuSEE_POWER:
    def __init__(self, emulator):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        if (emulator):
            self.hk = LuSEE_HK_EMULATOR()
        else:
            self.hk = LuSEE_HK()
        self.measure = LuSEE_MEASURE()
        self.comm = LuSEE_COMMS()
        
        #Input voltages on cable, used for LDO power consumption
        self.cable_5p  = 5.5
        self.cable_5n  = -5.5
        self.cable_3_3 = 3.6
        self.cable_2_5 = 3.6
        self.cable_1_8 = 2.3
        self.cable_1_5 = 2.3
        self.cable_1_0 = 1.5

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

        #Because of the voltage drop through the multiplexer array, we need to manually correct each measurement
        #If the measurement is above 0.1V or so, the amount lost in the multiplexers is an even proportion
        #However, the current measurements are less, and they have different proportions lost in the chain
        self.correction = {
                               "FPGA Thermistor (Kelvin)":1,
                               "ADC0 Thermistor (Kelvin)":1,
                               "ADC1 Thermistor (Kelvin)":1,

                               "+5V Output Voltage":1,
                               "+5V Output Current":1,
                               "-5V Output Voltage":1,
                               "-5V Output Current":1,

                               "1.8VA Output Voltage":1,
                               "1.8VA Output Current":1,
                               "1.8VAD Output Voltage":1,
                               "1.8VAD Output Current":1,

                               "3.3VD Output Voltage":1,
                               "3.3VD Output Current":1.00,
                               "2.5VD Output Voltage":1,
                               "2.5VD Output Current":1,

                               "1.8VD Output Voltage":1,
                               "1.8VD Output Current":1.0,
                               "1.5VD Output Voltage":1,
                               "1.5VD Output Current":1.0,
                               "1.0VD Output Voltage":1.00,
                               "1.0VD Output Current":1.00,
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


        self.power_rails = {
            "I5_5P [A]": [5.5,0],
            "I5_5N [A]": [5.5,0],
            "I3_6P [A]": [3.6,0],
            "I2_3P [A]": [2.3,0],
            "I1_5P [A]": [1.5,0]
            }
        self.test_info = {}
        self.settings_info = {}

    def stop(self):
        self.measure.stop()
        self.comm.stop()

    def sequence(self, config_file):
        with open(config_file, "r") as jsonfile:
            self.json_data = json.load(jsonfile)

        self.name = self.json_data['title']
        self.df = pd.DataFrame(self.initial_df, columns=[f"{self.name}"])

        start = datetime.datetime.now()
        self.test_info['Test Datetime Start'] = start.strftime("%B %d, %Y %I:%M:%S %p")
        self.test_info['Test Datetime End'] = None
        self.test_info['Test Duration'] = None
        firmware = self.comm.get_firmware_version()

        self.test_info['Firmware Version'] = firmware['version']
        self.test_info['Firmware ID'] = firmware['id']
        self.test_info['Firmware Compilation Datetime'] = firmware['formatted_datetime']
        self.test_info['User Description'] = self.json_data['comment']

        self.measure.start_test(config_file)
        self.comm.connection.write_reg(0x100, 6)

        num = int(self.json_data['adc_num'], 16)
        high = int(self.json_data['adc_high'], 16)
        low = int(self.json_data['adc_low'], 16)

        adc_stats = {"HIGH_THRESHOLD": high,
                    "LOW_THRESHOLD": low}
        stats = self.comm.get_adc_stats(num = num, high = high, low = low)
        self.logger.info(stats)
        adc_stats.update(stats)

        self.settings_info['Register 0x100'] = hex(comm.connection.read_reg(comm.uC_reset))
        self.settings_info['Register 0x101'] = hex(comm.connection.read_reg(comm.DDR_reg))
        self.settings_info['ADC0 gain and config (Register 0x500)'] = hex(comm.connection.read_reg(comm.mux0_reg))
        self.settings_info['ADC1 gain and config (Register 0x501)'] = hex(comm.connection.read_reg(comm.mux1_reg))
        self.settings_info['ADC2 gain and config (Register 0x502)'] = hex(comm.connection.read_reg(comm.mux2_reg))
        self.settings_info['ADC3 gain and config (Register 0x503)'] = hex(comm.connection.read_reg(comm.mux3_reg))
        self.settings_info['Spectrometer Enabled'] = hex(comm.connection.read_reg(comm.enable_spe))
        self.settings_info['Spectrometer Averages'] = 2 ** comm.connection.read_reg(comm.main_average)
        self.settings_info['Notch Filter Enabled'] = hex(comm.connection.read_reg(comm.notch_reg))
        self.settings_info['Notch Averages'] = 2 ** comm.connection.read_reg(comm.notch_average)

        self.settings_info['Spectrometer Blocks Disabled'] = hex(comm.connection.read_reg(comm.spe_disable))
        self.settings_info['Notch Averagers Disabled'] = hex(comm.connection.read_reg(comm.calibrator_and_notch_disable))
        self.settings_info['Main Averagers Disabled'] = hex(comm.connection.read_reg(comm.avg_disable))
        self.settings_info['Notch Correlators Disabled'] = hex(comm.connection.read_reg(comm.corr_notch_disable))
        self.settings_info['Main Correlators Disabled'] = hex(comm.connection.read_reg(comm.corr_main_disable))
        self.settings_info['Notch Subtract Disabled'] = hex(comm.connection.read_reg(comm.notch_subtract_disable))

        self.settings_info['Correlation Array 1'] = hex(comm.connection.read_reg(comm.corr_array1))
        self.settings_info['Correlation Array 2'] = hex(comm.connection.read_reg(comm.corr_array2))
        self.settings_info['Correlation Array 3'] = hex(comm.connection.read_reg(comm.corr_array3))
        self.settings_info['Notch Array 1'] = hex(comm.connection.read_reg(comm.notch_array1))
        self.settings_info['Notch Array 2'] = hex(comm.connection.read_reg(comm.notch_array2))
        self.settings_info['Notch Array 3'] = hex(comm.connection.read_reg(comm.notch_array3))

        self.settings_info['Calibrator Phaser Averages'] = 2 ** (5 + (comm.connection.read_reg(comm.Nac1)))
        self.settings_info['Calibrator Process Averages'] = 2 ** comm.connection.read_reg(comm.Nac2)

        self.logger.info("Setting up internal FPGA voltage readings")
        self.hk.setup_fpga_internal()
        if (not emulator):
            self.logger.info("Setting up I2C Mux")
            self.hk.init_i2c_mux()
            self.logger.info("Setting up I2C ADC")
            self.hk.init_i2c_adc()

        self.logger.info(f"Started the spectrometer and PCB settings, waiting {self.delay} seconds for power to stabilize")
        time.sleep(self.delay)

        self.logger.info("Taking power data")
        #Will eventually need the name of the full row of columns in order to add rows later
        #This accumulates them as the test goes on
        all_indexes = [self.name]

        #Each test sets the hardware configuration for it, and then conducts the measurements
        self.power_sequence("Measurements")
        all_indexes.append("Measurements")

        for key,val in self.power_rails.items():
            self.power_rails[key][1] = round(val[1], 3)

        #self.logger.debug(all_indexes)

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
        self.logger.info("Calculating total power for each configuration")
        power_row = ["Total PCB Power (W)"]
        total_row = ["Total Power with LDO dissipation (W)"]
        for num,i in enumerate(self.df):
            #The first column just has the indexes, no values
            if (num > 0):
                #From there just add up all the power values indicated in the column and add the total to the above row
                total_power = 0
                total_ldo_power = 0
                for j in power_columns:
                    total_power += self.df[i][j]
                for j in ldo_columns:
                    total_ldo_power += self.df[i][j]
                power_row.append(total_power)
                total_row.append(total_ldo_power + total_power)

        #Empty column
        self.df[''] = ''
        #First create an empty row to space the new power row
        empty_row = pd.Series([""] * len(all_indexes), index=all_indexes)
        #Then the power row
        power_df = pd.Series(power_row, index = all_indexes)
        total_df = pd.Series(total_row, index = all_indexes)
        #And concatenate these new rows into the spreadsheet
        self.df = pd.concat([self.df, pd.DataFrame([empty_row]), pd.DataFrame([power_df]), pd.DataFrame([total_df])], ignore_index = True)


        end = datetime.datetime.now()
        self.test_info['Test Datetime End'] = end.strftime("%B %d, %Y %I:%M:%S %p")
        duration = end - start
        total_seconds = int(duration.total_seconds())
        minutes, seconds = divmod(total_seconds, 60)
        self.test_info['Test Duration'] = f"{minutes:02d} minutes, {seconds:02d} seconds"

        additional_descriptions = list(self.power_rails.keys()) + [''] + list(self.test_info.keys()) + [''] + list(self.settings_info.keys()) + list(adc_stats.keys())
        power_rail_data = self.power_rails.values()
        power_rail_amps = []
        power_rail_power = []
        for i in power_rail_data:
            power_rail_amps.append(i[1])
            power_rail_power.append(i[0]*i[1])
        additional_data = power_rail_amps + [''] + list(self.test_info.values()) + [''] + list(self.settings_info.values()) + list(adc_stats.values())
        power_data = power_rail_power + [sum(power_rail_power)]

        new_series = pd.Series(additional_descriptions, name='Extra Parameters')
        self.df = self.df.reindex(index = new_series.index).assign(C=new_series)
        self.df['Extra Data'] = pd.Series(additional_data)
        self.df['Power'] = pd.Series(power_data)

        #Create a pandas.ExcelWriter object
        writer = pd.ExcelWriter(f"{self.name}.xlsx", engine='xlsxwriter')

        #Write the data frame to Excel
        self.df.to_excel(writer, index=False, sheet_name='LuSEE_Power_Measurement')

        #Get the XlsxWriter workbook and worksheet objects
        workbook = writer.book
        left_align_format = workbook.add_format({'align': 'left'})

        worksheet = writer.sheets['LuSEE_Power_Measurement']
        #Adjust the column widths based on the content
        for i, col in enumerate(self.df.columns):
            if (col != "Extra Data"): #This column gets very wide with the comment field
                width = max(self.df[col].apply(lambda x: len(str(x))).max(), len(col))
                worksheet.set_column(i, i, width, left_align_format)

        #Save the Excel file
        writer._save()
        self.logger.info(f"Wrote {self.name}.xlsx")

    #Measures all the desired tests. The name argument is just the name of the configuration, "FFT off" for example
    def power_sequence(self, name):
        self.logger.info(f"Taking power data for the {name} configuration\n")

        #The internal measurements are quick, so I do them every time just to have them
        bank1v, bank1_8v, bank2_5v = self.hk.read_fpga_voltage()
        fpga_temp = int(self.hk.read_fpga_temp())

        #Resets the running list which will eventually be the full column that is appended to the spreadsheet.
        #Has appropriate spaces to account for the labels on the first column
        running_list = ["", round(bank1v/1000, 3), round(bank1_8v/1000, 3), round(bank2_5v/1000, 3), round(fpga_temp, 3), ""]
        self.logger.info(f"1V is {bank1v} mV, 1.8V is {bank1_8v} mV, 2.5V is {bank2_5v} mV, temp is {fpga_temp} Kelvin\n")

        #Loops through all desired measurements, 3.3V branch, 1.8V branch, etc...
        for key,val in self.configurations.items():
            self.logger.info(f"Measuring the {key} branch...")

            #Assuming each batch starts with voltage, add the space before a new batch
            if "Voltage" in key or "FPGA Thermistor" in key:
                running_list.extend([""])

            #A 0 means that the mux was confirmed to be written
            #The write_i2c_mux will print an error and return a 1 if the readback is incorrect also
            resp = 1
            while (resp != 0):
                resp = self.hk.write_i2c_mux(val)

            time.sleep(self.delay)

            #Once the mux is set, this reads the ADC which the mux is pointing to
            #The ADC0 channel measures the voltage directly
            #The ADC4 channel measures the voltage after going through a 1/2 voltage divider, anticipating having to read any higher voltages than the ADC reference
            #temp is the ADC's internal temperature, probably not useful
            adc0, adc4, temp = self.hk.read_hk_data()
            self.logger.info(f"Raw ADC0 is {adc0} and ADC4 {adc4}")

            #Correction needs to be applied because of the losses along the multiplexer chain
            adc0 = adc0 / self.correction[key]
            adc4 = adc4 / self.correction[key]

            #The ADC just measures whatever voltage was at the input
            #If we know we used the mux to redirect a current measurement from the INA901 chip, then we need to convert that voltage to the actual current
            #Assuming that Current is measured after Voltage, for every current, I calculate the power from the two, using the previous ADC reading
            #Use absolute value with prev_adc0 because it could be negative for the -5.5V branch
            if "Current" in key:
                adc0, adc4 = self.hk.convert_current(resistance = self.resistors[key], val1 = adc0, val2 = adc4)
                if (abs(prev_adc0) < 0.1):
                    adc0 = 0
                p = round(adc0 * abs(prev_adc0), 3)
                cable_voltage = self.get_cable_voltage(branch = key)
                self.logger.info(f"Cable voltage is {cable_voltage} and voltage was {prev_adc0} and this current is {round(adc0, 3)}")
                p_ldo = round(abs(cable_voltage - prev_adc0) * adc0, 3)

                if "+5V" in key:
                    self.power_rails["I5_5P [A]"][1] += adc0
                elif "-5V" in key:
                    self.power_rails["I5_5N [A]"][1] += adc0
                elif ("3.3" in key) or ("2.5" in key):
                    self.power_rails["I3_6P [A]"][1] += adc0
                elif ("1.8" in key) or ("1.5" in key):
                    self.power_rails["I2_3P [A]"][1] += adc0
                elif "1.0" in key:
                    self.power_rails["I1_5P [A]"][1] += adc0
                else:
                    sys.exit(f"Error: Key was {key}")

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
            self.logger.info(f"ADC0 is {adc0} and ADC4 {adc4}\n")
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
        #self.logger.debug(self.df)
        #self.logger.debug(running_list)
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
            self.logger.error(f"Branch string is given as {branch} which does not exist in the table")
            return 0
        return cable_voltage

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = 'config/config_logger.ini'
    config_path = os.path.join(script_dir, relative_path)
    logging.config.fileConfig(config_path)

    config_file = sys.argv[1]
    emulator = sys.argv[2]
    power = LuSEE_POWER(emulator)

    comm = LuSEE_COMMS()
    comm.connection.write_cdi_reg(5, 69, 32000)
    resp = comm.connection.read_cdi_reg(5)
    if (resp["data"] == 69):
        power.logger.info("Communication to DCB Emulator is ok")
    else:
        power.logger.critical(f"Communication to DCB Emulator is not ok. Response was {resp}")
        sys.exit()

    comm.connection.write_reg(0x120, 69)
    resp = comm.connection.read_reg(0x120)
    if (resp == 69):
        power.logger.info("Communication to Spectrometer Board is ok")
    else:
        power.logger.critical(f"Communication to Spectrometer Board is not ok. Response was {resp}")
        sys.exit()


    power.sequence(config_file)
    power.stop()
    power.logger.info("Finished!")
