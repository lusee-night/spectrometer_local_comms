# LuSEE Readout Scripts

These are readout scripts for the the LuSEE-Night Spectrometer board designed by BNL. They conduct various functions such as collect general data, do power measurements, or use the bootloader to delete or write new regions to the flash memory.

As of now, these scripts are meant to be run on a computer being connected to the DCB emulator through an Ethernet/UDP connection.

## Todo:
* Implement reading from virtual TCP socket at SSL, so communication can happen remotely through an actual DCB
* Implement a threaded queue, so that the socket is always listening and buffering incoming data. Rather than the current method of request -> open socket for response
* Organize functionality into a GUI so live debugging is easier

## Installation
These scripts use Python and associated libraries. The requirements are in `requirements.txt`. They can be installed by using your pip as below:

```console
pip3 install -r requirements.txt
```
## Config files
The `lusee_measure.py` and `lusee_power_read.py` functionality uses configuration files to organize the numerous options and knobs that can be tweaked for the LuSEE FPGA's functionality. The full documentation for the FPGA register map and inner workings can be found [in this Google Doc](https://docs.google.com/document/d/1nYvZ_bvYrfkG3akz7YOnAUKMPMGPlmQmX-YEOfuaNGs/edit#heading=h.fmkuyenh6zac "LuSEE-Night Spectrometer FPGA documentation"). An explanation of the fields is below:
```json
"schema": "A number for future proofing in case the schema changes. Default is '1'"
"test": "The sequence that will happen when you call a script with this config file. Current implementations are `spectrometer_simple`, `calibrator` and `debug`"
"output_directory": "All the data and plots that are saved will be at 'output/<this directory>'"
"title": "This will be the title used on all the plots generated"
"comment": "This is meant to be a detailed comment for the notes of this data collection. Will also be in the spreadsheet of the power benchmarking."
"relative": "If true, the 'output/<output_directory>' will be generated in the top level of this directory. If false, then the <output_directory> will be taken as an absolute path"

"reset": "true or false, whether you want the test to start with a full system reset. It can take up to 5 seconds."
"pcb": "`red` or `green`, there are 2 versions of the FPGA Mezzannine. `red` was the old one, all final versions will be `green`."

"adc_num": "When using the ADC stats system, this is the value that goes to register 0x321. It's interpreted as a hex value, so use 0xFFFE for example"
"adc_high": "When using the ADC stats system, this is the value that goes to register 0x322. It's interpreted as a hex value, so use 0x3FFF for example"
"adc_low": "When using the ADC stats system, this is the value that goes to register 0x323. It's interpreted as a hex value, so use 0x0 for example"

"mux1_in1": "Sets register 0x500 according to which integer input is specified here for the P side"
"mux1_in2": "Sets register 0x500 according to which integer input is specified here for the N side"
"mux1_gain": "Sets register 0x500 according to which integer input is specified here for the gain"
"Similar for mux2, 3, and 4"

"adc1_save_data": "true or false, if the sequence has an option to collect ADC data after configuration, data will be saved"
"adc1_plot": "true or false, should a plot be created based on this data"
"adc1_plot_show": "true or false, should the plot pop up in the middle of the sequence (this pauses it until closed)"
"adc1_plot_save": "true or false, should the plot be saved in the output directory"
"adc1_plot_overlay": "true or false, in the case of the calibrator, the ADC input can be plotted to overlay it in 2048 samples to see how well matched the calibration sequence is. The plot being shown/saved will follow the above conventions"
"Similar for adc2, 3, and 4"

"pfb_averages": "Integer that sets the value in register 0x411"
"notch_filter": "true or false for register 0x410"
"notch_subtract_disable": "true or false, register 0x425 gets set to 0 or 0xFFFF"
"notch_averages": "Integer that sets the value in register 0x412"
"sticky_errors": "true or false, register 0x432 gets set to 0 or 0xF"
"pfb_test_mode": "true or false for register 0x402"

"pfb1_main_index": "Hex format value that sets A1 of register 0x411"
"pfb1_notch_index": "Hex format value that sets A1 of register 0x413"
"similar for pfb2-16"

"pfb1_fpga_save_data": "true or false, if the sequence has an option to collect spectrum data after configuration through the FPGA interface, data will be saved"
"pfb1_fpga_plot": "true or false, should a plot be created based on this data"
"pfb1_fpga_plot_show": "true or false, should the plot pop up in the middle of the sequence (this pauses it until closed)"
"pfb1_fpga_plot_save": "true or false, should the plot be saved in the output directory"
"Similar for pfb2, 3, and 4"

"pfb_sw_save_data": "true or false, if the sequence has an option to collect spectrum data after configuration through the microcontroller interface (includes all 16 channels), data will be saved"
"pfb_sw_plot": "true or false, should a plot be created based on this data"
"pfb_sw_plot_show": "true or false, should the plot pop up in the middle of the sequence (this pauses it until closed)"
"pfb_sw_plot_save": "true or false, should the plot be saved in the output directory"

"The below parameters are needed only for the calibaration test:"

"reset_cal": "true or false to reset the whole calibration subsystem at the beginning of the sequence. true means that you will get the actual initial searching from the default drift value"
"wait_to_start": "true or false, there will be a command line prompt to continue before the PFB and calibration is enabled. This helps if you want to set up the incoming calibration signal and then push go."
"Nac1": "Integer value for register 0x801"
"Nac2": "Integer value for register 0x802"
"notch_index": "Integer value for register 0x803"
"cplx_index": "Integer value for register 0x804"
"sum1_index": "Integer value for register 0x805"
"sum2_index": "Integer value for register 0x806"
"powertop_index": "Integer value for register 0x807"
"powerbot_index": "Integer value for register 0x808"
"driftFD_index": "Integer value for register 0x809"
"driftSD1_index": "Integer value for register 0x80A"
"driftSD2_index": "Integer value for register 0x80B"
"default_drift": "Value for register 0x80C. Can be 'default', in hex format like 0xFFFF1234, or a float like 5e-5"
"have_lock_value": "Value for register 0x80D. Can be 'default', in hex format like 0xFFFF1234, or a float like 5e-5"
"have_lock_radian": "Value for register 0x80E. Can be 'default', in hex format like 0xFFFF1234, or a float like 5e-5"
"lower_guard_value": "Value for register 0x80F. Can be 'default', in hex format like 0xFFFF1234, or a float like 5e-5"
"upper_guard_value": "Value for register 0x810. Can be 'default', in hex format like 0xFFFF1234, or a float like 5e-5"
"power_ratio": "Value for register 0x811 in hex format"
"antenna_enable": "Value for register 0x812 in hex format"
"power_slice": "Value for register 0x83D in hex format"
"fdsd_slice": "Value for register 0x83D in hex format"
"fdxsdx_slice": "Value for register 0x83F in hex format"
"hold_drift": "true or false for register 0x840"

"limit_frequency": "true or false for register 0x841"
"lower_frequency": "Integer value for register 0x842"
"upper_frequency": "Integer value for register 0x843"

"print_calib": "true or false to print out all calibration values (27 parameters with 2048 values each) in the command line. Used for debugging"
"calib_fout_plot": "true or false to make a plot of Fout_real/image 1-4"
"calib_fout_plot_show": "true or false, should the plots pop up in the middle of the sequence (this pauses it until closed)"
"calib_fout_plot_save": "true or false, should the plots be saved in the output directory"

"calib_drift_plot": "true or false to make a plot of pwr_used and drift values"
"calib_drift_plot_show": "true or false, should the plots pop up in the middle of the sequence (this pauses it until closed)"
"calib_drift_plot_save": "true or false, should the plots be saved in the output directory"

"calib_topbottom_plot": "true or false to make a plot of top and bottom power values"
"calib_topbottom_plot_show": "true or false, should the plots pop up in the middle of the sequence (this pauses it until closed)"
"calib_topbottom_plot_save": "true or false, should the plots be saved in the output directory"

"calib_fdsd_plot": "true or false to make a plot of FD, SD, FDX and SDX values"
"calib_fdsd_plot_show": "true or false, should the plots pop up in the middle of the sequence (this pauses it until closed)"
"calib_fdsd_plot_save": "true or false, should the plots be saved in the output directory"
```
## Running the scripts
### `lusee_measure.py`
This script is run like:
```console
python3 lusee_measure.py config/config_calibrator.json
```

It will read in the config file and decide whether it's running one of these tests:
* spectrometer_simple: It will configure the spectrometer with the gain/averagering settings in the file, and then look to read out the ADC and PFB data
* calibrator: It will do a spectrometer_simple test, and then look at the calibration drift for one frame as defined by Nac2
* debug: This was a custom sequence that's still made to be tweaked. It was when I was looking at the notch output from the spectrometer for one bin and seeing the oscillation and other specific tests when trying to get calibration to work

The main point of this script is to do these measurements, get plots or at least data that can be analyzed later, and end

### `lusee_power_read.py`
This script is run like:
```console
python3 lusee_power_read.py config/config_power.json true
```

The reason it needs a config file is because it has the option of doing a full `spectrometer_simple` test beforehand, so that there is a record of what type of signal was at the ADC inputs, and other PFB characteristics when putting the power figures in context. It also needs the ADC stats parameters for reliable output.

The last parameter is a true/false for whether the new emulator board is being used. False means that the original stub adapter board is being used, which polls the voltages and thermistors in a certain way. True means that the new emulator board is used which has different ADCs and I2C schemes for getting those values.

### `lusee_bootloader.py`
This script is run like:
```console
python3 lusee_bootloader.py /home/eraguzin/Documents/microcontroller/output.hex
```

There are a number of options you can do in the bootloader, too many to parametrize. So the user is encouraged to alter the `if __name__ == "__main__":` sequence at th ebottom of the file. The user can have the sequence:
* Go to bootloader mode
* Read back the programs loaded in Flash
* Delete a region
* Write a hex file to a flash region
* Choose a region to put into memory
* Read back a hex file in flash
* Load a specific flash region

It's up to the user how they want it done. The functions are in the file, and various examples are in the `if __name__ == "__main__":` commented out. The file argument is needed if the user wishes to load a new hex file to a region of memory, or read back the program on flash and compare it to a hex file.
