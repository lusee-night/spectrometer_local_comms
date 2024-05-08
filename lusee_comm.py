import time
from datetime import datetime
from ethernet_comm import LuSEE_ETHERNET

class LuSEE_COMMS:
    def __init__(self):
        self.version = 1.08

        self.connection = LuSEE_ETHERNET()

        self.pcb_fix = 0x002
        self.dcb_ts_1 = 0x020
        self.dcb_ts_2 = 0x021
        self.sys_ts_1 = 0x022
        self.sys_ts_2 = 0x023

        self.FW_Version = 0x0FC
        self.FW_ID = 0x0FD
        self.FW_Date = 0xFE
        self.FW_Time = 0xFF

        self.uC_reset = 0x100
        self.scratchpad_1 = 0x120
        self.scratchpad_2 = 0x121

        self.comm_reset = 0x200
        self.load_data = 0x210
        self.num_samples = 0x211
        self.data_src_sel = 0x212
        self.fifo_rst = 0x213
        self.fft_select = 0x214
        self.cdi_src_sel = 0x21F
        self.df_enable = 0x220
        self.df_drop_err = 0x224
        self.df_timestamp1 = 0x230
        self.df_timestamp2 = 0x231
        self.client_control = 0x240
        self.client_ack = 0x241

        self.adc_readout_reset = 0x300
        self.adc_reset = 0x301
        self.adc_function = 0x302
        self.adc_reg_data = 0x303
        self.adc_clk = 0x310
        self.adc_cntl = 0x311

        self.sengine_reset = 0x400
        self.enable_spe = 0x401
        self.test_mode = 0x402
        self.notch_reg = 0x410
        self.main_average = 0x411
        self.notch_average = 0x412
        self.corr_array1 = 0x413
        self.corr_array2 = 0x414
        self.corr_array3 = 0x415
        self.notch_array1 = 0x416
        self.notch_array2 = 0x417
        self.notch_array3 = 0x418
        self.adc_min_threshold = 0x430
        self.adc_max_threshold = 0x431
        self.error_stick = 0x432

        self.mux0_reg = 0x500
        self.mux1_reg = 0x501
        self.mux2_reg = 0x502
        self.mux3_reg = 0x503

        self.calibrator_reset = 0x800
        self.calibrator_bit = 0
        self.calibrator_formatter_bit = 1
        self.Nac1 = 0x801
        self.Nac2 = 0x802
        self.notch_index = 0x803
        self.cplx_index = 0x804
        self.sum1_index = 0x805
        self.sum2_index = 0x806
        self.powertop_index = 0x807
        self.powerbot_index = 0x808
        self.driftFD_index = 0x809
        self.driftSD1_index = 0x80A
        self.driftSD2_index = 0x80B
        self.default_drift = 0x80C
        self.have_lock_value = 0x80D
        self.have_lock_radian = 0x80E
        self.lower_guard_value = 0x80F
        self.upper_guard_value = 0x810
        self.power_ratio = 0x811
        self.antenna_enable = 0x812
        self.cal_error_stick = 0x813
        self.CF_Enable = 0x814
        self.CF_TST_Mode_En = 0x815
        self.CF_start_ADDR = 0x816

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

    #Only need to do one in the beginning
    #Takes a few seconds
    def reset(self):
        self.connection.reset()

    def reset_comms(self):
        self.connection.write_reg(self.comm_reset, 1)

    def uC_reset(self, reset, ddr3_reset, clk_disable):
        reg_val = ((reset & 0x1) << 2) + ((ddr3_reset & 0x1) << 1) + (clk_disable & 0x1)
        self.connection.write_reg(self.uC_reset, reg_val)

    def reset_adc_readout(self, adc):
        self.connection.write_reg(self.adc_readout_reset, 1)

    def reset_adc(self, adc0, adc1):
        reg_val = ((adc1 & 0x1) << 1) + (adc0 & 0x1)

    def reset_spectrometer(self):
        self.connection.write_reg(self.sengine_reset, 1)

    def set_pcb(self, board):
        self.connection.write_reg(self.pcb_fix, board)

    def read_dcb_timestamp(self):
        lower = self.connection.read_reg(self.dcb_ts_1)
        upper = self.connection.read_reg(self.dcb_ts_2)
        return (upper << 32) + lower

    def read_sys_timestamp(self):
        lower = self.connection.read_reg(self.sys_ts_1)
        upper = self.connection.read_reg(self.sys_ts_2)
        return (upper << 32) + lower

    def read_df_timestamp(self):
        lower = self.connection.read_reg(self.df_timestamp1)
        upper = self.connection.read_reg(self.df_timestamp2)
        return (upper << 32) + lower

    def get_firmware_version(self):
        firmware_dict = {}
        firmware_dict['version'] = hex(self.connection.read_reg(self.FW_Version))
        firmware_dict['id'] = hex(self.connection.read_reg(self.FW_ID))
        firmware_dict['date'] = hex(self.connection.read_reg(self.FW_Date))
        firmware_dict['time'] = hex(self.connection.read_reg(self.FW_Time))

        date_string = firmware_dict['date'][2:]
        time_string = firmware_dict['time'][2:]

        year = int(date_string[:4])
        month = int(date_string[4:6])
        day = int(date_string[6:])
        hour = int(time_string[:2])
        minute = int(time_string[2:4])
        second = int(time_string[4:6])

        datetime_object = datetime(year = year, month = month, day = day, hour = hour, minute = minute, second = second)
        firmware_dict['datetime'] = datetime_object

        formatted_data = datetime_object.strftime("%B %d, %Y %I:%M:%S %p")
        firmware_dict['formatted_datetime'] = formatted_data
        return firmware_dict

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

        self.connection.write_reg(self.data_src_sel, val)

    def readout_mode(self, mode):
        if (mode == "fpga"):
            self.connection.write_reg(self.cdi_src_sel, 1)
        elif (mode == "sw"):
            self.connection.write_reg(self.cdi_src_sel, 0)
        else:
            print(f"Python LuSEE Comm --> You need to use a readout method of 'fpga' or 'sw', you used {mode}")

    def set_counter_num(self, num):
        self.counter_num = int(num)
        self.connection.write_reg(self.num_samples, int(num))

    def reset_all_fifos(self):
        print("Python Debugging --> Resetting FIFO")
        self.connection.write_reg(self.fifo_rst, 1)
        time.sleep(self.wait_time)
        self.connection.write_reg(self.fifo_rst, 0)
        time.sleep(self.wait_time)
        print("Python Debugging --> FIFO reset complete")

    def load_adc_fifos(self):
        old_val = self.connection.read_reg(self.load_data)
        new_val = old_val | 0x2
        print(f"Python Debugging --> While loading ADC FIFOs, the original register {hex(self.load_data)} value was {hex(old_val)} and we're trying to set it to {hex(new_val)}")
        self.connection.write_reg(self.load_data, new_val)
        time.sleep(self.wait_time)
        self.connection.write_reg(self.load_data, old_val)
        time.sleep(self.wait_time)
        print(f"Python Debugging --> The final value is {hex(self.connection.read_reg(self.load_data))}")

    def load_fft_fifos(self):
        old_val = self.connection.read_reg(self.load_data)
        new_val = old_val | 0x4
        print(f"Python Debugging --> While loading FFT FIFOs, the original register {hex(self.load_data)} value was {hex(old_val)} and we're trying to set it to {hex(new_val)}")
        self.connection.write_reg(self.load_data, new_val)
        time.sleep(self.wait_time)
        self.connection.write_reg(self.load_data, old_val)
        time.sleep(self.wait_time)
        print(f"Python Debugging --> The final value is {hex(self.connection.read_reg(self.load_data))}")

    def get_df_drop_err(self):
        return self.connection.read_reg(self.df_drop_err)

    def set_adc_clock(self, val):
        self.connection.write_reg(self.adc_clk, int(val))

    def set_adc_powerdown(self, val):
        self.connection.write_reg(self.adc_cntl, int(val))

    def start_spectrometer(self):
        self.connection.write_reg(self.enable_spe, 1)

    def stop_spectrometer(self):
        self.connection.write_reg(self.enable_spe, 0)

    def spectrometer_test_mode(self, val):
        if (val):
            self.connection.write_reg(self.test_mode, 1)
        else:
            self.connection.write_reg(self.test_mode, 0)

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

    def notch_filter_on(self):
        self.connection.write_reg(self.notch_reg, 1)

    def notch_filter_off(self):
        self.connection.write_reg(self.notch_reg, 0)

    def set_adc_threshold(self, adc_min, adc_max):
        self.connection.write_reg(self.adc_min_threshold, int(adc_min))
        self.connection.write_reg(self.adc_max_threshold, int(adc_max))

    def set_sticky_error(self, sticky):
        self.connection.write_reg(self.error_stick, int(sticky))

    def set_all_index(self, val):
        for key in self.fft_sel:
            self.set_index_array(key, val, "main")
            self.set_index_array(key, val, "notch")

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
        time.sleep(self.cycle_time * (2**self.avg))
        data = self.get_data(data_type = "fft", num=self.FFT_PACKETS, header = header)
        return data

    def get_pfb_data_sw(self, header = False, avg = None, test = False):
        if (avg != None):
            self.avg = avg
        #Put Python in control of readout
        self.connection.write_reg(self.client_control, 1)

        #This function could get called again with the FIFO and microcontroller cut short after errors
        #Tells the microcontroller sequence to reset
        self.connection.write_reg(self.scratchpad_2, 1)
        #Resets the CDI output FIFOs
        self.connection.write_reg(self.fifo_rst, 1)
        self.connection.write_reg(self.scratchpad_2, 0)
        self.connection.write_reg(self.fifo_rst, 0)
        #Spectrometer outputs will go to microcontroller
        if (test):
            #Enables the test bit as well
            self.connection.write_reg(self.df_enable, 3)
        else:
            self.connection.write_reg(self.df_enable, 1)
        all_data = []
        #Wait for averaging
        wait_time = self.cycle_time * (2**self.avg)
        if (wait_time > 1.0):
            print(f"Waiting {wait_time} seconds for PFB data because average setting is {self.avg} for {2**self.avg} averages")
        time.sleep(self.cycle_time * (2**self.avg))
        #Stop sending spectrometer data to microcontroller
        #self.connection.write_reg(self.df_enable, 0)
        #Will return all 16 correlations
        for i in range(16):
            #Allows us to repeat, since we've gotten errors where a channel doesn't come on the first try
            received = False
            errors = 0
            while (not received):
                apid = 0x210 + i
                wait_i = 0
                #Wait for microcontroller to say that data has been returned back to CDI buffer
                while(self.connection.read_reg(self.client_ack) == 0x0):
                    if (wait_i > 10):
                        print("Flag didn't go high within 10 seconds of expected time, exiting")
                        return all_data
                    print("Waiting for data CDI flag to go high")
                    time.sleep(1)
                    wait_i = wait_i + 1
                print(f"Flag is high, Python can now read channel {i}")
                #Get data from CDI microcontroller buffer, header to check that APID was correct
                data, header = self.connection.get_data_packets(data_type='sw', num=self.FFT_PACKETS, header = True)
                if header == []:
                    self.connection.write_reg(self.scratchpad_1, 0x10 + (apid & 0xF))
                    received = False
                    errors += 1
                    print(f"Header is empty")
                    print(f"Retrying channel {i}")
                else:
                    #Data usually comes in 3 packets and has 3 separate headers
                    for pkt in range(3):
                        if pkt in header:
                            if 'ccsds_appid' in header[pkt]:
                                if (int(header[pkt]['ccsds_appid'], 16) == apid):
                                    #This is the successful case where everything matches
                                    self.connection.write_reg(self.scratchpad_1, (apid & 0xF))
                                    #print(f"Wrote {apid & 0xF} to scratchpad")
                                    received = True
                                else:
                                    self.connection.write_reg(self.scratchpad_1, 0x20 + (apid & 0xF))
                                    received = False
                                    errors += 1
                                    print(f"Expected APID was {apid} and received APID was {int(header[pkt]['ccsds_appid'], 16)}")
                                    print(f"Retrying channel {i}")
                                    break
                            else:
                                self.connection.write_reg(self.scratchpad_1, 0x30 + (apid & 0xF))
                                received = False
                                errors += 1
                                print("ccsds_appid not in the header dictionary")
                                print(f"Retrying channel {i}")
                                break
                        else:
                            self.connection.write_reg(self.scratchpad_1, 0x40 + (apid & 0xF))
                            received = False
                            errors += 1
                            print(f"Header doesn't have key {pkt}")
                            print(f"Retrying channel {i}")
                            break
                if (errors > 10):
                    print("That's 10 errors in a row in lusee_comm, exiting")
                    return all_data
                #Clear the acknowledge flag to tell microcontroller to check our response
                self.connection.write_reg(self.client_ack, 0)
            all_data.append(data)
        return all_data

    def set_chan_gain(self, ch, in1, in2, gain):
        chs=[2,1,0,3,4,5,6,7]
        gains=[[2,0,1],[1,2,0],[2,0,1],[1,2,0]]
        # pos-input is lsb side
        c1=chs[in2]
        # neg-input is in middle
        c2=chs[in1]
        # gain is msb side
        g=gains[ch][gain]
        mux_byte = ((g>>1) << 7) + ((g&0x1) << 6) + ((c2>>2) << 5) + (((c2>>1)&0x1) << 4) + ((c2&0x1) << 3) + ((c1>>2) << 2) + (((c1>>1)&0x1) << 1) + (c1&0x1)

        if (ch == 0):
            self.connection.write_reg(self.mux0_reg, mux_byte)
        elif (ch == 1):
            self.connection.write_reg(self.mux1_reg, mux_byte)
        elif (ch == 2):
            self.connection.write_reg(self.mux2_reg, mux_byte)
        elif (ch == 3):
            self.connection.write_reg(self.mux3_reg, mux_byte)
        return mux_byte

    def reset_calibrator(self):
        self.connection.write_reg(self.calibrator_reset, 1 << self.calibrator_bit)
        self.connection.write_reg(self.calibrator_reset, 0)

    def reset_calibrator_formatter(self):
        self.connection.write_reg(self.calibrator_reset, 1 << self.calibrator_formatter_bit)

    def setup_calibrator(self, Nac1, Nac2, notch_index, cplx_index, sum1_index, sum2_index, powertop_index, powerbot_index, driftFD_index,
                         driftSD1_index, driftSD2_index, default_drift, have_lock_value, have_lock_radian, lower_guard_value, upper_guard_value, power_ratio, antenna_enable):

        self.connection.write_reg(self.Nac1, Nac1)
        self.connection.write_reg(self.Nac2, Nac2)
        self.connection.write_reg(self.notch_index, notch_index)
        self.connection.write_reg(self.cplx_index, cplx_index)
        self.connection.write_reg(self.sum1_index, sum1_index)
        self.connection.write_reg(self.sum2_index, sum2_index)
        self.connection.write_reg(self.powertop_index, powertop_index)
        self.connection.write_reg(self.powerbot_index, powerbot_index)
        self.connection.write_reg(self.driftFD_index, driftFD_index)
        self.connection.write_reg(self.driftSD1_index, driftSD1_index)
        self.connection.write_reg(self.driftSD2_index, driftSD2_index)
        self.connection.write_reg(self.default_drift, default_drift)
        self.connection.write_reg(self.have_lock_value, have_lock_value)
        self.connection.write_reg(self.have_lock_radian, have_lock_radian)
        self.connection.write_reg(self.lower_guard_value, lower_guard_value)
        self.connection.write_reg(self.upper_guard_value, upper_guard_value)
        self.connection.write_reg(self.power_ratio, power_ratio)
        self.connection.write_reg(self.antenna_enable, antenna_enable)

        self.connection.write_reg(0x421, 0xFF)
        self.connection.write_reg(0x813, 1)
        self.reset_calibrator()
        self.reset_calibrator_formatter()
        input("Ready?")
        self.reset_calibrator()
        self.reset_calibrator_formatter()
        self.connection.write_reg(0x421, 0x0)

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
