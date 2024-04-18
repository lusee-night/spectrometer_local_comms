import time
import os
import sys
import struct
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_BOOTLOADER:
    def __init__(self):
        self.version = 1.00
        self.connection = LuSEE_ETHERNET()

        self.UC_REG = 0x100

        self.REMAIN = 0xB00000
        self.LOAD_REGION_1 = 0xB00001
        self.LOAD_REGION_2 = 0xB00002
        self.LOAD_REGION_3 = 0xB00003
        self.LOAD_REGION_4 = 0xB00004
        self.LOAD_REGION_5 = 0xB00005
        self.LOAD_REGION_6 = 0xB00006

        self.LAUNCH_SW = 0xB00007
        self.GET_PROGRAM_INFO = 0xB00008
        self.SEND_PROGRAM_TO_DCB = 0xB00009
        self.DELETE_DEFAULTS = 0xB0000A
        self.WRITE_TO_FLASH = 0xB0000B
        self.WRITE_METADATA = 0xB0000C
        self.DELETE_FLASH_REGION = 0xB0000D
        self.QUICK_DDR_TEST = 0xB0000E
        self.FULL_DDR_TEST = 0xB0000F

    def init_bootloader(self):
        #Send reset microcontroller packet
        self.connection.write_reg(self.UC_REG, 1)
        self.connection.write_reg(self.UC_REG, 0)
        #Check that bootloader init packet comes in
        time.sleep(1)
        resp = self.connection.receive_bootloader_message()
        print(resp)
        #Send remain in bootloader message
        self.connection.send_bootloader_message(self.REMAIN)

    def remain(self):
        self.connection.send_bootloader_message(self.REMAIN)

    def get_program_info(self):
        self.connection.send_bootloader_message(self.GET_PROGRAM_INFO)
        #resp = self.connection.receive_bootloader_message()
        print(resp)

    def open_file(self, path):
        if (not os.path.isfile(path)):
            sys.exit(f"The given path {path} is not a valid file. Point to a microcontroller hex file")
        f = open(path, mode="rb")
        lines = f.readlines()

        write_array = bytearray()
        for num,i in enumerate(lines):
            print(len(i))
            if (len(i) < 3):
                sys.exit(f"Line {num} of file {path} has a length of {len(i)}, the full line is {i}")
            if (i[0:1] != bytes(":","utf-8")):
                sys.exit(f"Line {num} of file {path} does not start with a ':', it starts with a {i[0:1]}")
            line_type = int(struct.unpack('c', i[1:2])[0])
            if (line_type == 1):
                print("data line")
                line_number = int(i[2:6].decode('ascii'))
                if (line_number != num):
                    sys.exit(f"The binary file's line number was {line_number} but the program was at line {num}")
                for j in range(4):
                    resp = struct.unpack_from('>4H', i, 9 + (8*j))
                    print(resp)
                    for k in resp:
                        print(hex(k))
                    rearranged_bytes = struct.pack('>H', resp[3]) + struct.pack('>H', resp[2]) + struct.pack('>H', resp[1]) + struct.pack('>H', resp[0])
                    print(rearranged_bytes)
                    write_array += rearranged_bytes
            else:
                sys.exit(f"Error, second byte of line was {line_type}. Valid types are '1' for a data line,")
            if (num == 2):
                print(write_array)
                sys.exit(f"ok{path}")

        first = data[0][9:17]
        print(len(first))
        print(first)
        # Unpack the original bytes object
        original_bytes = b'12345678'
        print(len(original_bytes))
        print(original_bytes[:4])
        unpacked_data = struct.unpack('>4H', original_bytes)

        # Pack the unpacked data in little-endian format with 4 bytes and concatenate them
        rearranged_bytes = struct.pack('>H', unpacked_data[3]) + struct.pack('>H', unpacked_data[2]) + struct.pack('>H', unpacked_data[1]) + struct.pack('>H', unpacked_data[0])
        print(rearranged_bytes)

if __name__ == "__main__":
    #arg = sys.argv[1]
    boot = LuSEE_BOOTLOADER()
    #boot.init_bootloader()
    #boot.remain()
    #boot.get_program_info()
    boot.open_file(sys.argv[1])
