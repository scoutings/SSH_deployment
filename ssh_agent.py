"""
    Todo
"""

import argparse
import paramiko

class ssh_agent():
    """
        Todo
    """
    def __init__(self, host, username, password=None, verbose=False):

        self.host = host
        self.username = username
        self.password = password
        self.verbose = verbose

        self._ssh_connect()

        self.streams = {
            "in": None,
            "out": None,
            "err": None
        }

    def __del__(self):
        # Closes connection with SSh Server
        if self.verbose: print("\nClosing SHH Connection")
        self.ssh.close()
        if self.verbose: print("Connection to {} closed.\n".format(self.host))

    # ////////////////////// Commands ////////////////////// #

    def list_directory(self, directory=""):
        self._run_command("ls -al {}".format(directory))
        self._print_stdout()

    # ////////////////////// Helpers ////////////////////// #

    def _run_command(self, command):
        stdin, stdout, stderr = self.ssh.exec_command(command)
        self.streams["in"] = stdin
        self.streams["out"] = stdout.readlines()
        self.streams["err"] = stderr.readlines()

    def _print_stdout(self):
        if self.streams["out"]:
            for line in self.streams["out"]:
                print(line, end='')
        else:
            print("!!! WARNING: stdout is empty !!!")

    def _ssh_connect(self):
        try:
            if self.verbose: print("\nSSH Connecting to: Host-{}, Username-{}, password-{}".format(self.host, self.username, self.password))
            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.connect(hostname=self.host, username=self.username, password=self.password)
            if self.verbose: print("Connected\n")
        except Exception as e:
            print("\n!!! ERROR: Unable to SSH connect; error message: [{}] !!!\n".format(e))

def main(host, username, password=None, verbose=False):
    ssh = ssh_agent(host=host, username=username, password=password, verbose=verbose)
    ssh.list_directory()
    del ssh

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-H', '--host', dest='host', action='store', required=True, help='Host of SSH Server to connect to')
    parser.add_argument('-U', '--username', dest='username', action='store', required=True, help='Username used for SSH connection')
    parser.add_argument('-p', '--password', dest='password', action='store', required=False, default=None, help='Password used for SSH Connection')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False, help='Turns on verbosity')

    args = parser.parse_args()

    main(host=args.host, username=args.username, password=args.password, verbose=args.verbose)