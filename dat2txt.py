import csv
import sys
import os
#Program to convert Emi's data for the signal generator in CSV format
#to a text file that the VHDL test bench can easily read
#Includes a section that does two's complement in Python3, which will be nice to reuse
file_in = sys.argv[1]
file_out = sys.argv[2]
fullpath = os.path.join(os.getcwd(), file_in)
with open(fullpath) as csvfile:
    reader = csv.reader(csvfile, delimiter=' ')
    vals = []
    for row in reader:
        vals.append(row[1])


vals.pop(0)
vals.pop(-1)
#print(vals)

with open(sys.argv[2], 'w') as the_file:
    for i in vals:
        print("--")
        j = int(float(i))
        #Convert's negative number to two's complement
        if (j < 0):
            print(j)
            j = (16383 + 1 - abs(j))
            print(j)
            print(hex(j))
        hex_str = f"{j:04x}"
        print(hex_str)
        the_file.write(f"{hex_str}\n")
