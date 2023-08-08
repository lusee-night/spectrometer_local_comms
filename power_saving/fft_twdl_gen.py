#!/usr/bin/env python3
#Script by Eric to take in simulation output of Matlab FFT block and generate more efficient VHDL block

import sys, os, json, subprocess
from vcd.reader import TokenKind, tokenize
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import math

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
        self.num = int(self.json_data["num"])
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

    def write_file(self):
        start, re_index, im_index = self.find_valid_start()
        #print(re_index)
        #print(im_index)
        re, im = self.elaborate_vals(start, re_index, im_index)
        resp = self.find_pattern(re["y"])
        #print(resp)
        #print(re["y"][:resp])
        self.make_vhdl_file(re["y"], im["y"], resp)

    def find_valid_start(self):
        start = None
        for i in self.json_data["signals"]:
            #print(i)
            title = (self.json_data["signals"][i]['Title'])
            if (title == "Real"):
                real = self.vals[i]
            elif (title == "Imaginary"):
                im = self.vals[i]
            elif (title == "Valid"):
                valid = self.vals[i]

        for num, i in enumerate(valid["y"]):
            if (i == 1):
                #print(num)
                start = valid["x"][num]
                break

        #print(start)
        prev_i = 0
        for i in real["x"]:
            if (i > start):
                re_index = real["x"].index(i)
                break

        for i in im["x"]:
            if (i > start):
                im_index = im["x"].index(i)
                break

        return start, re_index, im_index

    def elaborate_vals(self, start, re_index, im_index):
        for signal in self.json_data["signals"]:
            desc = self.json_data["signals"][signal]['Title']
            if (desc == "Real" or desc == "Imaginary"):
                time = []
                value = []
                prev_i = start
                first = True
                if (desc == "Real"):
                    next_index = re_index
                elif (desc == "Imaginary"):
                    next_index = im_index
                #print(self.vals[signal]['x'][:25])
                #print(self.vals[signal]['y'][:25])
                for num,i in enumerate(self.vals[signal]['x'][next_index:]):
                    num = num + next_index
                    #print(num)
                    #print(i)
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
                                #The first time, there was no original appending of that value. For the subsequent times, the repeated value
                                #Is posted once before we notice that there was a gap in time
                                if (first):
                                    first = False
                                    for j in range(iterations):
                                        time.append(prev_i + (j * self.time_step))
                                        value.append(self.vals[signal]['y'][num-1])
                                else:
                                    for j in range(iterations-1):
                                        time.append(prev_i + ((j+1) * self.time_step))
                                        value.append(self.vals[signal]['y'][num-1])

                                time.append(i)
                                value.append(self.vals[signal]['y'][num])

                            prev_i = i
                            #print(time)
                            #print(value)
                            #sys.exit("yo")
                        else:
                            time.append(i)
                            value.append(self.vals[signal]['y'][num])
                            prev_i = i

                if (desc == "Real"):
                    real = {"x":time, "y":value}
                elif (desc == "Imaginary"):
                    im = {"x":time, "y":value}

        return real, im

    def find_pattern(self, vals):
        max_len = len(vals) / 2
        for x in range(2, int(max_len)):
            if (vals[0:x] == vals[x:2*x]) :
                #Make sure it's not the beginning where all the values are the same
                if (vals[0:x].count(vals[0]) != len(vals[0:x])):
                    print(f"Python --> Matched with {vals[x:2*x]}")
                    return x

    def make_vhdl_file(self, re, im, index):
        real_string = ""
        for i in re[:index]:
            real_string += f"x\"{i:08X}\", "
        real_string = real_string[:-2]

        im_string = ""
        for i in im[:index]:
            im_string += f"x\"{i:08X}\", "
        im_string = im_string[:-2]


        total_string = f"""
--------------------------------------------------------------------------------
-- Company: Brookhaven National Laboratory
-- Eric Raguzin
-- LuSEE
-- Automatically generated Twiddle factor file based on Matlab output simulation
--
-- File: TWDLROM_{self.num}_1_array.vhd
-- File history:
--      <Revision number>: <Date>: <Comments>
--      <Revision number>: <Date>: <Comments>
--      <Revision number>: <Date>: <Comments>
--
-- Description:
--
-- This block was generated using a VCD file output from a simulation that was run by a Matlab generated FFT
-- The Python script looked for the repeating twiddle factors that were outputs and condensed it to this VHDL block
--
--------------------------------------------------------------------------------

library IEEE;
USE ieee.std_logic_1164.all;
USE ieee.std_logic_arith.all;
USE ieee.std_logic_unsigned.all;

entity TWDLROM_{self.num}_1_array is
    PORT(   clk                               :   IN    std_logic;
            reset                             :   IN    std_logic;
            enb                               :   IN    std_logic;
            dout_{self.num-1}_1_vld                     :   IN    std_logic;
            softReset                         :   IN    std_logic;
            twdl_{self.num}_1_re                      :   OUT   std_logic_vector(31 DOWNTO 0);  -- sfix32_En30
            twdl_{self.num}_1_im                      :   OUT   std_logic_vector(31 DOWNTO 0);  -- sfix32_En30
            twdl_{self.num}_1_vld                     :   OUT   std_logic
            );
end TWDLROM_{self.num}_1_array;

architecture architecture_TWDLROM_{self.num}_1_array of TWDLROM_{self.num}_1_array is

type TWDLROM_{self.num}_CONSTANTS is array (0 TO {index-1}) OF std_logic_vector(31 downto 0);

constant TWDLROM_{self.num}_re : TWDLROM_{self.num}_CONSTANTS := ({real_string});

constant TWDLROM_{self.num}_im : TWDLROM_{self.num}_CONSTANTS := ({im_string});


SIGNAL Valid_s1          : std_logic;
SIGNAL Valid_s2          : std_logic;
SIGNAL index             : std_logic_vector({int(math.log2(index)-1)} downto 0);

begin

PROCESS (clk, reset)
BEGIN
    IF reset = '1' THEN
        Valid_s1          <= '0';
        Valid_s2          <= '0';
        twdl_{self.num}_1_vld     <= '0';
        twdl_{self.num}_1_re      <= x"00000000";
        twdl_{self.num}_1_im      <= x"00000000";
        index             <= x"0";
    ELSIF clk'EVENT AND clk = '1' THEN
        Valid_s1          <= dout_{self.num-1}_1_vld;
        Valid_s2          <= Valid_s1;
        twdl_{self.num}_1_re      <= TWDLROM_{self.num}_re(CONV_INTEGER(unsigned(index)));
        twdl_{self.num}_1_im      <= TWDLROM_{self.num}_im(CONV_INTEGER(unsigned(index)));
        twdl_{self.num}_1_vld     <= Valid_s2;
        if(Valid_s2 = '1') then
            index  <= index + 1;
        end if;
    END IF;
END PROCESS;

end architecture_TWDLROM_{self.num}_1_array;
        """

        with open(f"TWDLROM_{self.num}_1_array.vhd", "w") as text_file:
            text_file.write(total_string)

        print(total_string)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Error: You need to supply an input config file as the argument! You had {len(sys.argv)-1} arguments!")
    x = LuSEE_fft_gen(sys.argv[1])
    x.analyze_file()
    x.header()
    x.body()
    x.write_file()
    print("Python --> Done!")
