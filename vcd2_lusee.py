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

class LuSEE_Integrated_Simulator:
    def __init__(self):
        print("Python --> Welcome to the LuSEE VCD Converter")

    def analyze_file(self, name, signals):
        if (not os.path.isfile(f"{name}")):
            sys.exit(f"Python --> {name} does not exist")
        else:
            print(f"Python --> {name} found")
            self.name = name
            self.sensitivity_list = {}
            self.vals = {}
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
                num_bits = i.var.size
                #Want to create signals that keep the arrays together.
                if reference in self.signals_of_interest:
                    #First time a signal name is found. A key in the master list is made for it as a 1-bit value
                    #And a spot in the value tracker array ismade too
                    val_in = {}
                    val_in['x'] = []
                    val_in['y'] = []
                    val_in['size'] = num_bits
                    val_in['prev'] = None
                    self.vals[reference] = val_in

                    new_sensitive_var = {}
                    new_sensitive_var[id_code] = reference
                    self.sensitivity_list.update(new_sensitive_var)

            #The last line of the preamble/header
            elif (i.kind is TokenKind.ENDDEFINITIONS):
                print (self.vals)
                #print (self.sensitivity_list)
                self.names = list(self.sensitivity_list.values())
                #print(self.names)
                break

    def body(self, write_file = None):
        f = open(write_file, "w")
        writer = csv.writer(f, delimiter=',')
        first_row = self.names.copy()
        first_row.insert(0, 'time')
        writer.writerow(first_row)
        for num,i in enumerate(self.tokens):
            #Unfortunately the only way to check these files is line by line as far as I can tell
            #If the time has changed, check for any values that may have changed in the previous time interval
            #If there is an array, we want the final value to be recorded after all bits of the array have been registered as changed.
            #VCD files end with a time stamp, so this will be the last section read when analyzing a file
            if (i.kind is TokenKind.CHANGE_TIME):
                self.prev_time = self.time
                self.time = int(i.data)
                #print(f"time is now {self.time}")
                #for j in self.vals:
                #    self.vals[j]['x'] = self.time
                if ((self.prev_time%20 == 0) and (int(i.data) > 0)):
                    next_row = [self.prev_time]
                    for i in self.names:
                        next_row.append(self.vals[i]['prev'])
                    writer.writerow(next_row)
            #We're getting the full bit vector here, so we don't need to play the games with a different bit in every line
            elif (i.kind is TokenKind.CHANGE_VECTOR):
                id_code = i.vector_change.id_code
                if id_code in self.sensitivity_list:
                    signal = self.sensitivity_list[id_code]
                    value = i.vector_change.value
                    num_bits = self.vals[signal]['size']
                    converted = self.twos_comp(value, num_bits)
                    #print(converted)
                    #print(f"{value} is {converted}")
                    self.vals[signal]['x'].append(self.time)
                    self.vals[signal]['y'].append(value)
                    self.vals[signal]['prev'] = int(converted)
            #Each line after the time indicates a changed value. See if the changed value is one that is tracked
            elif (i.kind is TokenKind.CHANGE_SCALAR):
                id_code = i.scalar_change.id_code
                if id_code in self.sensitivity_list:
                    signal = self.sensitivity_list[id_code]
                    value = i.scalar_change.value
                    if (len(self.vals[signal]['y']) > 0):
                        prev_value = self.vals[signal]['y'][-1]
                        self.vals[signal]['x'].append(self.prev_time)
                        self.vals[signal]['y'].append(prev_value)
                    self.vals[signal]['x'].append(self.time)
                    self.vals[signal]['y'].append(int(value))
                    self.vals[signal]['prev'] = int(value)

            elif (i.kind is TokenKind.DUMPOFF):
                #For some reason with ModelSim, after you do a `vcd flush` to get the file to disk, it gives final values to every variable as "don't know" or X.
                #So ignore everything after the `vcd flush` command
                break
        f.close()
        #After the file is done, add the last value as the final time tick
        #It helps with analysis later
        #print("vals")
        #for i in self.vals:
        #    print(i)
        print("Python --> Done with VCD body")

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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(f"Error: You need to supply a VCD file, output csv file, and signals to track! You had {len(sys.argv)-1} arguments!")
    vcd_file = sys.argv[1]
    output_file = sys.argv[2]
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
    print(f"Output file is {output_file}")
    print(f"Signals to track are {track}")

    x = LuSEE_Integrated_Simulator()
    x.analyze_file(vcd_file, track)
    x.header()
    x.body(output_file)
    #x.plot()
