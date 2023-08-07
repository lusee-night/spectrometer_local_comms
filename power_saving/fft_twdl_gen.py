#!/usr/bin/env python3
#Script by Eric to take in simulation output of Matlab FFT block and generate more efficient VHDL block

import sys, os, json, subprocess
from vcd.reader import TokenKind, tokenize
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

class LuSEE_fft_gen:
    def __init__(self, config_file):
        print("Python --> Welcome to the LuSEE FFT Twiddle Factor block generator")
        with open(config_file, "r") as jsonfile:
            self.json_data = json.load(jsonfile)

        self.signals_of_interest = {}
        for num,i in enumerate(self.json_data["signals"]):
            listing = {}
            listing['Title'] = self.json_data["signals"][i]['Title']
            self.signals_of_interest[i] = listing
        self.vcd_file = self.json_data["file"]
        self.output = self.json_data["output"]
        self.time_step = self.json_data["time_step"]

    def analyze_file(self):
        if (not os.path.isfile(f"{self.vcd_file}")):
            sys.exit(f"Python --> {self.vcd_file} does not exist")
        else:
            print(f"Python --> {self.vcd_file} found")
            self.name = self.vcd_file
            self.sensitivity_list = {}
            self.pairs = {}
            self.vals = {}
            self.top = None
            self.time = 0
            self.prev_time = 0
            self.plot_num = 0
            f = open(f"{self.vcd_file}", "rb")
            self.tokens = tokenize(f)

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
                if reference in self.signals_of_interest:
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
                #print (self.pairs)
                #print (self.vals)
                #print (self.sensitivity_list)
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
                        x = self.vals[j]['x']
                        y = self.vals[j]['y']

                        lv = self.vals[j]['last_val']

                        x.append(self.prev_time)
                        y.append(lv)

                        self.vals[j]['x'] = x
                        self.vals[j]['y'] = y
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
                    else:
                        print(f"Python --> WARNING: Value for {signal} at time {self.time} is {value}")

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

    def elaborate_vals(self, start, next_index):
        for signal in self.json_data["signals"]:
            desc = self.json_data["signals"][signal]['Title']
            if (desc == "Real" or desc == "Imaginary"):
                time = []
                value = []
                prev_i = start
                first = True
                print(start)
                print(next_index)
                for num,i in enumerate(self.vals[signal]['x'][next_index:]):
                    print("---------")
                    print(num)
                    print(i)
                    if (i == prev_i):
                        time.append(i)
                        value.append(self.vals[signal]['y'][num])
                    else:
                        if ((i - prev_i) != self.time_step):
                            #print(f"Missed time {num} {i} {prev_i}")
                            time_space = i - prev_i
                            if (time_space % self.time_step != 0):
                                sys.exit(f"In iteration {num}, {i}, time step was {time_space}, {self.time_step}")
                            else:
                                iterations = time_space // self.time_step
                                for j in range(iterations-1):
                                    time.append(prev_i + (j * self.time_step))
                                    value.append(self.vals[signal]['y'][num+1])



                            prev_i = i

                        else:
                            time.append(i)
                            value.append(self.vals[signal]['y'][num])
                            prev_i = i

                            print(time)
                            print(value)
                            sys.exit("hi")

                print(time[0:25])
                print(value[0:25])
                sys.exit("here")


    def write_file(self):
        start, next_index = self.find_valid_start()
        self.elaborate_vals(start, next_index)
        #resp = self.find_pattern()
        print(self.vals["twdl_11_1_vld"])

    def find_valid_start(self):
        start = None
        for num, i in enumerate(self.vals["twdl_11_1_vld"]["y"]):
            if (i == 1):
                #print(num)
                start = self.vals["twdl_11_1_vld"]["x"][num]
                break

        #print(start)
        prev_i = 0
        for i in self.vals["twdl_11_1_re"]["x"]:
            if (i > start):
                next_index = self.vals["twdl_11_1_re"]["x"].index(i)
                return start, next_index



if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Error: You need to supply an input config file as the argument! You had {len(sys.argv)-1} arguments!")
    x = LuSEE_fft_gen(sys.argv[1])
    x.analyze_file()
    x.header()
    x.body()
    x.write_file()
