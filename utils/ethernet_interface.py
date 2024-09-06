import queue
from ethernet_comm import LuSEE_ETHERNET
from ethernet_processing import LuSEE_PROCESSING

class LuSEE_INTERFACE:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Class created")

        self.comm = LuSEE_ETHERNET()
        self.processing = LuSEE_PROCESSING()

    def write_reg(self, reg, val):
        write_dict = {"command": "write",
                      "reg": int(reg),
                      "val": int(val)}
        self.comm.send_queue.put(write_dict)

    def read_reg(self, reg):
        read_dict = {"command": "read",
                      "reg": int(reg)}
        self.comm.send_queue.put(read_dict)

        while not self.comm.stop_event.is_set():
            resp = self.processing.reg_output_queue.get()
            self.processing.reg_output_queue.task_done()
            if resp is self.processing.stop_signal:
                self.logger.debug(f"read_reg has been told to stop. Exiting...")
                break
            if (resp["reg"] == reg):
                return resp["data"]
            else:
                self.logger.warning(f"Read requested for register {reg}, but received {resp}")
                break

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = '../config/config_logger.ini'
    config_path = os.path.join(script_dir, relative_path)
    logging.config.fileConfig(config_path)

    e = LuSEE_INTERFACE()

    e.write_reg(0x121, 0x69)
    print("Wrote")
    time.sleep(1)
    e.read_reg(0x121)

    e.write_reg(122, 68)
    e.read_reg(122)
