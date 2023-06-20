
from ethernet_comm import LuSEE_ETHERNET

class TestSequence:
    def __init__(self):
        self.readout_modes = {
            "ADC1": 1,
            "ADC2": 2,
            "ADC3": 3,
            "ADC4": 4,
            "Counter": 5
            }
        self.connection = LuSEE_ETHERNET()
        self.ADC_PACKETS = 2
        self.tries = 5
        self.bytes_per_packet = 0x7F8

    #Only need to do one in the beginning
    #Takes a few seconds
    def reset(self):
        self.connection.reset()

    def get_data(self, num, header=False):
        i = 0
        while (i < self.tries):
            if (header):
                data, header = self.connection.get_data_packets(num=num, header = header)
                if (data[0] != []):
                    return data, header
                else:
                    print("LuSEE COMM --> No packet response, retrying...")
                    i += 1
            else:
                data = self.connection.get_data_packets(num=num, header = header)
                if (data != []):
                    return data
                else:
                    print("LuSEE COMM --> No packet response, retrying...")
                    i += 1

    def get_adc1_data(self):
        self.connection.set_function(self.readout_modes["ADC1"])
        self.connection.reset_fifo()
        self.connection.load_fifo()
        data = self.get_data(num=self.ADC_PACKETS, header = False)
        print(data)

    def get_adc2_header_data(self):
        self.connection.set_function(self.readout_modes["ADC2"])
        self.connection.reset_fifo()
        self.connection.load_fifo()
        data, header = self.get_data(num=self.ADC_PACKETS, header = True)
        print(header)

    def get_counter_data(self, counter_num):
        packets = (counter_num // self.bytes_per_packet) + 1
        self.connection.set_function(self.readout_modes["Counter"])
        self.connection.set_counter_num(counter_num)
        self.connection.reset_fifo()
        self.connection.load_fifo()
        data, header = self.get_data(num=packets, header = True)
        print(data)
        print(header)

if __name__ == "__main__":
    #arg = sys.argv[1]
    ethernet = TestSequence()
    ethernet.get_adc1_data()
    ethernet.get_adc2_header_data()
    ethernet.get_counter_data(counter_num = 0x840)
