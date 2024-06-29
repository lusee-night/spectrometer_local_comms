import os
import sys
import json
import math
import time
from datetime import datetime

from lusee_comm import LuSEE_COMMS
from lusee_plotting import LuSEE_PLOTTING

class LuSEE_MEASURE:
    def __init__(self):
        self.version = 1.11
        self.comm = LuSEE_COMMS()
        self.prefix = "LuSEE Measure --> "
        self.tick_size = 22
        self.title_size = 32
        self.subtitle_size = 28
        self.label_size = 28

    def set_all_adc_ramp(self):
        self.comm.write_adc(0, 0x42, 0x08) #Enable digital functions on ADC0
        self.comm.write_adc(1, 0x42, 0x08) #Enable digital functions on ADC1
        self.comm.write_adc(0, 0x25, 0x04) #Enable ramp for channel A on ADC0
        self.comm.write_adc(1, 0x25, 0x04) #Enable ramp for channel A on ADC1
        self.comm.write_adc(0, 0x2B, 0x04) #Enable ramp for channel B on ADC0
        self.comm.write_adc(1, 0x2B, 0x04) #Enable ramp for channel B on ADC1

    def get_adc_data(self, adc, header):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function(f"ADC{adc}")
        return self.comm.get_adc_data(header = header)

    def get_adcs_sync(self):
        self.comm.readout_mode("fpga")
        self.comm.reset_all_fifos()
        self.comm.load_adc_fifos()
        self.comm.set_function("ADC1")
        #With no argument, header defaults to 'False"
        data1 = self.comm.get_adc_data()
        self.comm.set_function("ADC2")
        data2 = self.comm.get_adc_data()
        self.comm.set_function("ADC3")
        data3 = self.comm.get_adc_data()
        self.comm.set_function("ADC4")
        data4 = self.comm.get_adc_data()
        return data1, data2, data3, data4

    def get_counter_data(self, counter_num):
        self.comm.readout_mode("fpga")
        self.comm.set_function("Counter")
        self.comm.set_counter_num(counter_num)
        data, header = self.comm.get_counter_data(header = True)
        return data, header

    def to_radian(self, val):
        if (val > 1 or val < -1):
            sys.exit(f"lusee_measure --> Must supply radian values between -1 and 1. You supplied {val}")
        sign = True if val >= 0 else False
        if (sign):
            working_val = 0
            for num,i in enumerate(range(30, -1, -1)):
                digit_val = 1/(2**num)
                if (digit_val <= val):
                    working_val |= 1 << i
                    val -= digit_val
        else:
            working_val = 0xC0000000
            val += 1
            for num,i in enumerate(range(29, -1, -1)):
                digit_val = 1/(2**(num+1))
                if (digit_val <= val):
                    working_val |= 1 << i
                    val -= digit_val
        return working_val

    def calibrator_test(self):
        self.comm.connection.write_reg(0x838, 1)
        #Overwrite ADC ramp
        self.comm.connection.write_reg(0x84D, 1)
        self.comm.connection.write_reg(0x84E, 0x0)
        self.comm.connection.write_reg(0x851, 2046)

        #Choose frequency bin
        self.comm.connection.write_reg(0x84F, 0)
        self.comm.connection.write_reg(0x850, 511)
        self.comm.connection.write_reg(0x214, 8)
        if (self.json_data[f"pretest"]):
            self.spectrometer_simple()
        else:
            self.setup()
            self.setup_pfb()

        self.setup_calibrator()

        with open(self.json_output_file, 'w', encoding='utf-8') as f:
            json.dump(self.datastore, f, ensure_ascii=False, indent=4, default=str)
        self.plotter = LuSEE_PLOTTING(self.results_path)

        self.comm.readout_mode("sw")
        all_data,all_headers = self.comm.get_calib_data_sw(
            header_return = True, notch_avg = self.json_data["notch_averages"], Nac1 = self.json_data["Nac1"], Nac2 = self.json_data["Nac2"], test = False
            )
        calib_dict = {"header": all_headers,
                        "data": all_data}
        with open(os.path.join(self.results_path, f"calib_output.json"), 'w', encoding='utf-8') as f:
            json.dump(calib_dict, f, ensure_ascii=False, indent=4, default=str)

        if (self.json_data[f"print_calib"]):
            self.plotter.print_calib()

        if (self.json_data[f"calib_fout_plot"]):
            self.plotter.plot_fout(self.json_data[f"calib_fout_plot_show"], self.json_data[f"calib_fout_plot_save"])

        if (self.json_data[f"calib_drift_plot"]):
            self.plotter.plot_lock_drift(self.json_data[f"calib_drift_plot_show"], self.json_data[f"calib_drift_plot_save"])

        if (self.json_data[f"calib_topbottom_plot"]):
            self.plotter.plot_topbottom(self.json_data[f"calib_topbottom_plot_show"], self.json_data[f"calib_topbottom_plot_save"])

        if (self.json_data[f"calib_fdsd_plot"]):
            self.plotter.plot_fdsd(self.json_data[f"calib_fdsd_plot_show"], self.json_data[f"calib_fdsd_plot_save"])

    def spectrometer_simple(self):
        self.setup()
        for i in range(1, 5):
            if (self.json_data[f"adc{i}_save_data"]):
                data, header = self.get_adc_data(i, True)
                adc_dict = {"header": header,
                            "data": data}
                with open(os.path.join(self.results_path, f"adc{i}_output.json"), 'w', encoding='utf-8') as f:
                    json.dump(adc_dict, f, ensure_ascii=False, indent=4, default=str)

                if (self.json_data[f"adc{i}_plot"]):
                    self.plotter.plot_adc(i, self.json_data[f"adc{i}_plot_show"], self.json_data[f"adc{i}_plot_save"])

                if (self.json_data[f"adc{i}_plot_overlay"]):
                    self.plotter.plot_adc_overlay(i)

        self.setup_pfb()
        self.comm.readout_mode("fpga")
        #input("ready?")
        time.sleep(.2)
        for i in range(1, 5):
            if (self.json_data[f"pfb{i}_fpga_save_data"]):
                self.comm.set_function(f"FFT{i}")
                data, header = self.comm.get_pfb_data(header = True)
                pfb_dict = {"header": header,
                            "data": data}
                with open(os.path.join(self.results_path, f"pfb_fpga{i}_output.json"), 'w', encoding='utf-8') as f:
                    json.dump(pfb_dict, f, ensure_ascii=False, indent=4, default=str)

                if (self.json_data[f"pfb{i}_fpga_plot"]):
                    self.plotter.plot_pfb_fpga(i, self.json_data[f"pfb{i}_fpga_plot_show"], self.json_data[f"pfb{i}_fpga_plot_save"])

                #self.plotter.plot_notches(i, True, True)

        if (self.json_data[f"pfb_sw_save_data"]):
            self.comm.readout_mode("sw")
            all_data, all_headers = self.comm.get_pfb_data_sw(header_return = True)

            pfb_dict = {"header": all_headers,
                        "data": all_data}
            with open(os.path.join(self.results_path, f"pfb_sw_output.json"), 'w', encoding='utf-8') as f:
                json.dump(pfb_dict, f, ensure_ascii=False, indent=4, default=str)

            if (self.json_data[f"pfb_sw_plot"]):
                self.plotter.plot_pfb_sw(self.json_data[f"pfb_sw_plot_show"], self.json_data[f"pfb_sw_plot_save"])

    def debug(self):
        self.comm.connection.write_reg(0x838, 1)
        self.setup()
        if (self.json_data[f"pretest"]):
            for i in range(1, 5):
                if (self.json_data[f"adc{i}_save_data"]):
                    data, header = self.get_adc_data(i, True)
                    adc_dict = {"header": header,
                                "data": data}
                    with open(os.path.join(self.results_path, f"adc{i}_output.json"), 'w', encoding='utf-8') as f:
                        json.dump(adc_dict, f, ensure_ascii=False, indent=4, default=str)

                    if (self.json_data[f"adc{i}_plot"]):
                        self.plotter.plot_adc_overlay(i)

            if (self.json_data[f"pfb_sw_save_data"]):
                self.comm.readout_mode("sw")
                all_data, all_headers = self.comm.get_pfb_data_sw(header_return = True)

                pfb_dict = {"header": all_headers,
                            "data": all_data}
                with open(os.path.join(self.results_path, f"pfb_sw_output.json"), 'w', encoding='utf-8') as f:
                    json.dump(pfb_dict, f, ensure_ascii=False, indent=4, default=str)

                if (self.json_data[f"pfb_sw_plot"]):
                    self.plotter.plot_pfb_sw(self.json_data[f"pfb_sw_plot_show"], self.json_data[f"pfb_sw_plot_save"])
        self.setup_pfb()
        self.comm.readout_mode("fpga")
        pfb_dict = {}

        iterations = 64
        for i in range(iterations):
            self.comm.set_function(f"FFT1")
            data, header = self.comm.get_pfb_data(header = True)
            #self.comm.set_function(f"FFT3")
            #data, header = self.comm.get_pfb_data(header = True)
            pfb_dict.update({f"header{i}": header,
                        f"data{i}": data})
            self.comm.load_fft_fifos()
            print("got it")
        with open(os.path.join(self.results_path, f"notch_filter_output.json"), 'w', encoding='utf-8') as f:
            json.dump(pfb_dict, f, ensure_ascii=False, indent=4, default=str)

        self.plotter.plot_notches_multiple(iterations)
        self.plotter.plot_notches_multiple_freq(iterations)

    def setup(self):
        if (self.json_data["reset"]):
            self.comm.reset()
            self.comm.reset_adc(adc0 = True, adc1 = True)

        if (self.json_data["pcb"] == "red"):
            self.comm.set_pcb(0)
        elif (self.json_data["pcb"] == "green"):
            self.comm.set_pcb(1)
        else:
            pcb = self.json_data["pcb"]
            sys.exit(f"{self.prefix}Error, pcb model designated as {pcb}")

        self.comm.set_chan_gain(0, self.json_data["mux1_in1"], self.json_data["mux1_in2"], self.json_data["mux1_gain"])
        self.comm.set_chan_gain(1, self.json_data["mux2_in1"], self.json_data["mux2_in2"], self.json_data["mux2_gain"])
        self.comm.set_chan_gain(2, self.json_data["mux3_in1"], self.json_data["mux3_in2"], self.json_data["mux3_gain"])
        self.comm.set_chan_gain(3, self.json_data["mux4_in1"], self.json_data["mux4_in2"], self.json_data["mux4_gain"])

        self.datastore['0x500'] = hex(self.comm.connection.read_reg(self.comm.mux0_reg))
        self.datastore['0x501'] = hex(self.comm.connection.read_reg(self.comm.mux1_reg))
        self.datastore['0x502'] = hex(self.comm.connection.read_reg(self.comm.mux2_reg))
        self.datastore['0x503'] = hex(self.comm.connection.read_reg(self.comm.mux3_reg))

    def setup_pfb(self):
        avgs = self.json_data["pfb_averages"]
        self.comm.set_main_average(avgs)
        self.comm.set_notch_filter(self.json_data["notch_filter"])
        self.comm.set_notch_subtract_disable(self.json_data["notch_subtract_disable"])
        self.comm.set_notch_average(self.json_data["notch_averages"])
        self.comm.set_sticky_error(self.json_data["sticky_errors"])
        self.comm.spectrometer_test_mode(self.json_data["pfb_test_mode"])

        for i in range(1, 17):
            main_index = int(self.json_data[f"pfb{i}_main_index"], 16)
            notch_index = int(self.json_data[f"pfb{i}_notch_index"], 16)
            self.comm.set_index_array(i-1, main_index, "main")
            self.comm.set_index_array(i-1, notch_index, "notch")

        self.comm.reset_all_fifos()
        self.comm.load_fft_fifos()
        self.comm.start_spectrometer()

        wait_time = self.comm.cycle_time * (2**avgs)
        if (wait_time > 1.0):
            print(f"Waiting {wait_time} seconds for PFB data because average setting is {avgs} for {2**avgs} averages")

    def setup_calibrator(self):
        self.comm.connection.write_reg(0x838, 1)
        self.comm.connection.write_reg(0x840, self.json_data["hold_drift"])

        self.comm.set_cal_sticky_error(self.json_data["sticky_errors"])

        #Overwrite a stable notch value
        self.comm.connection.write_reg(0x844, 0)
        self.comm.connection.write_reg(0x845, 2)
        self.comm.connection.write_reg(0x846, 3)
        self.comm.connection.write_reg(0x847, 2)
        self.comm.connection.write_reg(0x848, 3)
        self.comm.connection.write_reg(0x849, 2)
        self.comm.connection.write_reg(0x84A, 3)
        self.comm.connection.write_reg(0x84B, 2)
        self.comm.connection.write_reg(0x84C, 3)

        base_tone = 50e3
        samples_per_fft = 4096
        sampling_rate = 102.4e6
        alpha = 1e-6

        phase_drift_per_ppm = base_tone * samples_per_fft / sampling_rate * alpha * 2
        notch_averages = 2 ** self.json_data["notch_averages"]
        alpha_to_pdrift = phase_drift_per_ppm * notch_averages

        if (self.json_data["default_drift"] == "default"):
            default_drift = 0
        else:
            default_drift = int(self.json_data["default_drift"], 16)

        if (self.json_data["have_lock_value"] == "default"):
            have_lock_value_raw = alpha_to_pdrift * 0.05 * math.pi
            self.datastore['have_lock_value_calculated_raw'] = have_lock_value_raw
            have_lock_value = self.to_radian(have_lock_value_raw)
            self.datastore['have_lock_value_calculated_formatted'] = hex(have_lock_value)
        else:
            have_lock_value = int(self.json_data["have_lock_value"], 16)

        if (self.json_data["have_lock_radian"] == "default"):
            have_lock_radian_raw = alpha_to_pdrift * 0.05
            self.datastore['have_lock_radian_calculated_raw'] = have_lock_radian_raw
            have_lock_radian = self.to_radian(have_lock_radian_raw)
            self.datastore['have_lock_radian_calculated_formatted'] = hex(have_lock_radian)
        else:
            have_lock_radian = int(self.json_data["have_lock_radian"], 16)

        if (self.json_data["upper_guard_value"] == "default"):
            upper_guard_value_raw = alpha_to_pdrift * 1.2
            self.datastore['upper_guard_calculated_raw'] = upper_guard_value_raw
            upper_guard_value = self.to_radian(upper_guard_value_raw)
            self.datastore['upper_guard_calculated_formatted'] = hex(upper_guard_value)
        else:
            upper_guard_value = int(self.json_data["upper_guard_value"], 16)

        if (self.json_data["lower_guard_value"] == "default"):
            lower_guard_value_raw = alpha_to_pdrift * -1.2
            self.datastore['lower_guard_calculated_raw'] = lower_guard_value_raw
            lower_guard_value = self.to_radian(lower_guard_value_raw)
            self.datastore['lower_guard_calculated_formatted'] = hex(lower_guard_value)
        else:
            lower_guard_value = int(self.json_data["lower_guard_value"], 16)

        self.comm.setup_calibrator(
            Nac1 = self.json_data["Nac1"],
            Nac2 = self.json_data["Nac2"],
            notch_index = self.json_data["notch_index"],
            cplx_index = self.json_data["cplx_index"],
            sum1_index = self.json_data["sum1_index"],
            sum2_index = self.json_data["sum2_index"],
            powertop_index = self.json_data["powertop_index"],
            powerbot_index = self.json_data["powerbot_index"],
            driftFD_index = self.json_data["driftFD_index"],
            driftSD1_index = self.json_data["driftSD1_index"],
            driftSD2_index = self.json_data["driftSD2_index"],
            default_drift = default_drift,
            have_lock_value = have_lock_value,
            have_lock_radian = have_lock_radian,
            lower_guard_value = lower_guard_value,
            upper_guard_value = upper_guard_value,
            power_ratio = int(self.json_data["power_ratio"], 16),
            antenna_enable = int(self.json_data["antenna_enable"], 16),
            power_slice = int(self.json_data["power_slice"], 16),
            fdsd_slice = int(self.json_data["fdsd_slice"], 16),
            fdxsdx_slice = int(self.json_data["fdxsdx_slice"], 16),
            restrict_frequency = self.json_data["limit_frequency"],
            lower_frequency = self.json_data["lower_frequency"],
            upper_frequency = self.json_data["upper_frequency"]
            )
        if (self.json_data["reset_cal"]):
            self.calibrator_reset()
        if (self.json_data["wait_to_start"]):
            self.calibrator_wait()

    def calibrator_reset(self):
        self.comm.reset_calibrator()
        self.comm.reset_calibrator_formatter()

    def calibrator_wait(self):
        self.comm.connection.write_reg(0x421, 0xFF)

        self.calibrator_reset()
        #self.connection.write_reg(0x838, 1)
        #self.connection.write_reg(0x839, 1)
        #self.connection.write_reg(0x83A, 1)
        #self.connection.write_reg(0x83B, 1)
        #self.connection.write_reg(0x83C, 1)
        input("Ready?")
        self.calibrator_reset()
        self.comm.connection.write_reg(0x421, 0x0)

    def start_test(self, config_file):
        print(f"{self.prefix}Initializing Test")
        with open(config_file, "r") as jsonfile:
            self.json_data = json.load(jsonfile)

        #The datastore is the eventual output JSON file that will be written after the test
        #Want to also include what the inputs for this particular test was
        self.datastore = {}
        self.datastore['input_params'] = self.json_data
        self.start_time = datetime.now()
        self.datastore['start_time'] = self.start_time
        self.datastore.update(self.comm.get_firmware_version())

        if (self.json_data["relative"] == True):
            output_path = os.path.abspath(self.json_data["output_directory"])
        else:
            output_path = os.path.normpath(self.json_data["output_directory"])

        json_date = datetime.today().strftime('%Y%m%d%H%M%S')
        os.makedirs(os.path.join(output_path, json_date))
        self.results_path = os.path.join(output_path, json_date)
        self.json_output_file = os.path.join(self.results_path, f"output.json")
        self.datastore['json_path'] = self.json_output_file

        with open(self.json_output_file, 'w', encoding='utf-8') as f:
            json.dump(self.datastore, f, ensure_ascii=False, indent=4, default=str)

        self.plotter = LuSEE_PLOTTING(self.results_path)

        test = self.json_data["test"]

        if (test == "spectrometer_simple"):
            self.spectrometer_simple()
        elif (test == "calibrator"):
            self.calibrator_test()
        elif (test == "debug"):
            self.debug()
        else:
            sys.exit(f"{self.prefix}Incorrect test supplied, {test} is not valid.")

        end_time = datetime.now()
        test_time = end_time - self.start_time
        self.datastore['end_time'] = end_time
        self.datastore['test_time'] = test_time

        with open(self.json_output_file, 'w', encoding='utf-8') as f:
            json.dump(self.datastore, f, ensure_ascii=False, indent=4, default=str)

        print(f"{self.prefix}Test complete")

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        arg = sys.argv[1]
    else:
        sys.exit("You need to supply an argument")
    measure = LuSEE_MEASURE()
    measure.comm.connection.write_cdi_reg(5, 69)
    resp = measure.comm.connection.read_cdi_reg(5)
    if (resp == 69):
        print("[TEST] Communication to DCB Emulator is ok")
    else:
        sys.exit("[TEST] Communication to DCB Emulator is not ok")

    measure.comm.connection.write_reg(0x120, 69)
    resp = measure.comm.connection.read_reg(0x120)
    if (resp == 69):
        print("[TEST] Communication to Spectrometer Board is ok")
    else:
        print(resp)
        sys.exit("[TEST] Communication to Spectrometer Board is not ok")

    if (arg == "reset"):
        measure.comm.reset()
        measure.comm.reset_adc(adc0 = True, adc1 = True)

    if (arg == "adc"):
        measure.set_all_adc_ramp()

    if len(sys.argv) < 2:
        sys.exit(f"Error: You need to supply a config file for this test as the argument! You had {len(sys.argv)-1} arguments!")

    measure.start_test(arg)
