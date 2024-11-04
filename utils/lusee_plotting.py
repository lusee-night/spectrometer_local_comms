import os
import json
import math
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import FuncFormatter

class LuSEE_PLOTTING:
    def __init__(self, directory):
        self.version = 1.1
        self.prefix = "LuSEE Plotting --> "
        self.tick_size = 22
        self.title_size = 32
        self.subtitle_size = 20
        self.label_size = 14
        self.plot_num = 0

        self.directory = directory
        try:
            with open(os.path.join(self.directory, "output.json"), "r") as jsonfile:
                self.json_data = json.load(jsonfile)
        except:
            pass

    def convert_from_radian(self, val):
        sign = val&0xC0000000
        if (sign == 0x40000000):
            return math.pi
        elif (sign == 0x80000000):
            return -1 * math.pi
        elif (sign == 0x00000000):
            sign = True
            working_val = 0
        elif (sign == 0xC0000000):
            sign = False
            working_val = -1

        for num,j in enumerate(range(29, -1, -1)):
            digit_mask = 1 << j
            masked_val = (val & digit_mask) >> j
            if (masked_val):
                working_val += masked_val/(2**(num+1))
        return working_val

    def from_radian(self, val):
        """compute the radian angle equivalent of int value val in Microchip format"""
        if (isinstance(val, str)):
            return self.convert_from_radian(int(val, 16))
        elif (isinstance(val, list)):
            new = []
            for i in val:
                if (isinstance(i, str)):
                    new.append(self.convert_from_radian(int(val, 16)))
                elif (isinstance(i, int)):
                    new.append(self.convert_from_radian(i))
                else:
                    sys.exit(f"Incorrect type. {val} element is of type {type(i)}")
            return new
        elif (isinstance(val, int)):
            return self.convert_from_radian(val)
        else:
            sys.exit(f"Incorrect type. {val} is of type {type(val)}")

    def convert_twos_comp(self, val, bits):
        if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
            val = val - (1 << bits)        # compute negative value
        return val

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (not isinstance(val, int)):
            new = []
            for i in val:
                new.append(self.convert_twos_comp(i, bits))
            return new
        else:
            return (self.convert_twos_comp(val, bits))

    def plot_adc(self, adc, show, save):
        print(f"{self.prefix}Plotting ADC {adc}")

        with open(os.path.join(self.directory, f"adc{adc}_output.json"), "r") as jsonfile:
            adc_data = json.load(jsonfile)

        data = adc_data["data"]
        fig = self.plot(self.twos_comp(data, 14), f"ADC{adc} raw data", xaxis = "Ticks", yaxis = "Value")

        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_adc{adc}.jpg"))
        self.plot_num += 1

    def plot_pfb_fpga(self, pfb, show, save):
        print(f"{self.prefix}Plotting FPGA PFB {pfb}")

        with open(os.path.join(self.directory, f"pfb_fpga{pfb}_output.json"), "r") as jsonfile:
            pfb_data = json.load(jsonfile)

        data = pfb_data["data"]
        fig = self.plot_fft(data, f"FFT{pfb} through FPGA")

        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_pfb_fpga{pfb}.jpg"))
        self.plot_num += 1

    def plot_pfb_sw(self, show, save):
        print(f"{self.prefix}Plotting SW PFB")

        with open(os.path.join(self.directory, f"pfb_sw_output.json"), "r") as jsonfile:
            pfb_data = json.load(jsonfile)

        data = pfb_data["data"]
        for i in range(16):
            fig = self.plot_fft(data[i], f"FFT{i} through Microcontroller")

            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_pfb_sw{i}.jpg"))
            self.plot_num += 1

    def plot(self, data, title, xaxis = "", yaxis = ""):
        fig, ax = plt.subplots()
        fig.suptitle(title, fontsize=self.subtitle_size)
        ax.set_ylabel(yaxis, fontsize=self.label_size)
        ax.set_xlabel(xaxis, fontsize=self.label_size)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(data)
        return fig

    def plot_fft(self, data, title):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data)):
            x.append(i / 2048 * 100 / 2)
        #x.reverse()
        fig.suptitle(title, fontsize=self.subtitle_size)
        yaxis = "Counts"
        ax.set_ylabel(yaxis, fontsize=self.label_size)
        ax.set_yscale('log')
        ax.set_xlabel('MHz', fontsize=self.label_size)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(x, data)
        return fig

    def print_calib(self):
        with open(os.path.join(self.directory, f"calib_output.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]

        formatted_data = []
        for i in data:
            formatted_data.append([hex(j) for j in i])

        all_names = ["Fout1_Real", "Fout1_Imag", "Fout2_Real", "Fout2_Imag", "Fout3_Real", "Fout3_Imag", "Fout4_Real", "Fout4_Imag", "Lock", "Drift", "Top1", "Top2", "Top3", "Top4", "Bot1", "Bot2", "Bot3", "Bot4", "FD1", "FD2", "FD3", "FD4", "SD1", "SD2", "SD3", "SD4", "FDX", "SDX"]
        for num,i in enumerate(formatted_data):
            print(f"-----{all_names[num]}-----")
            print(i)

    def plot_single_bin(self, show, save, b):
        with open(os.path.join(self.directory, f"calib_output1.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        names = [f"Ch0_Real_bin{b}", f"Ch0_Imag_bin{b}", f"Ch1_Real_bin{b}", f"Ch1_Imag_bin{b}", f"Ch2_Real_bin{b}", f"Ch2_Imag_bin{b}", f"Ch3_Real_bin{b}", f"Ch3_Imag_bin{b}"]
        for i in range(8):
            fig = self.plot(self.twos_comp(data[i], 32), f"{names[i]}", xaxis = "Cycles", yaxis = "Value")

            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_{names[i]}.jpg"))
            self.plot_num += 1

    def plot_cal_correlator(self, show, save):
        with open(os.path.join(self.directory, f"calib_output2.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        names = [f"Ch0_Real_correlator", f"Ch0_Imag_correlator", f"Ch1_Real_correlator", f"Ch1_Imag_correlator", f"Ch2_Real_correlator", f"Ch2_Imag_correlator", f"Ch3_Real_correlator", f"Ch3_Imag_correlator"]
        for i in range(16):
            fig = self.plot(self.twos_comp(data[i], 32), f"{names[i]}", xaxis = "Cycles", yaxis = "Value")

            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_{names[i]}.jpg"))
            self.plot_num += 1

    def plot_fout(self, show, save):
        with open(os.path.join(self.directory, f"calib_output0.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        names = ["Fout1_Real", "Fout1_Imag", "Fout2_Real", "Fout2_Imag", "Fout3_Real", "Fout3_Imag", "Fout4_Real", "Fout4_Imag"]
        for i in range(8):
            fig = self.plot(self.twos_comp(data[i], 32), f"{names[i]}", xaxis = "Cycles", yaxis = "Value")

            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_{names[i]}.jpg"))
            self.plot_num += 1

    def plot_notches(self, ch, show, save):
        with open(os.path.join(self.directory, f"pfb_fpga{ch}_output.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        fig = self.plot_notch(self.twos_comp(data, 32), f"Notch Averager {ch}")

        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_notch{ch}.jpg"))
        self.plot_num += 1

    def plot_notches_multiple(self, num):
        datas = []
        labels = []
        with open(os.path.join(self.directory, f"notch_filter_output.json"), "r") as jsonfile:
            notch_data = json.load(jsonfile)
        for i in range(num):
            datas.append(self.twos_comp(notch_data[f"data{i}"], 32))
            labels.append(f"Cycle{i}")

        fig = self.plot_notch_multiple(datas, labels)
        plt.show()
        plt.close(fig)
        fig.savefig (os.path.join(self.directory, f"multiple_notch_plots.jpg"))

    def plot_notches_multiple_freq(self, num, bin_num):
        datas = []
        labels = []
        with open(os.path.join(self.directory, f"notch_filter_output.json"), "r") as jsonfile:
            notch_data = json.load(jsonfile)
        freq_data = []
        for i in range(num):
            this_iteration = notch_data[f"data{i}"][bin_num]
            freq_data.append(self.twos_comp(this_iteration, 32))

        freq = bin_num * 0.25
        fig = self.plot(freq_data, f"Notch Averager output for bin {bin_num} or {freq} MHz")
        plt.show()
        plt.close(fig)
        fig.savefig (os.path.join(self.directory, f"multiple_notch_plots_{bin_num}.jpg"))

    def plot_notch(self, data, title):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data)):
            x.append(i / 2048 * 100 / 2)
        fig.suptitle(title, fontsize=self.subtitle_size)
        yaxis = "Counts"
        ax.set_ylabel(yaxis, fontsize=self.label_size)
        ax.set_xlabel('MHz', fontsize=self.label_size)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(x, data)
        return fig

    def plot_notch_multiple(self, data, labels):
        fig, ax = plt.subplots()
        #print(data)
        x = []
        for i in range(len(data[0])):
            x.append(i / 2048 * 100 / 2)
        fig.suptitle("Multiple notch1 plots", fontsize=self.subtitle_size)
        yaxis = "Counts"
        ax.set_ylabel(yaxis, fontsize=self.label_size)
        ax.set_xlabel('MHz', fontsize=self.label_size)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        for d,l in zip(data,labels):
            print(d)
            ax.plot(x, d, label = l)
        plt.legend()
        return fig

    def plot_lock_drift(self, show, save):
        with open(os.path.join(self.directory, f"calib_output.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        lock_data = data[8]
        fig = self.plot_lock_power(lock_data)
        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_lock.jpg"))
        self.plot_num += 1

        drift_data = self.from_radian(data[9])
        fig = self.plot_drift(lock_data, drift_data)
        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_drift.jpg"))
        self.plot_num += 1

    def plot_lock_power(self, data):
        lock = [i&0x1 for i in data]
        pwr1 = [(i&0x2) >> 1 for i in data]
        pwr2 = [(i&0x4) >> 2 for i in data]
        pwr3 = [(i&0x8) >> 3 for i in data]
        pwr4 = [(i&0x10) >> 4 for i in data]

        fig, (lock_ax, pwr1_ax, pwr2_ax, pwr3_ax, pwr4_ax) = plt.subplots(nrows=5, ncols=1, sharex=True, figsize=(32, 24))
        axs = [lock_ax, pwr1_ax, pwr2_ax, pwr3_ax, pwr4_ax]
        names = [["No Lock", "Lock"],["No Pwr1", "Pwr1 Used"],["No Pwr2", "Pwr2 Used"],["No Pwr3", "Pwr3 Used"],["No Pwr4", "Pwr4 Used"]]
        datas = [lock, pwr1, pwr2, pwr3, pwr4]

        plt.subplots_adjust(wspace=0, hspace=0, top = 0.90, bottom = 0.1, right = 0.92, left = 0.09)
        fig.suptitle(f"Process Parameters", fontsize = self.title_size)

        for ax, name, dat in zip(axs, names, datas):
            ax.plot(dat)
            ax.set_yticks([0, 1], labels = name)
            ax.set_ylim([-0.5, 1.5])
            ax.tick_params(axis='y', labelsize=self.tick_size)
        ax.set_xlabel("Cycle", fontsize=self.label_size)
        ax.tick_params(axis='x', labelsize=self.tick_size)

        return fig

    def plot_drift(self, lock_data, drift):
        lock = [i&0x1 for i in lock_data]

        fig, drift_ax = plt.subplots()
        fig.suptitle(f"Drift Parameters", fontsize = self.title_size)

        drift_ax.plot(drift)
        if ('upper_guard_calculated_raw' in self.json_data):
            upper = self.json_data['upper_guard_calculated_raw']
        else:
            upper = self.from_radian(self.json_data['input_params']['upper_guard_value'])

        if ('lower_guard_calculated_raw' in self.json_data):
            lower = self.json_data['lower_guard_calculated_raw']
        else:
            lower = self.from_radian(self.json_data['input_params']['lower_guard_value'])

        drift_ax.set_ylim([lower, upper])
        drift_ax.set_ylabel("Drift Angle (radians)", fontsize=self.label_size)
        drift_ax.tick_params(axis='y', labelsize=self.tick_size)
        drift_ax.tick_params(axis='x', labelsize=self.tick_size)
        drift_ax.set_xlabel("Cycle", fontsize=self.label_size)

        def scientific_formatter(val, pos):
            return f'{val:.1e}'
        drift_ax.yaxis.set_major_formatter(FuncFormatter(scientific_formatter))

        lock_ax = drift_ax.twinx()
        lock_ax.plot(lock, linestyle = '--', color = 'red')
        lock_ax.set_yticks([0, 1], labels = ["No Lock", "Lock"])
        lock_ax.tick_params(axis='y', labelsize=self.tick_size)
        lock_ax.set_ylim([-0.1, 1.1])

        return fig

    def plot_topbottom(self, show, save):
        with open(os.path.join(self.directory, f"calib_output.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        names = ["Top1", "Top2", "Top3", "Top4", "Bot1", "Bot2", "Bot3", "Bot4"]
        converted_data = []
        for num, i in enumerate(range(10, 18)):
            fig = self.plot(self.twos_comp(data[i], 32), f"{names[num]}", xaxis = "Cycles", yaxis = "Value")
            converted_data.append(self.twos_comp(data[i], 32))
            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_{names[num]}.jpg"))
            self.plot_num += 1
        fig = self.plot_multiple(converted_data, "All power signals", "Cycles", "Value", names)
        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_all_power.jpg"))
        self.plot_num += 1

    def plot_fdsd(self, show, save):
        with open(os.path.join(self.directory, f"calib_output.json"), "r") as jsonfile:
            calib_data = json.load(jsonfile)
        data = calib_data["data"]
        names = ["FD1", "FD2", "FD3", "FD4", "SD1", "SD2", "SD3", "SD4", "FDX", "SDX"]
        converted_data = []
        for num, i in enumerate(range(18, 28)):
            fig = self.plot(self.twos_comp(data[i], 32), f"{names[num]}", xaxis = "Cycles", yaxis = "Value")
            converted_data.append(self.twos_comp(data[i], 32))
            if (show):
                plt.show()
            else:
                plt.close(fig)

            if (save):
                fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_{names[num]}.jpg"))
            self.plot_num += 1
        fig = self.plot_multiple(converted_data, "All FD-SD signals", "Cycles", "Value", names)
        if (show):
            plt.show()
        else:
            plt.close(fig)

        if (save):
            fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_all_fdsd.jpg"))
        self.plot_num += 1

    def plot_multiple(self, data, title, xaxis = "", yaxis = "", names = []):
        fig, ax = plt.subplots()
        fig.suptitle(title, fontsize = self.title_size)
        ax.set_ylabel(yaxis, fontsize=self.label_size)
        ax.set_xlabel(xaxis, fontsize=self.label_size)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        for d,n in zip(data, names):
            ax.plot(d, label = n)
        plt.legend()
        return fig

    def plot_adc_overlay(self, ch):
        with open(os.path.join(self.directory, f"adc{ch}_output.json"), "r") as jsonfile:
            adc_file = json.load(jsonfile)
        data = self.twos_comp(adc_file["data"], 14)
        #print(f"Max data is {max(data)} and min data is {min(data)}")
        num_repetitions = len(data) // 2048
        #print(f"Overall length is {len(data)}")
        #print(f"Num repetitions is {num_repetitions}")
        orig_max = data[0:2048].index(max(data[0:2048]))
        #print(f"Orig max is {orig_max}")
        adc_data = []
        names = []
        for i in range(num_repetitions):
            adc_data.append(data[i*2048:(i*2048)+2048])
            #this_max = data[i*2048:(i*2048)+2048].index(max(data[i*2048:(i*2048)+2048]))
            #print(f"This max is {this_max}")
            #if (this_max == orig_max):
                #print("So stays the same")
                #adc_data.append(data[i*2048:(i*2048)+2048])
            #else:
                #if (this_max > orig_max):
                    #difference = this_max - orig_max
                #elif (this_max < orig_max):
                    #difference = 2048 - (orig_max - this_max)
                #print(f"So instead of {i*2048} to {(i*2048)+2048}")
                #print(f"We look at {(i*2048)+difference} to {(i*2048)+2048+difference}")
                #adc_data.append(data[(i*2048)+difference:(i*2048)+2048+difference])
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

        fig = self.plot_multiple(adc_data, f"ADC{ch} Overlay", "ADC Counts", "ADC Values", names)
        plt.show()
        plt.close(fig)
        fig.savefig (os.path.join(self.directory, f"plot{self.plot_num}_adc{ch}_overlay.jpg"))

if __name__ == "__main__":
    p = LuSEE_PLOTTING('/u/home/eraguzin/Documents/PF_EVAL_Readout/debug/20240617151543')
    #p.plot_adc_overlay()
    #p.plot_notches(True, True)
    #p.plot_notches_multiple(256)
    print(p.twos_comp(-3 * 3435, 32))
    input("k")
    p.plot_notches_multiple_freq(256, 190)
