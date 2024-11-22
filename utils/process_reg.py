import binascii
import threading
import queue
import logging
import logging.config

#TODO: Add the register processing from the actual DCB, where the CDI header isn't stripped out.
class LuSEE_PROCESS_REG:
    def __init__(self, parent):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")
        self.readback_register = 0xB #Didn't inherit from ethernet_comm to reduce complexity, but must match that value
        self.parent = parent
        self.stop_event = parent.stop_event
        self.stop_signal = parent.stop_signal
        self.reg_input_queue = parent.reg_input_queue
        self.reg_output_queue = parent.reg_output_queue
        self.dcb_emulator_queue = parent.dcb_emulator_queue

    def process_reg(self):
        name = threading.current_thread().name
        self.logger.debug(f"{name} started")
        while not self.stop_event.is_set():
            data = self.reg_input_queue.get()
            self.reg_input_queue.task_done()
            if data is self.stop_signal:
                self.logger.debug(f"{name} has been told to stop. Exiting...")
                self.reg_output_queue.put(self.stop_signal)
                break
            dataHex = binascii.hexlify(data)
            #If reading, say register 0x290, you may get back
            #029012345678
            #The first 4 bits are the register you requested, the next 8 bits are the value
            #With a DCB emulator, those first 4 bits will be the register on the DCB emulator you requested
            #The register from the spectrometer is lost in the middle
            #Return the data part of the response in integer form (it's just easier)
            response_reg = int(dataHex[0:4],16)
            data_val = int(dataHex[4:12],16)

            response_dict = {"reg": response_reg,
                             "data": data_val}
            self.logger.debug(f"Received {response_dict}")
            if (response_reg != self.readback_register):
                #This queue is the response for when toggling the latch, or actual DCB emulator registers
                self.dcb_emulator_queue.put(response_dict)
            else:
                #This one is when the DCB emulator is reporting on Spectrometer registers
                self.reg_output_queue.put(response_dict)
        self.logger.debug(f"{name} exited")

