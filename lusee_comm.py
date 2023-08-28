import time
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_COMMS:
    def __init__(self):
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

        self.wait_time = 0.025
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
        self.weight_fold_shift = 23
        self.notch_reg = 24

        self.corr_array1 = 25
        self.corr_array2 = 26
        self.corr_array3 = 27

        self.notch_array1 = 28
        self.notch_array2 = 29
        self.notch_array3 = 30

        self.pfb_delays = 31

    #Only need to do one in the beginning
    #Takes a few seconds
    def reset(self):
        self.connection.reset()

    def reset_adc(self, adc):
        self.connection.write_reg(self.adc_function, 0x10 << int(adc))
        self.connection.write_reg(self.adc_function, 0x0)

    def write_adc(self, adc, reg, data):
        print(f"Reg is {reg} and data is {hex(data)}")
        val = data & 0xFF
        reg_num = reg & 0xFF
        final_val = reg_num + (val << 8)
        print(f"sending {hex(final_val)}")
        self.connection.write_reg(self.adc_reg_data, final_val)
        print(f"reg 2 is {1 << int(adc)}")
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
        return int(resp)

    def set_function(self, function):
        try:
            val = self.readout_modes[function]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use a function listed in {self.readout_modes}")
            print(f"You inputted {function}")
            return

        self.connection.write_reg(self.function_register, val)

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
        self.connection.write_reg(self.main_average, avg_num)

    def set_notch_average(self, avg):
        avg_num = int(avg)
        self.connection.write_reg(self.notch_average, avg_num)

    def set_weight_fold_shift(self, shift):
        shift_num = int(shift)
        self.connection.write_reg(self.weight_fold_shift, shift_num)

    def notch_filter_on(self):
        self.connection.write_reg(self.notch_reg, 1)

    def notch_filter_off(self):
        self.connection.write_reg(self.notch_reg, 0)

    def set_corr_array(self, fft, val):
        try:
            fft_num = self.fft_sel[fft]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use an FFT choice listed in {self.fft_sel}")
            print(f"You inputted {fft}")
            return

        val_num = int(val)
        batch = fft_num // 6
        position = fft_num % 6

        if (batch == 0):
            reg = self.corr_array1
        elif (batch == 1):
            reg = self.corr_array2
        else:
            reg = self.corr_array3

        in_position = val_num << (5*position)
        #print(f"in_position is {hex(in_position)}")
        current_val = self.connection.read_reg(reg)
        #print(f"current_val is {hex(current_val)}")
        inverse_mask = 0x1F << (5*position)
        #print(f"inverse_mask is {hex(inverse_mask)}")
        inverse = ~inverse_mask
        #print(f"inverse is {hex(inverse)}")
        inverse_mask_applied = current_val | inverse_mask
        #print(f"inverse_mask_applied is {hex(inverse_mask_applied)}")
        remove_current = inverse & inverse_mask_applied
        #print(f"remove_current is {hex(remove_current)}")
        add_value = remove_current | in_position
        #print(f"add_value is {hex(add_value)}")
        self.connection.write_reg(reg, add_value)

    def set_notch_array(self, fft, val):
        try:
            fft_num = self.fft_sel[fft]
        except KeyError:
            print(f"Python LuSEE Comm --> You need to use an FFT choice listed in {self.fft_sel}")
            print(f"You inputted {fft}")
            return

        val_num = int(val)
        batch = fft_num // 6
        position = fft_num % 6

        if (batch == 0):
            reg = self.notch_array1
        elif (batch == 1):
            reg = self.notch_array2
        else:
            reg = self.notch_array3

        in_position = val_num << (5*position)
        #print(f"in_position is {hex(in_position)}")
        current_val = self.connection.read_reg(reg)
        #print(f"current_val is {hex(current_val)}")
        inverse_mask = 0x1F << (5*position)
        #print(f"inverse_mask is {hex(inverse_mask)}")
        inverse = ~inverse_mask
        #print(f"inverse is {hex(inverse)}")
        inverse_mask_applied = current_val | inverse_mask
        #print(f"inverse_mask_applied is {hex(inverse_mask_applied)}")
        remove_current = inverse & inverse_mask_applied
        #print(f"remove_current is {hex(remove_current)}")
        add_value = remove_current | in_position
        #print(f"add_value is {hex(add_value)}")
        self.connection.write_reg(reg, add_value)

    def set_pfb_delays(self, delay):
        delay_num = int(delay)
        self.connection.write_reg(self.pfb_delays, delay_num)

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
        data = self.get_data(data_type = "fft", num=self.FFT_PACKETS, header = header)
        return data

    def set_chan(self, ch, in1, in2, gain):
        a = [None, None]
        b = [None, None]
        c = [None, None]
        for num, i in enumerate([in1, in2]):
            a[num] = 0 if (i == 2 or i == 0) else 1
            b[num] = 0 if (i == 2 or i == 1) else 1
            c[num] = 0 if (i <= 3 or i >= 0) else 1

        gain_a = 1 if (gain == "high") else 0
        gain_b = 1 if (gain == "low") else 0

        mux_byte = (gain_b << 7) + (gain_a << 6) + (c[1] << 5) + (b[1] << 4) + (a[1] << 3) + (c[0] << 2) + (b[0] << 1) + a[0]
        total_register = mux_byte << (ch*8)
        self.connection.write_reg(self.mux_reg, total_register)
        return total_register

if __name__ == "__main__":
    #arg = sys.argv[1]
    ethernet = LuSEE_COMMS()
    x = ethernet.get_adc1_data()
    y = []
    for i in x:
        y.append(ethernet.twos_comp(i, 14))
    #ethernet.plot(y)
    #x,y = ethernet.get_adc2_header_data()
    x,y = ethernet.get_counter_data(counter_num = 0x840)
    print("Getting FFT")
    ethernet.get_pfb_data()
