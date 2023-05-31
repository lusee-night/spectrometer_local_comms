import subprocess
import os
import sys
#python3 move_to_optiplex.py LuSEE_Spectrometer 6 LuSEE_Spectrometer.prjx
class OPTIPLEX:
    def __init__(self, move_dir, action, proj_file = None):
        self.remote_location = "lusee@130.199.33.247"
        self.remote_directory = "/home/lusee/etamura/LuSEE/FPGA"
        self.remote_libero = "/usr/local/microchip/Libero_SoC_v2022.3/Libero/bin/libero"
        self.local_libero = "/usr/local/microchip/Libero_SoC_v2022.3/Libero/bin64/libero"
        self.tcl_name = "run_program.tcl"

        self.move_dir = move_dir
        self.action = action
        self.proj_file = proj_file
        #scp -pr ~/nextcloud/LuSEE/Libero/EM_TEST/LuSEE_Spectrometer/ lusee@130.199.33.247:/home/lusee/etamura/LuSEE/FPGA
    def get_dir_status(self):
        sshProcess = subprocess.Popen(["ssh", "-T", f"{self.remote_location}"],
                                      stdin = subprocess.PIPE,
                                      stdout = subprocess.PIPE,
                                      text = True,
                                      universal_newlines = True,
                                      bufsize=0)
        sshProcess.stdin.write(f"cd {self.remote_directory}\n")
        sshProcess.stdin.write("pwd\n")
        sshProcess.stdin.write("ls\n")
        output, errors = sshProcess.communicate()

        #Get the location of the pwd output so that I can skip all the initial junk the ssh connection spits out
        result_location = output.find(self.remote_directory)
        dir_location = output.find(self.move_dir, result_location)
        if (dir_location != -1):
            print(f"{self.move_dir} already exists at {self.remote_directory}. Deleting...")
            self.delete_remote_dir()

    def delete_remote_dir(self):
        sshProcess = subprocess.Popen(["ssh", "-T", f"{self.remote_location}"],
                                      stdin = subprocess.PIPE,
                                      stdout = subprocess.PIPE,
                                      text = True,
                                      universal_newlines = True,
                                      bufsize=0)
        sshProcess.stdin.write(f"cd {self.remote_directory}\n")
        sshProcess.stdin.write(f"rm -r {self.move_dir}\n")
        output, errors = sshProcess.communicate()
        if (errors == None):
            print("Deleted successfully")
        else:
            print(f"Errors while deleting: {errors}")

    def scp_input(self, fordir):
        comp = subprocess.run(["scp", "-pr", fordir, f"{self.remote_location}:{self.remote_directory}"])
        if (comp.returncode != 0):
            print("Output was:")
            print(comp.stdout)
            print("Error was:")
            print(comp.stderr)
            raise AssertionError("Error returned from 'scp' command")
        else:
            print("Successfully scp'd files to remote computer")

    def compile_locally(self):
        subprocess.run([self.local_libero, f"script:{self.tcl_name}",
                        f"script_args:{self.project_location} {self.project_file} 1",
                        "logfile:make_libero.log"])

    def remote_program(self):
        self.scp_input(self.tcl_name)

        sshProcess = subprocess.Popen(["ssh", "-T", f"{self.remote_location}"],
                                stdin = subprocess.PIPE,
                                stdout = subprocess.PIPE,
                                text = True,
                                universal_newlines = True,
                                bufsize=1)
        sshProcess.stdin.write(f"cd {self.remote_directory}\n")
        sshProcess.stdin.write("export LM_LICENSE_FILE=\"1702@iolicense2.inst.bnl.gov:7180@iolicense2.inst.bnl.gov:7184@iolicense2.inst.bnl.gov\"\n")
        sshProcess.stdin.write(f"{self.remote_libero} script:{self.tcl_name} \"script_args:{self.move_dir} {self.proj_file} 2 logfile:make_libero.log\"\n")
        output, errors = sshProcess.communicate()

        if (errors == None):
            print("Communicated successfully")
        else:
            print(f"Errors while deleting: {errors}")

        print(output)

if __name__ == "__main__":
    move_dir = sys.argv[1]
    action = int(sys.argv[2])
    try:
        proj_file = sys.argv[3]
    except IndexError:
        proj_file = None

    x = OPTIPLEX(move_dir, action, proj_file)

    check_local_compile = action & 0x1
    if (check_local_compile):
        print("Request to compile project locally first")
        x.compile_locally()

    check_move = (action >> 1) & 0x1
    if (check_move):
        print("Request to move project over")
        x.get_dir_status()
        x.scp_input(x.move_dir)

    check_remote_program = (action >> 2) & 0x1
    if (check_remote_program):
        print("Request to program project remotely", flush = True)
        x.remote_program()

    print("Finished")
