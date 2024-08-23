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

"reset": true or false, whether you want the test to start with a full system reset. It can take up to 5 seconds.
"pcb": `red` or `green`, there are 2 versions of the FPGA Mezzannine. `red` was the old one, all final versions will be `green`.

"adc_num": "When using the ADC stats system, this is the value that goes to register 0x321. It's interpreted as a hex value, so use 0xFFFE for example"
"adc_high": "When using the ADC stats system, this is the value that goes to register 0x322. It's interpreted as a hex value, so use 0x3FFF for example"
"adc_low": "When using the ADC stats system, this is the value that goes to register 0x323. It's interpreted as a hex value, so use 0x0 for example"

"mux1_in1": "Sets register 0x500 according to which integer input is specified here for the P side"
"mux1_in2": "Sets register 0x500 according to which integer input is specified here for the N side"
"mux1_gain": "Sets register 0x500 according to which integer input is specified here for the gain"
"Similar for mux2, 3, and 4

"adc1_save_data": true,
"adc1_plot": true,
"adc1_plot_show": false,
"adc1_plot_save": true,
"adc1_plot_overlay": false,

"pfb_averages": 10,
"notch_filter": true,
"notch_subtract_disable": false,
"notch_averages": 4,
"sticky_errors": true,
"pfb_test_mode": false,

"pfb1_main_index": "0x18",
"pfb1_notch_index": "0x18",
"pfb2_main_index": "0x18",
"pfb2_notch_index": "0x18",
"pfb3_main_index": "0x18",
"pfb3_notch_index": "0x18",
"pfb4_main_index": "0x18",
"pfb4_notch_index": "0x18",

"pfb5_main_index": "0x18",
"pfb5_notch_index": "0x18",
"pfb6_main_index": "0x18",
"pfb6_notch_index": "0x18",
"pfb7_main_index": "0x18",
"pfb7_notch_index": "0x18",
"pfb8_main_index": "0x18",
"pfb8_notch_index": "0x18",

"pfb9_main_index": "0x18",
"pfb9_notch_index": "0x18",
"pfb10_main_index": "0x18",
"pfb10_notch_index": "0x18",
"pfb11_main_index": "0x18",
"pfb11_notch_index": "0x18",
"pfb12_main_index": "0x18",
"pfb12_notch_index": "0x18",

"pfb13_main_index": "0x18",
"pfb13_notch_index": "0x18",
"pfb14_main_index": "0x18",
"pfb14_notch_index": "0x18",
"pfb15_main_index": "0x18",
"pfb15_notch_index": "0x18",
"pfb16_main_index": "0x18",
"pfb16_notch_index": "0x18",

"pfb1_fpga_save_data": true,
"pfb1_fpga_plot": true,
"pfb1_fpga_plot_show": false,
"pfb1_fpga_plot_save": true,

"pfb2_fpga_save_data": true,
"pfb2_fpga_plot": true,
"pfb2_fpga_plot_show": false,
"pfb2_fpga_plot_save": true,

"pfb3_fpga_save_data": true,
"pfb3_fpga_plot": true,
"pfb3_fpga_plot_show": false,
"pfb3_fpga_plot_save": true,

"pfb4_fpga_save_data": true,
"pfb4_fpga_plot": true,
"pfb4_fpga_plot_show": true,
"pfb4_fpga_plot_save": true,

"pfb_sw_save_data": false,
"pfb_sw_plot": true,
"pfb_sw_plot_show": true,
"pfb_sw_plot_save": true
```
