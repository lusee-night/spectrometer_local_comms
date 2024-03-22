#!/usr/bin/env python3
#Script by Eric to take VCD output from Identify and convert certain signals to a CSV
#The VCD format from Identify puts vectors on the same line instead of separately bit by bit
#So the analysis is different here than the ModelSim VCD analyzers.
#You tell it which signals to write to CSV through the command line
import sys, os, json, subprocess
from vcd.reader import TokenKind, tokenize
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import csv
import pprint

class LuSEE_Calibration_Test:
    def analyze_file(self, name, signals):
        if (not os.path.isfile(f"{name}")):
            sys.exit(f"Python --> {name} does not exist")
        else:
            print(f"Python --> {name} found")
            self.name = name
            self.sensitivity_list = {}
            self.vals = {}
            self.pairs = {}
            self.top = None
            self.time = 0
            self.prev_time = 0
            self.plot_num = 0
            f = open(f"{name}", "rb")
            self.tokens = tokenize(f)

        self.signals_of_interest = signals

    def header(self):
        for num,i in enumerate(self.tokens):
            #Still in the preamble. It's getting header data and signal definitions.
            if (i.kind is TokenKind.TIMESCALE):
                self.time_magnitude = i.timescale.magnitude.value
                self.timescale = i.timescale.unit.value

            elif (i.kind is TokenKind.SCOPE):
                self.top = i.scope.ident

            elif (i.kind is TokenKind.VAR):
                id_code = i.var.id_code
                reference = i.var.reference
                bit_index = i.var.bit_index
                array_type = type(bit_index)
                #This means it's an array of an array, so like $var wire 1 " pks_ref [0][12] $end
                #This correction assumes you can only have double nested arrays. It will have to be fixed if you can have triple or higher
                if array_type is tuple:
                    reference = f"{reference}_{bit_index[0]}"
                    bit_index = bit_index[1]
                #Want to create signals that keep the arrays together.
                if reference not in self.pairs:
                    #First time a signal name is found. A key in the master list is made for it as a 1-bit value
                    #And a spot in the value tracker array ismade too
                    key_in = {}
                    key_in[id_code] = bit_index
                    key_in['bits'] = 1
                    self.pairs[reference] = key_in

                    val_in = {}
                    val_in['x'] = []
                    val_in['y'] = []
                    val_in['last_val'] = 0
                    val_in['modified'] = False
                    self.vals[reference] = val_in

                else:
                    #This means this key is part of an array, the extra bit and indicator is added to the master list
                    key_in = {}
                    key_in[id_code]=bit_index
                    key_in['bits'] = self.pairs[reference]['bits'] + 1
                    self.pairs[reference].update(key_in)

                new_sensitive_var = {}
                new_sensitive_var[id_code] = reference
                self.sensitivity_list.update(new_sensitive_var)

            #The last line of the preamble/header
            elif (i.kind is TokenKind.ENDDEFINITIONS):
                #self.pp.pprint (self.pairs)
                #self.pp.pprint (self.vals)
                #self.pp.pprint (self.sensitivity_list)
                break

    def body(self):
        for num,i in enumerate(self.tokens):
            #Unfortunately the only way to check these files is line by line as far as I can tell
            #If the time has changed, check for any values that may have changed in the previous time interval
            #If there is an array, we want the final value to be recorded after all bits of the array have been registered as changed.
            #VCD files end with a time stamp, so this will be the last section read when analyzing a file
            if (i.kind is TokenKind.CHANGE_TIME):
                self.prev_time = self.time
                self.time = int(i.data)
                for j in self.pairs:
                    if (self.vals[j]['modified'] == True):
                        lv = self.vals[j]['last_val']
                        self.vals[j]['x'].append(self.prev_time)
                        self.vals[j]['y'].append(f"{lv:08x}")
                        self.vals[j]['modified'] = False

            #Each line after the time indicates a changed value. See if the changed value is one that is tracked
            elif (i.kind is TokenKind.CHANGE_SCALAR):
                id_code = i.scalar_change.id_code
                if id_code in self.sensitivity_list:
                    signal = self.sensitivity_list[id_code]
                    sublist = self.pairs[signal]
                    previous_val = self.vals[signal]['last_val']
                    bit = sublist[id_code]
                    value = i.scalar_change.value
                    #Update most recent value of that array for that bit with the specified value
                    if (value == '0'):  #Is there a better way to deal with don't cares?
                        val = 0
                        if (bit == None):
                            previous_val = val
                        else:
                            #To change a single bit to a 0, need to AND with a mask of 1s with a 0 in the desired bit location
                            inverse_mask = 1 << bit
                            mask = ~inverse_mask
                            previous_val = previous_val & mask
                    elif (value == '1'):
                        val = 1
                        if (bit == None):
                            previous_val = val
                        else:
                            #To add a 1, simple to use OR
                            previous_val = previous_val | (val << bit)
                    # else:
                    #     print(f"Python --> WARNING: Value for {signal} at time {self.time} is {value}")

                    #Keep this value in case the next line has the next bit of the array
                    #Mark it so that this value gets saved at the end of the time tick
                    self.vals[signal]['last_val'] = previous_val
                    self.vals[signal]['modified'] = True

            elif (i.kind is TokenKind.DUMPOFF):
                #For some reason with ModelSim, after you do a `vcd flush` to get the file to disk, it gives final values to every variable as "don't know" or X.
                #So ignore everything after the `vcd flush` command
                break

        #After the file is done, add the last value as the final time tick
        #It helps with analysis later
        for i in self.vals:
            self.vals[i]['x'].append(self.time)
            self.vals[i]['y'].append(self.vals[i]['last_val'])

        print("Python --> Done with VCD body")
    def output(self):
        for i in self.vals:
            time_list = self.vals[i]['x']
            val_list = self.vals[i]['y']
            print(f"Scanning {i} to array")
            #Finding when this signal reaches the start time
            prev_j = 0
            index = None
            for num,j in enumerate(time_list):
                print(j)
                if (j >= self.start_time):
                    index = num
                    break
                prev_j = j
            if (index == None):
                sys.exit(f"Scanned {i} until {prev_j}, but no time reached {self.start_time}. Index is {index}")

            #Now that we have the start time, build the array of relevant data
            output = []
            time = self.start_time
            next_event = time_list[index]
            while (time <= self.end_time):
                if (next_event == time):
                    output.append(val_list[index])
                    index += 1
                    next_event = time_list[index]
                elif (next_event > time):
                    output.append(val_list[index-1])
                else:
                    sys.exit(f"Somehow, for {i}, the next event at {next_event}, index {index} is less than the current time of {time}")

                time += self.time_tick

            with open(f"{i}_proc.dat", "w") as f:
                f.writelines(x + '\n' for x in output)
    def plot(self):
        #Find where fft_ready goes from 0 to 1
        to_check = self.vals['fft_ready']['y']
        check = 0
        for num,i in enumerate(to_check):
            if (check == 0):
                if (i == 0):
                    check = 1
            elif (check == 1):
                if (i == 1):
                    start_index = num
                    check = 2
            elif (check == 2):
                if (i == 0):
                    end_index = num
                    break
        time_start = self.vals['fft_ready']['x'][start_index]
        time_end = self.vals['fft_ready']['x'][end_index]
        print(f"FFT ready goes high at {time_start} and goes low at {time_end}")

        bin_slice = self.get_values_between_time(self.vals['bin']['x'], self.vals['bin']['y'], time_start, time_end)
        real_slice = self.get_values_between_time(self.vals['ch1_val_re']['x'], self.vals['ch1_val_re']['y'], time_start, time_end)

        fig, ax = plt.subplots()

        #title = self.signals_of_interest["pks0"]["Title"]
        fig.suptitle("here", fontsize = 20)
        ax.set_ylabel("here2", fontsize=14)
        #ax.set_yscale('log')
        ax.set_xlabel('MHz', fontsize=14)
        ax.ticklabel_format(style='plain', useOffset=False, axis='x')
        ax.plot(bin_slice, real_slice)
        plt.show()

    def get_values_between_time(self, x, y, start, end):
        check_start = True
        for num,i in enumerate(x):
            if (check_start == True):
                if i >= start:
                    start_index = num
                    check_start = False
            if i >= end:
                end_index = num
                break
        value_slice = []
        for i in range(start_index, end_index, 1):
            value_slice.append(y[i])
        return(value_slice)

    def twos_comp(self, val, bits):
        """compute the 2's complement of int value val"""
        if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
            val = val - (1 << bits)        # compute negative value
        return val                         # return positive value as is

    def __init__(self):
        print("Python --> Welcome to the LuSEE VCD Converter")
        self.pp = pprint.PrettyPrinter(indent=4)
        self.start_time = 2673450000
        self.end_time = 2878250000
        self.time_tick = 100000

if __name__ == "__main__":
    #Start was 20644000 ns
    #End was   20966800 ns
    #Time tick is 10 ns
    if len(sys.argv) < 1:
        sys.exit(f"Error: You need to supply a VCD file and signals to track! You had {len(sys.argv)-1} arguments!")
    vcd_file = sys.argv[1]
    error = 0
    i = 3
    track = []
    while (error == 0):
        try:
            track.append(sys.argv[i])
        except:
            break
        i += 1
    print(f"Reading {vcd_file}")
    print(f"Signals to track are {track}")

    x = LuSEE_Calibration_Test()
    x.analyze_file(vcd_file, track)
    x.header()
    x.body()
    x.output()
