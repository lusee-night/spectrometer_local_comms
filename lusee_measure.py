import matplotlib.pyplot as plt
import os
import time
import sys

from lusee_comm import LuSEE_COMMS

class LuSEE_MEASURE:
    def __init__(self):
        self.version = 1.06
        self.scratchpad_2 = 0x121

        self.comm = LuSEE_COMMS()

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
        self.comm.set_notch_average(4)
        #self.comm.notch_filter_on()
        self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set these as well for each FFT you read out
        self.comm.set_index_array("A1", 0x10, "main")
        self.comm.set_index_array("A1", 0x10, "notch")

        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        x = self.comm.get_pfb_data(header = False)
        y = [hex(i) for i in x]
        print(y)
        # for i in range(len(y)):
        #     print(f"{i}:{y[i]}")

        self.plot_fft(x, "A1")

    def get_pfb_data_all_fpga(self):
        #0 is red pcb
        #1 is green pcb
        self.comm.set_pcb(0)

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
        #self.comm.spectrometer_test_mode(1)
        self.comm.notch_filter_on()
        #self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set index as well for each FFT you read out
        self.comm.set_all_index(0x10)
        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        for i in range(16):
            key = self.get_key(i)
            self.comm.select_fft(key)
            self.comm.load_fft_fifos()
            x = self.comm.get_pfb_data(header = False)
            y = [hex(i) for i in x]
            # if (i == 0):
            #     print(y)
            #     self.plot_fft(self.twos_comp(x, 32), f"{key}fpga")
            #self.check_test_vals(x, i)
            self.plot_fft(self.twos_comp(x, 32), f"{key}_fpga")
        # print(self.comm.read_dcb_timestamp())
        # print(self.comm.read_sys_timestamp())
        # print(self.comm.read_df_timestamp())
        # print(self.comm.get_df_drop_err())

    def get_pfb_data_sw(self):
        #0 is red pcb
        #1 is green pcb
        self.comm.set_pcb(0)

        #Set analog multiplexer scheme
        self.set_analog_mux(0, 0, 4, 0)
        self.set_analog_mux(1, 1, 4, 0)
        self.set_analog_mux(2, 2, 4, 0)
        self.set_analog_mux(3, 3, 4, 0)

        #We will read from microcontroller
        self.comm.readout_mode("sw")
        #Need to set these
        self.comm.set_main_average(12)
        self.comm.set_notch_average(4)
        self.comm.set_sticky_error(0x0)
        self.comm.spectrometer_test_mode(1)
        self.comm.notch_filter_on()
        #self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        self.comm.set_all_index(0x10)

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
        x.reverse()
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

    def plot(self, data):
        fig, ax = plt.subplots()
        #print(data)
        title = f"test"
        fig.suptitle(title, fontsize = 20)
        yaxis = "counts"
        ax.set_ylabel(yaxis, fontsize=14)
        #ax.set_yscale('log')
        ax.set_xlabel('clock cycles', fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(data)

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
        measure.comm.reset_adc(adc = 0)

    if (arg == "adc"):
        measure.comm.reset_adc(adc = 0)
        measure.comm.write_adc(adc = 0, reg = 0x25, data = 0xF4)
        measure.comm.read_adc(adc = 0, reg = 0x25)
        print(hex(resp))
        print(hex(resp >> 16))

    measure.set_analog_mux(0, 0, 4, 0)
    measure.set_analog_mux(1, 1, 4, 0)
    measure.set_analog_mux(2, 2, 4, 0)
    measure.set_analog_mux(3, 3, 4, 0)

    x = measure.get_adc1_data()
    measure.plot(measure.twos_comp(x, 14))

    x = measure.get_adc2_data()
    measure.plot(measure.twos_comp(x, 14))

    x = measure.get_adc3_data()
    measure.plot(measure.twos_comp(x, 14))

    x = measure.get_adc4_data()
    measure.plot(measure.twos_comp(x, 14))
    #
    # a,b = measure.get_adc2_header_data()
    # print(b)
    #
    # c = measure.get_counter_data(0x100)
    # print(c[0])
    #
    # e = measure.get_adcs_sync()
    # measure.plot(measure.twos_comp(e[0], 14))
    #
    #d = measure.get_pfb_data()

    #measure.adc_cycle()

    #print(f"Multiplexer array is {bin(f)}")

    #x = measure.get_adc1_data()
    #print(x)
    #measure.save_adc_for_simulation(x)
    #measure.plot(measure.twos_comp(x, 14))

    #x = measure.get_adc2_data()
    #measure.plot(measure.twos_comp(x, 14))

    #measure.comm.stop_spectrometer()
    #input("ready?")
    #d = measure.get_pfb_data()
    #d = measure.get_pfb_data_all_fpga()
    #input("ready?")
    e = measure.get_pfb_data_sw()

    #You can save/plot the output data however you wish!
