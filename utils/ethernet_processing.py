import binascii
import threading
import queue
import logging
import logging.config

class LuSEE_PROCESSING:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.debug("Class created")
            self.stop_event = threading.Event()
            self.stop_signal = object()

            self.reg_input_queue = queue.Queue()
            self.data_input_queue = queue.Queue()
            self.hk_input_queue = queue.Queue()

            self.reg_output_queue = queue.Queue()
            self.data_output_queue = queue.Queue()
            self.hk_output_queue = queue.Queue()

            process_thread_settings = [(self.process_reg, "Register Response Processing Thread")]
            self.process_threads = []
            for process_settings in process_thread_settings:
                thread = threading.Thread(target=process_settings[0],
                            name=process_settings[1],
                            daemon = True
                            )
                thread.start()
                self.process_threads.append(thread)

    def stop(self):
        self.logger.debug("Stopping all threads")
        self.stop_event.set()
        self.reg_input_queue.put(self.stop_signal)
        self.data_input_queue.put(self.stop_signal)
        self.hk_input_queue.put(self.stop_signal)

        for i in self.process_threads:
            self.logger.debug(f"Waiting for {i.name} to join")
            i.join()
            self.logger.debug(f"Class sees that {i.name} is done")

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
            #Looks for those first 4 bits to make sure you read the register you're looking for
            #Return the data part of the response in integer form (it's just easier)
            response_reg = int(dataHex[0:3],16)
            data_val = int(dataHex[4:12],16)

            response_dict = {"reg": response_reg,
                             "data": data_val}
            self.logger.debug(f"Received {response_dict}")
            self.reg_output_queue.put(response_dict)
        self.logger.debug(f"{name} exited")
