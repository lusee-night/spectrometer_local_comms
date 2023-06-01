#ModelSim outputs arrays as:
#$var wire 1 " pks_ref [0][12] $end
#Whereas pyvcd is expecting to see:
#$var wire 1 " pks_ref [0:12] $end
#https://github.com/westerndigitalcorporation/pyvcd/blob/ecaa5bf0faebeb34a5b0eead41a0ad8c73abb8b4/vcd/reader.py#L415
#This script cleans up the VCD output of ModelSim to put it in the format pyvcd expects
import sys, os
if __name__ == "__main__":
    print(f"Input file is {sys.argv[1]}")
    print(f"Output file is {sys.argv[2]}")

    file1 = open(os.path.join(os.getcwd(), sys.argv[1]), 'r')
    Lines = file1.readlines()
    file1.close()

    file2 = open(os.path.join(os.getcwd(), sys.argv[2]), 'w')
    for len, i in enumerate(Lines):
        #print(i.strip())
        new_line = i.replace("][", ":")
        file2.write(new_line)

    file2.close()
    print("Done")
