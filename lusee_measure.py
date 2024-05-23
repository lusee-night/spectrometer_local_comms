import matplotlib.pyplot as plt
import os
import time
import sys

from lusee_comm import LuSEE_COMMS

class LuSEE_MEASURE:
    def __init__(self):
        self.version = 1.10
        self.comm = LuSEE_COMMS()

    def set_all_adc_ramp(self):
        self.comm.write_adc(0, 0x42, 0x08) #Enable digital functions on ADC0
        self.comm.write_adc(1, 0x42, 0x08) #Enable digital functions on ADC1
        self.comm.write_adc(0, 0x25, 0x04) #Enable ramp for channel A on ADC0
        self.comm.write_adc(1, 0x25, 0x04) #Enable ramp for channel A on ADC1
        self.comm.write_adc(0, 0x2B, 0x04) #Enable ramp for channel B on ADC0
        self.comm.write_adc(1, 0x2B, 0x04) #Enable ramp for channel B on ADC1

    def get_adc1_data(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC1")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc2_data(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC2")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc3_data(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC3")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc4_data(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC4")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc2_header_data(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC2")
        data, header = self.comm.get_adc_data(header = True)
        return data, header

    def get_adcs_sync(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC1")
        #With no argument, header defaults to 'False"
        data1 = self.comm.get_adc_data()
        self.comm.set_function("ADC2")
        data2 = self.comm.get_adc_data()
        self.comm.set_function("ADC3")
        data3 = self.comm.get_adc_data()
        self.comm.set_function("ADC4")
        data4 = self.comm.get_adc_data()
        return data1, data2, data3, data4

    def get_counter_data(self, counter_num):
        self.comm.readout_mode("fpga")
        self.comm.set_function("Counter")
        self.comm.set_counter_num(counter_num)
        data, header = self.comm.get_counter_data(header = True)
        return data, header

    def get_pfb_data(self):
        #We will read from fpga output
        self.comm.readout_mode("fpga")
        #Need to set these
        self.comm.set_function("FFT1")
        self.comm.set_main_average(10)
        self.comm.set_sticky_error(0x0)

        #Notch not working yet
        self.comm.set_notch_average(6)
        self.comm.notch_filter_on()
        #self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set these as well for each FFT you read out
        self.comm.set_index_array("A1", 0x18, "main")
        self.comm.set_index_array("A1", 0x18, "notch")

        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        x = self.comm.get_pfb_data(header = False)
        #y = [hex(i) for i in x]
        #print(y)
        # for i in range(len(y)):
        #     print(f"{i}:{y[i]}")

        self.plot_fft(self.twos_comp(x, 32), "A1")

    def get_pfb_data_all_fpga(self):
        #0 is red pcb
        #1 is green pcb
        self.comm.set_pcb(1)

        #Set analog multiplexer scheme
        self.set_analog_mux(0, 0, 4, 0)
        self.set_analog_mux(1, 1, 4, 0)
        self.set_analog_mux(2, 2, 4, 0)
        self.set_analog_mux(3, 3, 4, 0)

        #We will read from fpga output
        self.comm.readout_mode("fpga")
        #Need to set these
        self.comm.set_function("FFT1")
        self.comm.set_main_average(10)
        self.comm.set_notch_average(4)
        self.comm.set_sticky_error(0x0)
        self.comm.spectrometer_test_mode(0)
        self.comm.notch_filter_on()
        #self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set index as well for each FFT you read out
        self.comm.set_all_index(0x18)
        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        for i in ["FFT1", "FFT2", "FFT3", "FFT4"]:
            #key = self.get_key(i)
            self.comm.set_function(i)
            self.comm.load_fft_fifos()
            x = self.comm.get_pfb_data(header = False)
            y = [hex(i) for i in x]
            # if (i == 0):
            #     print(y)
            #     self.plot_fft(self.twos_comp(x, 32), f"{key}fpga")
            #self.check_test_vals(x, i)
            self.plot_fft(self.twos_comp(x, 32), f"{i}_fpga")
        # print(self.comm.read_dcb_timestamp())
        # print(self.comm.read_sys_timestamp())
        # print(self.comm.read_df_timestamp())
        # print(self.comm.get_df_drop_err())

    def get_pfb_data_sw(self):
        #0 is red pcb
        #1 is green pcb
        self.comm.set_pcb(1)

        #Set analog multiplexer scheme
        self.set_analog_mux(0, 0, 4, 0)
        self.set_analog_mux(1, 1, 4, 0)
        self.set_analog_mux(2, 2, 4, 0)
        self.set_analog_mux(3, 3, 4, 0)

        #We will read from microcontroller
        self.comm.readout_mode("sw")
        #Need to set these
        self.comm.set_main_average(16)
        self.comm.set_notch_average(4)
        self.comm.set_sticky_error(0x0)
        self.comm.spectrometer_test_mode(0)
        #self.comm.notch_filter_on()
        self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        self.comm.set_all_index(0x18)

        data_good = False
        errors = 0
        while (not data_good):
            #Use this function to get all 16 correlations from the software
            x = self.comm.get_pfb_data_sw(header = False)
            #If there was an error with receiving data, it means you don't have all 16 channel subarrays
            #Or at least one of them is empty
            if (len(x) == 16 and (len(i) != 0 for i in x)):
                data_good = True
            else:
                errors += 1
                self.comm.stop_spectrometer()
                self.comm.start_spectrometer()
                print(f"Length of 16 ch array is {len(x)}")
                for i in range(16):
                    try:
                        print(f"Length of data channel {i} is {len(x[i])}")
                    except:
                        pass
            if (errors > 10):
                print("More than 10 errors in lusee_measure, exiting")
                break
        #y = [hex(i) for i in x[0]]
        #print(y)
        # for i in range(len(y)):
        #     print(f"-{i}:{y[i]}-", end="")
        for i in range(16):
            #print([hex(j) for j in x[i]])
            #self.check_test_vals(x[i], i)
            self.plot_fft(self.twos_comp(x[i], 32), f"{self.get_key(i)}_uC")

    def check_test_vals(self, data, ch):
        start_val = 0 + (2048 * ch)
        end_val = start_val + 2047
        for num,i in enumerate(range(start_val, end_val+1)):
            if (data[num] != i):
                print(f"Test data error: Val should be {hex(i)}, but is {data[num]}")

    def plot_fft(self, data, title):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data)):
            x.append(i / 2048 * 100 / 2)
        #x.reverse()
        fig.suptitle(title, fontsize = 20)
        yaxis = "counts"
        ax.set_ylabel(yaxis, fontsize=14)
        ax.set_yscale('log')
        ax.set_xlabel('MHz', fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(x, data)

        plt.show()
        plot_path = os.path.join(os.getcwd(), "plots")
        if not (os.path.exists(plot_path)):
            os.makedirs(plot_path)

        fig.savefig (os.path.join(plot_path, f"{title}.jpg"))

    def plot_adc_overlay(self, data, title):
        num_repetitions = len(data) // 2048
        print(f"Overall length is {len(data)}")
        print(f"Num repetitions is {num_repetitions}")
        adc_data = []
        names = []
        for i in range(num_repetitions+1):
            adc_data.append(data[i*2048:(i*2048)+2048])
            names.append(i)
        #print(data[2046:2050])
        #print(adc_data[0][2046:])
        #print(adc_data[1][0:2])
        #print(f"Length of one is {len(adc_data[0])}")
        #print(f"Length of two is {len(adc_data[1])}")
        #print(adc_data[0])
        #print("---")
        #print(adc_data[1])
        #print("---")
        #print(adc_data[2])

        self.plot_multiple(adc_data, title, "ADC Counts", "ADC Values", names)
        self.plot_multiple([adc_data[0], adc_data[2], adc_data[4], adc_data[6]], title, "ADC Counts", "ADC Values", names)
        self.plot_multiple([adc_data[1], adc_data[3], adc_data[5], adc_data[7]], title, "ADC Counts", "ADC Values", names)


    def plot(self, data, title, xaxis = "", yaxis = ""):
        fig, ax = plt.subplots()
        fig.suptitle(title, fontsize = 20)
        ax.set_ylabel(yaxis, fontsize=14)
        ax.set_xlabel(xaxis, fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(data)

        plt.show()
        plot_path = os.path.join(os.getcwd(), "plots")
        if not (os.path.exists(plot_path)):
            os.makedirs(plot_path)

        fig.savefig (os.path.join(plot_path, f"{title}.jpg"))

    def plot_multiple(self, data, title, xaxis = "", yaxis = "", names = []):
        fig, ax = plt.subplots()
        fig.suptitle(title, fontsize = 20)
        ax.set_ylabel(yaxis, fontsize=14)
        ax.set_xlabel(xaxis, fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        for d,n in zip(data, names):
            ax.plot(d, label = n)
        plt.legend()
        plt.show()
        plot_path = os.path.join(os.getcwd(), "plots")
        if not (os.path.exists(plot_path)):
            os.makedirs(plot_path)

        fig.savefig (os.path.join(plot_path, f"{title}.jpg"))

    def get_key(self, num):
        for key, val in self.comm.fft_sel.items():
            if (val == num):
                return key

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (not isinstance(val, int)):
            new = []
            for i in val:
                if (i & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
                    twos = i - (1 << bits)        # compute negative value
                    new.append(twos)
                else:
                    new.append(i)
            return new
        else:
            if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
                val = val - (1 << bits)        # compute negative value
            return val

    def set_analog_mux(self, ch, in1, in2, gain):
        result = self.comm.set_chan_gain(ch, in1, in2, gain)
        return result

    def get_calibrator_data(self, setup = False):
        notch_ave = 6
        Nac1 = 2
        Nac2 = 10
        if (setup):
            self.comm.setup_calibrator(Nac1 = Nac1,
                                    Nac2 = Nac2,
                                    notch_index = 0x2,
                                    cplx_index = 29,
                                    sum1_index = 32,
                                    sum2_index = 36,
                                    powertop_index = 8,
                                    powerbot_index = 32,
                                    driftFD_index = 32,
                                    driftSD1_index = 26,
                                    driftSD2_index = 2,
                                    default_drift = 0x6487C088,
                                    have_lock_value = 0x0002A2A,
                                    have_lock_radian = 0x00000D6C,
                                    lower_guard_value = 0xFFFEBDE1,
                                    upper_guard_value = 0x6487ED51,
                                    power_ratio = 0x0,
                                    antenna_enable = 0xF,
                                    power_slice = 0x9,
                                    fdsd_slice = 0x0,
                                    fdxsdx_slice = 0xB)

            #sys.exit("Done")
            #Need to set these
            self.comm.set_main_average(16)
            self.comm.set_notch_average(notch_ave)
            self.comm.set_cal_sticky_error(1)
            self.comm.notch_filter_on()
            #We will read from microcontroller
            self.comm.readout_mode("sw")
            #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
            self.comm.start_spectrometer()
            self.comm.set_all_index(0x18)

        data_good = False
        errors = 0
        self.comm.readout_mode("sw")
        x = self.comm.get_calib_data_sw(header = False, avg = notch_ave, Nac1 = Nac1, Nac2 = Nac2, test = False)
        y = []
        for i in x:
            y.append([hex(j) for j in i])

        all_names = ["Fout1_Real", "Fout1_Imag", "Fout2_Real", "Fout2_Imag", "Fout3_Real", "Fout3_Imag", "Fout4_Real", "Fout4_Imag", "Lock", "Drift", "Top1", "Top2", "Top3", "Top4", "Bot1", "Bot2", "Bot3", "Bot4", "FD1", "FD2", "FD3", "FD4", "SD1", "SD2", "SD3", "SD4", "FDX", "SDX"]
        for num,i in enumerate(y):
            print(f"{all_names[num]}-----")
            print(i)

        names = ["Fout1_Real", "Fout1_Imag", "Fout2_Real", "Fout2_Imag", "Fout3_Real", "Fout3_Imag", "Fout4_Real", "Fout4_Imag"]
        for num,i in enumerate(range(0, 8, 1)):
            self.plot_fft(self.twos_comp(x[i], 32), f"{self.test_name}_{names[num]}")

        self.plot(x[8], "Lock", "Cycles", "Value")
        self.plot(self.twos_comp(x[9], 32), "Drift", "Cycles", "Value")

        names = ["Top1", "Top2", "Top3", "Top4", "Bot1", "Bot2", "Bot3", "Bot4"]
        for num,i in enumerate(range(10, 18, 1)):
            self.plot(self.twos_comp([i], 32), f"{self.test_name}_{names[num]}", "Cycles", "Value")
        self.plot_multiple(x[10:18], "All power signals", "Cycles", "Value", names)

        names = ["FD1", "FD2", "FD3", "FD4", "SD1", "SD2", "SD3", "SD4", "FDX", "SDX"]
        fdsd = []
        for num,i in enumerate(range(18, 28, 1)):
            self.plot(self.twos_comp(x[i], 32), f"{self.test_name}_{names[num]}")
            fdsd.append(self.twos_comp(x[i], 32))
        self.plot_multiple(fdsd, "All FD-SD signals", "Cycles", "Value", names)

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        arg = sys.argv[1]
    else:
        arg = None
    #time.sleep(10)
    measure = LuSEE_MEASURE()
    measure.comm.connection.write_cdi_reg(5, 69)
    resp = measure.comm.connection.read_cdi_reg(5)
    if (resp == 69):
        print("[TEST] Communication to DCB Emulator is ok")
    else:
        sys.exit("[TEST] Communication to DCB Emulator is not ok")

    measure.comm.connection.write_reg(0x120, 69)
    resp = measure.comm.connection.read_reg(0x120)
    if (resp == 69):
        print("[TEST] Communication to Spectrometer Board is ok")
    else:
        print(resp)
        sys.exit("[TEST] Communication to Spectrometer Board is not ok")

    if (arg == "reset"):
        measure.comm.reset()
        measure.comm.reset_adc(adc0 = True, adc1 = True)

    if (arg == "adc"):
        measure.set_all_adc_ramp()

    measure.test_name = arg

    measure.set_analog_mux(0, 0, 4, 2)
    measure.set_analog_mux(1, 1, 4, 2)
    measure.set_analog_mux(2, 2, 4, 2)
    measure.set_analog_mux(3, 3, 4, 2)

    print(f"Firmware version is {measure.comm.get_firmware_version()}")
    measure.comm.connection.write_reg(0x838, 1)
    #print(measure.comm.read_dcb_timestamp())
    #print(measure.comm.read_sys_timestamp())
    x = measure.get_adc1_data()
    print(f"Length of ADC1 data is {len(x)}")
    measure.plot(measure.twos_comp(x, 14), "ADC1", "ADC ticks", "ADC counts")
    measure.plot_adc_overlay(measure.twos_comp(x, 14), "ADC1")
    measure.get_pfb_data()
    #measure.get_pfb_data_all_fpga()
    measure.get_calibrator_data(setup = True)

    #measure.get_pfb_data_sw()
    #You can save/plot the output data however you wish!
