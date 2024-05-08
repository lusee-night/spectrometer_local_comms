import time
import os
import sys
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_BOOTLOADER:
    def __init__(self):
        self.version = 1.00
        self.connection = LuSEE_ETHERNET()
        self.name = "LuSEE Bootloader --> "
        self.debug_file = "lusee_bootloader_operations.txt"

        self.REMAIN = 0xB00000
        self.LOAD_REGION_BASE = 0xB00000

        self.LAUNCH_SW = 0xB00007
        self.GET_PROGRAM_INFO = 0xB00008

        self.DELETE_DEFAULTS = 0xB0000A
        self.WRITE_TO_FLASH = 0xB0000B
        self.WRITE_METADATA = 0xB0000C
        self.DELETE_FLASH_REGION = 0xB0000D
        self.QUICK_DDR_TEST = 0xB0000E
        self.FULL_DDR_TEST = 0xB0000F

        self.last_hex_line = b':00000001FF'
        self.bootloader_flash_enable_reg = 0x630
        self.bootloader_flash_enable_phrase = 0xFEED0000
        self.bootloader_flash_delete_phrase = 0xDEAD0000
        self.bootloader_default_delete_phrase = 0xFACEFEED

        self.bootloader_flash_start_reg = 0x640
        self.bootloader_flash_checksum_reg = 0x621
        self.bootloader_flash_page_reg = 0x620

        self.bootloader_metadata_enable_reg = 0x632
        self.bootloader_metadata_size_reg = 0x630
        self.bootloader_metadata_checksum_reg = 0x631

    #With the type of sensitive bootloader operations we are doing here, it will be good to write the response packets to file
    def write_to_file(self, s):
        f = open(f"{self.debug_file}", 'a+')
        f.writelines(str(s))
        f.write('\n\n')
        f.close()

    #Restarts the C program and gets a confirmation packet that it did
    def init_bootloader(self):
        #Send reset microcontroller packet
        resp = self.connection.send_bootloader_message_response(self.connection.RESET_UC)
        self.write_to_file(resp)
        if (int(resp[0]['BL_Message'], 16) == self.connection.BL_RESET):
            print(f"{self.name}Microcontroller reset")
        else:
            sys.exit(f"{self.name}Microcontroller was not reset. Response was {resp}")
        Send remain in bootloader message
        self.connection.send_bootloader_message(self.REMAIN)

    #NOT IMPLEMENTED IN BOOTLOADER YET
    def remain(self):
        self.connection.send_bootloader_message(self.REMAIN)

    #Loads a specific region into memory, this gets no confirmation packet
    def load_region(self, region):
        self.connection.send_bootloader_message(self.LOAD_REGION_BASE + region)
        print(f"{self.name}Command sent to load region {region}")

    #Launch whatever program has been loaded into memory, and get the confirmation packet
    def launch_software(self):
        resp = self.connection.send_bootloader_message_response(self.LAUNCH_SW)
        self.write_to_file(resp)
        if (resp[0]["default_vals_loaded"]):
            print(f"{self.name}Program jumped to region {resp[0]['region_jumped_to']} with default values loaded")
        else:
            print(f"{self.name}Program jumped to region {resp[0]['region_jumped_to']} with without loading default values")

    #Gets info on all stored programs, and which ones are currently in memory
    def get_program_info(self):
        resp = self.connection.send_bootloader_message_response(self.GET_PROGRAM_INFO)
        self.write_to_file(resp)
        #print(resp)

    #Reads back the program, the full hex file for a comparison
    #NOT IMPLEMENTED YET
    def read_loaded_program(self):
        print("This function is not implemented yet")
        return
        resp = self.connection.send_bootloader_message_response(self.connection.SEND_PROGRAM_TO_DCB)
        print(resp)

    #Deletes the default settings that were used for bootup in the memory. Does not get a confirmation packet
    def delete_spectrometer_defaults(self):
        self.connection.write_reg(self.bootloader_flash_enable_reg, self.bootloader_default_delete_phrase)
        self.connection.send_bootloader_message(self.DELETE_DEFAULTS)
        self.connection.write_reg(self.bootloader_flash_enable_reg, 0)
        print(f"{self.name}Command sent to delete spectrometer defaults {region}")

    #Deletes a certain region of memory. Does not get a confirmation packet
    def delete_region(self, region):
        self.connection.write_reg(self.bootloader_flash_enable_reg, self.bootloader_flash_delete_phrase + region)
        self.connection.send_bootloader_message(self.DELETE_FLASH_REGION + (region << 8))
        print(f"{self.name}Command sent to delete region {region}")
        time.sleep(1) #Without the wait, the next commands don't get registered

    #Begins a quick DDR test, does not get a confirmation packet
    def ddr_quick_test(self):
        self.connection.send_bootloader_message(self.QUICK_DDR_TEST)
        print(f"{self.name}Command sent to begin quick DDR test")

    #Begins a full DDR test, does not get a confirmation packet
    def ddr_full_test(self):
        self.connection.send_bootloader_message(self.FULL_DDR_TEST)
        print(f"{self.name}Command sent to begin full, exhaustive DDR test")

    #Converts from the raw sum total after counting values to the two's complement checksum used in the Intel Hex File format and Jack's bootloader
    #Takes the number of bits to use to convert as well, because Python has to be a pain in the ass about bitwise inversion
    def convert_checksum(self, val, bits):
        mask = 0
        inverse = 0
        for i in range(bits):
            mask += 0x1 << i
            original_bit = ((0x1 << i) & val) >> i
            if (original_bit):
                new_bit = 0
            else:
                new_bit = 1
            inverse += new_bit << i
        return (inverse + 1) & mask

    #Check that the line read from the hex file conforms to Intel Hex Format: https://en.wikipedia.org/wiki/Intel_HEX
    def hex_line_error_checking(self, num, line):
        #Check basic conformance
        if (len(line) < 3):
            sys.exit(f"Line {num} of file {self.file_path} has a length of {len(line)}, the full line is {line}")
        if (line[0:1] != bytes(":","utf-8")):
            sys.exit(f"Line {num} of file {self.file_path} does not start with a ':', it starts with a {line[0:1]}")

        #Valid data starts after the initial colon and goes until before the last 2 nibbles, which are the line checksum
        #More details here: https://en.wikipedia.org/wiki/Intel_HEX#Checksum_calculation
        line_length = len(line[1:-2])
        #len() gives you length in nibbles, we want bytes
        bytes_length = int(line_length/2)

        #This starts after the colon and takes two consecutive nibbles at a time and converts them to their integer values, and stops before the line checksum
        val = [int(line[1+(j*2):1+(j*2)+2], 16) for j in range(bytes_length)]
        running_sum = sum(val)
        calculated_checksum = self.convert_checksum(running_sum, 8)

        #Last 2 characters are the 8 bit checksum, interpreted as hex
        line_checksum = int(line[-2:], 16)

        if (calculated_checksum != line_checksum):
            sys.exit(f"Line {num} of file {self.file_path} has a calculated checksum of {hex(calculated_checksum)} and a checksum at the end of the line of {hex(line_checksum)}. The total line is {line}")

    #Open a file in Intel Hex Format and create the array to write to FPGA: https://en.wikipedia.org/wiki/Intel_HEX
    def open_file(self):
        if (not os.path.isfile(self.file_path)):
            sys.exit(f"The given path {self.file_path} is not a valid file. Point to a microcontroller hex file")
        f = open(self.file_path, mode="rb")
        lines = f.read().splitlines() #Because line usually ends with \r\n

        #We will end up with an array of 32 bit integers, because that's how all this data is written to the FPGA registers
        write_array = []
        for num,i in enumerate(lines):
            self.hex_line_error_checking(num, i)
            #Part of Intel Hex Format
            line_type = int(i[1:3])
            if (line_type == 10):
                line_number = int(i[2:6], 16)
                if (line_number != num):
                    sys.exit(f"The binary file's line number was {line_number} but the program was at line {num}")
                #In a normal data line, there are 4 sets of 32 bit integers
                for j in range(4):
                    #First I grab them as 8 byte, two nibble values. The first 9 bits are the : character and the line number
                    four_bytes = [int(i[9+(j*8)+(k*2):9+(j*8)+(k*2)+2], 16) for k in range(4)]
                    #Then I rearrange them because that's what the SPI Flash calls for
                    rearranged_bytes = (four_bytes[3] << (8*3)) + (four_bytes[2] << (8*2)) + (four_bytes[1] << 8) + (four_bytes[0])
                    write_array.append(rearranged_bytes)
            #Jack includes this line that's written in the hex file, don't know if we need to. It doesn't have the line number
            elif (line_type == 4):
                four_bytes = [int(i[9+(k*2):9+(k*2)+2], 16) for k in range(4)]
                rearranged_bytes = (four_bytes[3] << (8*3)) + (four_bytes[2] << (8*2)) + (four_bytes[1] << 8) + (four_bytes[0])
                write_array.append(rearranged_bytes)
            elif (i != self.last_hex_line):
                sys.exit(f"Line {num} of file {self.file_path} should be the final line. Instead of being {self.last_hex_line}, it's {i}")
        return write_array

    #Gets the rearranged hex file, and writes it to the FPGA microcontroller line by line to write it to memory
    def write_hex_bootloader(self, region):
        write_array = self.open_file()
        print(f"{self.name}Rearranged the input file: {self.file_path}")
        array_length = len(write_array)  #Total number of 32 bit chunks
        pages = array_length // 64 #Each page in Flash is 64 of these 32 bit chunks, for 256 bytes (2048 bits) total
        leftover = array_length % 64 #The last page may not be filled, so we need to know when to start padding 0s
        program_size = len(write_array)
        program_checksum = self.convert_checksum(sum(write_array), 32)
        print(f"{self.name}Program size is {hex(program_size)} and program checksum is {hex(program_checksum)}")

        self.connection.write_reg(self.bootloader_flash_enable_reg, self.bootloader_flash_enable_phrase + region)
        #Run through all full pages
        for i in range(pages):
            print(f"{self.name}Writing page {i}/{pages}")
            page = write_array[i*64:(i+1)*64]
            self.write_hex_page(page, i, region)
        #And do the final partial page if necessary
        if (leftover):
            print(f"{self.name}Writing page {pages}/{pages}")
            #Fill the rest of this partial page with 0s
            final_page = write_array[pages*64:]
            filled_zeros = [0] * (64-leftover)
            final_page.extend(filled_zeros)
            self.write_hex_page(final_page, pages, region)

        self.connection.write_reg(self.bootloader_flash_enable_reg, 0)

        #Write all the metadata
        self.connection.write_reg(self.bootloader_metadata_enable_reg, self.bootloader_flash_enable_phrase + region)
        self.connection.write_reg(self.bootloader_metadata_size_reg, program_size)
        self.connection.write_reg(self.bootloader_metadata_checksum_reg, program_checksum)
        self.connection.send_bootloader_message(self.WRITE_METADATA + (region << 8))

        self.connection.write_reg(self.bootloader_metadata_enable_reg, 0)

    #Writes the given page with the necessary info
    def write_hex_page(self, page, page_num, region):
        #Jack does 16 bit checksums for each page, so I need to split the 32 bit int to add it for the running checksum
        running_sum = 0
        for num,chunk in enumerate(page):
            running_sum += chunk & 0xFFFF
            running_sum += (chunk & 0xFFFF0000) >> 16
            self.connection.write_reg(self.bootloader_flash_start_reg + num, chunk)

        print(f"{self.name}Page {page_num} checksum is {hex(self.convert_checksum(running_sum, 16))}")
        self.connection.write_reg(self.bootloader_flash_checksum_reg, self.convert_checksum(running_sum, 16))
        self.connection.write_reg(self.bootloader_flash_page_reg, page_num)
        self.connection.send_bootloader_message(self.WRITE_TO_FLASH + (region << 8))

    #Because Jack has not implemented the the fix for the bootloader's incorrect calculation of program size and checksum, we may need to use this
    def write_incorrect_metadata(self, region):
        #Write all the metadata
        self.connection.write_reg(self.bootloader_metadata_enable_reg, self.bootloader_flash_enable_phrase + region)
        self.connection.write_reg(self.bootloader_metadata_size_reg, 0xBBBB)
        self.connection.write_reg(self.bootloader_metadata_checksum_reg, 0xAAAAAAAA)
        self.connection.send_bootloader_message(self.WRITE_METADATA + (region << 8))

        self.connection.write_reg(self.bootloader_metadata_enable_reg, 0)


if __name__ == "__main__":
    #arg = sys.argv[1]
    boot = LuSEE_BOOTLOADER()
    boot.init_bootloader()
    #time.sleep(0.1)
    boot.remain()
    #boot.get_program_info()
    #boot.load_region(region = 1)
    #boot.get_program_info()
    #boot.read_loaded_program()
    #boot.ddr_quick_test()

    boot.file_path = sys.argv[1]
    boot.delete_region(region = 1)
    #time.sleep(3) #Have to add this because Jack gives us no feedback as to when the delete is finished
    boot.write_hex_bootloader(region = 1)
    #boot.write_incorrect_metadata(region = 1)

    #boot.launch_software()
