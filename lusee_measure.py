import matplotlib.pyplot as plt
import os
import time
import sys

from lusee_comm import LuSEE_COMMS

class LuSEE_MEASURE:
    def __init__(self):
        self.version = 1.0

        self.comm = LuSEE_COMMS()

    def get_adc1_data(self):
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC1")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc2_data(self):
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC2")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc3_data(self):
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC3")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc4_data(self):
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC4")
        data = self.comm.get_adc_data(header = False)
        return data

    def get_adc2_header_data(self):
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC2")
        data, header = self.comm.get_adc_data(header = True)
        return data, header

    def get_adcs_sync(self):
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
        self.comm.set_function("Counter")
        self.comm.set_counter_num(counter_num)
        data, header = self.comm.get_counter_data(header = True)
        return data, header

    def get_pfb_data(self):
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
        self.comm.set_index_array("A1", 0x1F, "main")
        self.comm.set_index_array("A1", 0x1F, "notch")

        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()

        x = self.comm.get_pfb_data(header = False)
        y = [hex(i) for i in x]

        self.plot_fft(x)

    def get_pfb_data_test(self):
        #Need to set these
        self.comm.set_function("FFT1")
        self.comm.set_weight_fold_shift(0xEEEE)

        #Notch not working yet
        self.comm.set_notch_average(4)
        #self.comm.notch_filter_on()
        self.comm.notch_filter_off()

        #Runs the spectrometer. Can turn it off with stop_spectrometer to see power
        self.comm.start_spectrometer()
        #Select which FFT to read out
        self.comm.select_fft("A1")
        #Need to set these as well for each FFT you read out
        self.comm.set_index_array("A1", 0x1F, "main")
        self.comm.set_index_array("A1", 0x1F, "notch")

        for i in range(21):
            print(f"Average setting is {i}")
            self.comm.set_main_average(i)
            self.comm.reset_all_fifos()
            self.comm.load_fft_fifos()

            x = self.comm.get_pfb_data(header = False)
            y = [hex(i) for i in x]

            self.plot_fft(x)

    def plot_fft(self, data):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data)):
            x.append(i / 2048 * 100 / 2)
        x.reverse()
        title = f"test"
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

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (len(val) > 1):
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
        result = self.comm.set_chan(ch, in1, in2, gain)
        return result

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        arg = sys.argv[1]
    else:
        arg = None
    measure = LuSEE_MEASURE()
    measure.comm.connection.write_cdi_reg(5, 69)
    resp = measure.comm.connection.read_cdi_reg(5)
    if (resp == 69):
        print("[TEST]", "Communication to DCB Emulator is ok")
    else:
        sys.exit("[TEST]", "Communication to DCB Emulator is not ok")

    measure.comm.connection.write_reg(5, 69)
    resp = measure.comm.connection.read_reg(5)
    if (resp == 69):
        print("[TEST]", "Communication to Spectrometer Board is ok")
    else:
        sys.exit("[TEST]", "Communication to Spectrometer Board is not ok")

    if (arg == "reset"):
        measure.comm.reset()
        measure.comm.reset_adc(adc = 0)

    measure.comm.readout_mode("fpga")

    if (arg == "adc"):
        measure.comm.reset_adc(adc = 0)
        measure.comm.write_adc(adc = 0, reg = 0x25, data = 0xF4)
        measure.comm.read_adc(adc = 0, reg = 0x25)
        print(hex(resp))
        print(hex(resp >> 16))

    # x = measure.get_adc1_data()
    # measure.plot(measure.twos_comp(x, 14))
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

    f = measure.set_analog_mux(0, 0, 4, "low")
    #print(f"Multiplexer array is {bin(f)}")

    x = measure.get_adc1_data()
    #print(x)
    #measure.save_adc_for_simulation(x)
    measure.plot(measure.twos_comp(x, 14))

    #measure.comm.stop_spectrometer()
    #input("ready?")
    d = measure.get_pfb_data()
    #measure.get_pfb_data_test()

    #You can save/plot the output data however you wish!
