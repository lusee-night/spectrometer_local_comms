import time
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_COMMS:
    def __init__(self):
        self.version = 1.0

        self.connection = LuSEE_ETHERNET()

        self.readout_modes = {
            "FFT1": 0,
            "ADC1": 1,
            "ADC2": 2,
            "ADC3": 3,
            "ADC4": 4,
            "Counter": 5,
            "FFT2": 6,
            "FFT3": 7,
            "FFT4": 8
            }

        self.fft_sel = {
            "A1": 0,
            "A2": 1,
            "A3": 2,
            "A4": 3,
            "X12R": 4,
            "X12I": 5,
            "X13R": 6,
            "X13I": 7,
            "X14R": 8,
            "X14I": 9,
            "X23R": 10,
            "X23I": 11,
            "X24R": 12,
            "X24I": 13,
            "X34R": 14,
            "X34I": 15
            }

        self.ADC_PACKETS = 9
        self.FFT_PACKETS = 3
        self.tries = 5
        self.bytes_per_packet = 0x7F8
        self.counter_num = None

        self.cycle_time = 40e-6
        self.avg = 0

        self.wait_time = 0.025
        self.readout_register = 0x1
        self.adc_function = 0x2
        self.adc_reg_data = 0x3
        self.action_register = 0x4
        self.counter_register = 0x5
        self.function_register = 0x6
        self.reset_fifo_reg = 0x7
        self.spectrometer_status = 0x9
        self.fft_select = 10

        self.mux_reg = 20
        self.main_average = 21
        self.notch_average = 22
        self.sticky_error = 23
        self.notch_reg = 24

        self.corr_array1 = 25
        self.corr_array2 = 26
        self.corr_array3 = 27

        self.notch_array1 = 28
        self.notch_array2 = 29
        self.notch_array3 = 30

    #Only need to do one in the beginning
    #Takes a few seconds
    def reset(self):
        self.connection.reset()

    def reset_adc(self, adc):
        self.connection.write_reg(self.adc_function, 0x10 << int(adc))
        self.connection.write_reg(self.adc_function, 0x0)

    def write_adc(self, adc, reg, data):
        #print(f"Reg is {reg} and data is {hex(data)}")
        val = data & 0xFF
        reg_num = reg & 0xFF
        final_val = reg_num + (val << 8)
        #print(f"sending {hex(final_val)}")
        self.connection.write_reg(self.adc_reg_data, final_val)
        time.sleep(self.wait_time)
        self.connection.write_reg(self.adc_function, 1 << int(adc))
        time.sleep(self.wait_time)
        self.connection.write_reg(self.adc_function, 0)
        time.sleep(self.wait_time)

    def read_adc(self, adc, reg):
        self.write_adc(adc, 0, 1)
        self.write_adc(adc, reg, 0)
        resp = self.connection.read_reg(self.adc_reg_data)
        self.write_adc(adc, 0, 0)

        #print(hex(resp))
        if (adc == 0):
            return (0xFF0000 & int(resp)) >> 16
        elif (adc == 1):
            return (0xFF000000 & int(resp)) >> 24
        else:
            return int(resp)

    def set_function(self, function):
        try:
            val = self.readout_modes[function]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use a function listed in {self.readout_modes}")
            print(f"You inputted {function}")
            return

        self.connection.write_reg(self.function_register, val)

    def readout_mode(self, mode):
        if (mode == "fpga"):
            self.connection.write_reg(self.readout_register, 1)
        elif (mode == "sw"):
            self.connection.write_reg(self.readout_register, 0)
        else:
            print(f"Python LuSEE Comm --> You need to use a readout method of 'fpga' or 'sw', you used {mode}")

    def set_counter_num(self, num):
        self.counter_num = int(num)
        self.connection.write_reg(self.counter_register, int(num))

    def reset_all_fifos(self):
        self.connection.write_reg(self.reset_fifo_reg, 1)
        self.connection.write_reg(self.reset_fifo_reg, 0)

    def load_adc_fifos(self):
        self.connection.write_reg(self.action_register, 2)
        self.connection.write_reg(self.action_register, 0)

    def load_fft_fifos(self):
        self.connection.write_reg(self.action_register, 4)
        self.connection.write_reg(self.action_register, 0)

    def start_spectrometer(self):
        self.connection.write_reg(self.spectrometer_status, 1)

    def stop_spectrometer(self):
        self.connection.write_reg(self.spectrometer_status, 0)

    def select_fft(self, fft_style):
        try:
            val = self.fft_sel[fft_style]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use an FFT choice listed in {self.fft_sel}")
            print(f"You inputted {fft_style}")
            return

        self.connection.write_reg(self.fft_select, val)

    def set_main_average(self, avg):
        avg_num = int(avg)
        self.avg = avg_num
        self.connection.write_reg(self.main_average, avg_num)

    def set_notch_average(self, avg):
        avg_num = int(avg)
        self.connection.write_reg(self.notch_average, avg_num)

    def set_sticky_error(self, sticky):
        stick = int(sticky)
        self.connection.write_reg(self.sticky_error, stick)

    def notch_filter_on(self):
        self.connection.write_reg(self.notch_reg, 1)

    def notch_filter_off(self):
        self.connection.write_reg(self.notch_reg, 0)

    def set_index_array(self, fft, val, index_type):
        try:
            fft_num = self.fft_sel[fft]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use an FFT choice listed in {self.fft_sel}")
            print(f"You inputted {fft}")
            return

        #Lets this function be reused for the main index and the correlator index, they just have different registers
        if (index_type == "main"):
            array1 = self.corr_array1
            array2 = self.corr_array2
            array3 = self.corr_array3
        elif (index_type == "notch"):
            array1 = self.notch_array1
            array2 = self.notch_array2
            array3 = self.notch_array3
        else:
            print("You need to supply this function with either 'main' or 'notch'")
            print(f"Your argument was {index_type}")
            return

        #Based on the position in the array, decide which batch of registers it falls in and which place within the register
        val_num = int(val)
        batch = fft_num // 5
        position = fft_num % 5

        #Because there are offsets unique to each register (because the 6 bits don't cleanly map to 32 bit registers and we want to condense)
        #Each batch has it's own bit offset, and higher batches have channel offsets
        #Channel 15 is unique also with the modulo and floor division results
        addition = 0
        if (batch == 1):
            addition = 4
            position = position - 1
        elif (batch == 2):
            addition = 2
            position = position - 1
        elif (fft_num == 15):
            batch = 2
            addition = 2
            position = 4

        #Channels 5 and 10 straddle 2 different registers, so they have unique considerations when being split up
        #between 2 registers with a different amount of bits in each one
        if (fft_num == 5):
            lower2bits_inposition = (val_num & 0x3) << 30
            inverse_mask = 0xC0000000
            resp = self.compute_index_send(lower2bits_inposition, inverse_mask, array1)

            upper4bits_inposition = (val_num & 0x3C) >> 2
            inverse_mask = 0xF
            resp = self.compute_index_send(upper4bits_inposition, inverse_mask, array2)

            return 0x12345678
        elif (fft_num == 10):
            lower4bits_inposition = (val_num & 0xF) << 28
            inverse_mask = 0xF0000000
            resp = self.compute_index_send(lower4bits_inposition, inverse_mask, array2)

            upper2bits_inposition = (val_num & 0x30) >> 4
            inverse_mask = 0x3
            resp = self.compute_index_send(upper2bits_inposition, inverse_mask, array3)
            return 0x9ABCDEF
        #Regular channels now, getting mapped to one of three registers
        else:
            if (batch == 0):
                reg = array1
            elif (batch == 1):
                reg = array2
            else:
                reg = array3

            #Takes the value and places it within the 32 bit register where it belongs
            in_position = val_num << ((6*position) + addition)
            #print(f"in_position is {hex(in_position)}")
            #Function requires a mask of all 1s in the same place
            inverse_mask = 0x3F << ((6*position) + addition)
            #print(f"inverse_mask is {hex(inverse_mask)}")
            #This function computes the actual value to send and returns the results
            resp = self.compute_index_send(in_position, inverse_mask, reg)
            return resp

    def compute_index_send(self, in_position, inverse_mask, register):
        #Get the current value of the register from the FPGA for comparisons
        current_val = self.connection.read_reg(register)
        #print(f"current_val is {hex(current_val)}")

        #Turn the mask of 1s in the spot where the data will be applied into the inverse
        #So if you are putting 6 bits of data into the channel 2 spot, it will go from the inverse mask of
        # 0000 0000 0000 00[11 1111] 0000 0000 0000 to:
        # 1111 1111 1111 11[00 0000] 1111 1111 1111
        inverse = ~inverse_mask
        #print(f"inverse is {hex(inverse)}")

        #Now we apply the current value on the FPGA as read by the register to the original inverse mask of mostly 0s
        #So let's say the current vale was already 0xFF000000 and we are writing channel 2 like in the example above:
        # 1111 1111 0000 00[11 1111] 0000 0000 0000
        inverse_mask_applied = current_val | inverse_mask
        #print(f"inverse_mask_applied is {hex(inverse_mask_applied)}")

        #Then we AND this applied mask with the value to the inverse mask with mostly 0s. So we end up with
        # 1111 1111 0000 00[00 0000] 0000 0000 0000
        # We want this because it has the original register value untouched for channels outside of the one we want to write to
        # And the channel we're writing to has been cleared to all 0s, so existing bits don't interfere.
        remove_current = inverse & inverse_mask_applied
        #print(f"remove_current is {hex(remove_current)}")

        #Now we finall apply the actual value (which has already been shifted to the correct position)
        #To the mask with original values but hollowed out to fit this new channel
        #So for example, if the value is 001100 to be applied to channel 2, now we have the value of the 32 bit register to write back to the FPGA:
        # 1111 1111 0000 00[00 1100] 0000 0000 0000
        add_value = remove_current | in_position
        #print(f"add_value is {hex(add_value)}")
        #print(f"add_value is {bin(add_value)}")

        self.connection.write_reg(register, add_value)
        return add_value

    def get_data(self, data_type, num, header=False):
        i = 0
        while (i < self.tries):
            if (header):
                data, header = self.connection.get_data_packets(data_type=data_type, num=num, header=header)
                if (data[0] != []):
                    return data, header
                else:
                    print("LuSEE COMM --> No packet response, retrying...")
                    i += 1
            else:
                data = self.connection.get_data_packets(data_type=data_type, num=num, header=header)
                if (data != []):
                    return data
                else:
                    print("LuSEE COMM --> No packet response, retrying...")
                    i += 1

    def get_adc_data(self, header=False):
        data = self.get_data(data_type = "adc", num=self.ADC_PACKETS, header = header)
        return data

    def get_counter_data(self, header=False):
        if (self.counter_num == None):
            print("LuSEE COMM --> You need to set the counter number before reading out the counter FIFO!")
            return
        packets = (self.counter_num // self.bytes_per_packet) + 1
        data = self.get_data(data_type = "adc", num=packets, header = header)
        return data

    def get_pfb_data(self, header=False):
        wait_time = self.cycle_time * (2**self.avg)
        if (wait_time > 1.0):
            print(f"Waiting {wait_time} seconds for PFB data because average setting is {self.avg} for {2**self.avg} averages")
        time.sleep(40e-6 * (2**self.avg))
        data = self.get_data(data_type = "fft", num=self.FFT_PACKETS, header = header)
        return data

    def set_chan(self, ch, in1, in2, gain):
        a = [None, None]
        b = [None, None]
        c = [None, None]
        for num, i in enumerate([in1, in2]):
            if (i < 4):
                a[num] = 0 if (i == 2 or i == 0) else 1
                b[num] = 0 if (i == 2 or i == 1) else 1
                c[num] = 0 if (i <= 3 or i >= 0) else 1
            else:
                a[num] = i & 0x1
                b[num] = (i >> 0x1) & 0x1
                c[num] = (i >> 0x2) & 0x1

        gain_a = 1 if (gain == "high") else 0
        gain_b = 1 if (gain == "low") else 0

        mux_byte = (gain_b << 7) + (gain_a << 6) + (c[1] << 5) + (b[1] << 4) + (a[1] << 3) + (c[0] << 2) + (b[0] << 1) + a[0]
        total_register = mux_byte << (ch*8)
        zeroing_mask = 0xFF << (ch*8)
        #print(f"zeroing mask is {hex(zeroing_mask)}")
        current_val = self.connection.read_reg(self.mux_reg)
        #print(f"current val is {hex(current_val)}")
        zeroed_val = current_val & ~zeroing_mask
        #print(f"zeroed_val is {hex(zeroed_val)}")
        total_register = zeroed_val + total_register
        #print(f"total_register is {hex(total_register)}")
        self.connection.write_reg(self.mux_reg, total_register)
        return total_register

if __name__ == "__main__":
    #arg = sys.argv[1]
    ethernet = LuSEE_COMMS()
    # resp = 0xAAAAAAAA
    # for num,i in enumerate(ethernet.fft_sel):
    #     print(num)
    #     resp = ethernet.set_corr_array(i, 0x3F, 0x0)

    ethernet.write_adc(0, 5, 0x69)
    resp = ethernet.read_adc(0, 5)
    print(hex(resp))

    ethernet.write_adc(1, 4, 0x67)
    resp = ethernet.read_adc(1, 4)
    print(hex(resp))
