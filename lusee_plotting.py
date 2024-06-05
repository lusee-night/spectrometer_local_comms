import os
import json

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

class LuSEE_PLOTTING:
    def __init__(self, directory):
        self.version = 1.0
        self.prefix = "LuSEE Plotting --> "
        self.tick_size = 22
        self.title_size = 32
        self.subtitle_size = 20
        self.label_size = 14
        self.plot_num = 0

        self.directory = directory

        with open(os.path.join(self.directory, "output.json"), "r") as jsonfile:
            self.json_data = json.load(jsonfile)

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
