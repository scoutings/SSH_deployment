"""
    Created by Justin Marion 2021.

    This python file holds the ssh_agent used to connect and run commands via ssh to a given server.
    Its main() is currently mainly used fo testing during development of the ssh_agent class. This class is a big part
    of the ssh_deployer as this is what is being used to communicate with the server.
"""

import argparse
import paramiko
import os
import stat

class ssh_agent():
    """
        This is the ssh_agent class. It is used to send commands to a given server via ssh.
    """
    def __init__(self, host, username, verbose=False):

        self.host = host
        self.username = username
        self.verbose = verbose

        self.local_host = os.uname()[1]

        self.ssh = None
        self._ssh_connect()
        self.sftp = None
        self._ssh_sftp_connect()

        # Will hold the three main file types on the ssh server.
        self.streams = {
            "in": None,
            "out": None,
            "err": None
        }

        print()

    def __del__(self):

        # Closes SFTP connection
        if self.verbose: print("\nClosing SFTP Connection")
        self.sftp.close()
        if self.verbose: print("Closed")

        # Closed connection with the SSH server
        if self.verbose: print("\nClosing SHH Connection")
        self.ssh.close()
        if self.verbose: print("Connection to {} closed.".format(self.host))

    def print_stdout(self):
        """
            This method will print in real time the contents of stdout. This method will not finish until EOF is reached
            in stdout. If stdout is empty a warning will be printed.
        """

        # Used to determine if stdout is empty
        stdout_empty = True

        # readline will will return until "\n" but will not finish iterating until EOF
        for line in iter(self.streams["out"].readline, ""):

            # Print a line and define stdout as not empty
            self._host_print(line, end="")
            stdout_empty = False

        # If stdout is empty then print warning
        if stdout_empty == True:
            print("!!! WARNING: stdout is empty !!!")

        print()

    def print_stderr(self):
        """
            This method will print the contents of stderr. If stderr is printed a warning will be printed.
        """

        # Read lines until EOF
        stderr = self.streams["err"].readlines()

        # If there is something print print stderr, else warn that stderr is empty
        if stderr:

            for line in stderr:
                self._host_print(line, end="")

        else:

            print("!!! WARNING: stderr is empty !!!")

        print()

    # ////////////////////// Commands ////////////////////// #

    def list_directory(self, directory_path="", args=""):
        """
            This method runs the ls command through ssh on the connected server.

            :param str directory_path: The path to the directory to list.
            :param str args: Desired arguments to the ls command.
        """

        if self.verbose: print("========== List directory ==========")
        self._run_command("ls {} {}".format(args, directory_path))
        self.print_stdout()

    def run_python(self, path_to_python, args="", print_stdout=True, sudo=False):
        """
            This method runs a python file through ssh on the connected server.

            :param str path_to_python: Path to the python file to be ran.
            :param str args: Arguments to the python file when ran if any. Format is same as in shell.
            :param bool print_stdout: Print the programs output.
            :param bool sudo: Run as sudo.
        """

        if self.verbose: print("========== Running python ==========")

        if sudo:
            self._run_command("sudo python3 {} {}".format(path_to_python, args))
        else:
            self._run_command("python3 {} {}".format(path_to_python, args))

        if print_stdout:

            self.print_stdout()

            # Print exit status
            exit_status = self.streams["out"].channel.recv_exit_status()
            self._host_print("Process finished with exit code {}".format(exit_status))

            print()

    def get_server_directory_structure(self, directory):
        """
            This method will use the sftp connection to list the server directory and populate a directory structure of the
            repo. The structure of the repo will be denoted by a dictionary with each key being the name of an element in
            the repo. The value to each element will either be an integer representing the file size of element, or a
            dictionary representing the directory of the element. Therefore checking the type of the value of a key in
            repo structure will let you know whether the element is either a directory or a file. If while going through the
            repo, an element is a part of the ignored files list, it is skipped and will not appear in the returned structure.

            example_repo_structure = {
                "foo": 42,
                "bar": { ... }
            }

            :param str directory: The path to the server directory/repo.

            :return: The structure of the repo in type dictionary.
        """

        ret_val = {}

        # Iterate through all elements in the server repo
        directory_scan = self.sftp.listdir_attr(directory)
        for element in directory_scan:

            element_name = element.filename

            # If the elemnt is a directory we recursively call this method to get the structure of the directory
            if stat.S_ISDIR(element.st_mode):

                ret_val[element_name] = self.get_server_directory_structure(directory="{}/{}".format(directory, element_name))

            # If the element is a file, we set the element's value to the file size
            elif stat.S_ISREG(element.st_mode):

                ret_val[element_name] = element.st_size

            else:

                print("!!! ERROR: Did not recognize [{}] element type in directory: [{}] !!!".format(element_name, directory))

        return ret_val

    def copy_file_to_server(self, local_file, server_path):
        """
            This method will use the put() method to copy a file over to the ssh server from the local machine.

            :param str local_file: The local path to the file that needs to be copied.
            :param str server_path: The server path to the local to copy the local file.

        """

        if self.verbose: print("Copying {} to {}/".format(local_file, server_path))

        server_path_exists = self.file_exists_on_server(file_path=server_path)

        if not server_path_exists:
            self._run_command(command="sudo mkdir {}".format(server_path), get_pty=False)

        file_name = os.path.split(local_file)[1]
        self.sftp.put(local_file, "/tmp/{}".format(file_name))
        self._run_command("sudo mv /tmp/{} {}/".format(file_name, server_path), get_pty=False)

    def delete_file_from_server(self, file_path):
        """
            This method will delete a file in the ssh server.

            :param str file_path: The path to the file that needs to be deleted
        """
        if self.verbose: print("Deleting {}".format(file_path))
        self._run_command("sudo rm -rf {}".format(file_path), get_pty=False)

    def file_exists_on_server(self, file_path):
        """
            This method will check if the fle path given as a parameter exists on the ssh server. It will return T/F.

            :param str file_path: The path to determine if it exists or not.

            :return: T/F based on if the path exists or not.
        """

        ret_val = None

        try:

            self.sftp.stat(file_path)

        except IOError as e:

            ret_val = False

        else:

            ret_val = True

        return ret_val

    # ////////////////////// Helpers ////////////////////// #

    def _run_command(self, command, get_pty=True):
        """
            This is a simple wrapper method around exec_command() that stores stdin, stdout, and stderr in the streams
            class variable.

            :param str command: Command to run
        """

        stdin, stdout, stderr = self.ssh.exec_command(command, get_pty=get_pty)
        self.streams["in"] = stdin
        self.streams["out"] = stdout
        self.streams["err"] = stderr

    def _ssh_connect(self):
        """
            This method will connect to an ssh server given its class variables instantiated int the init method.
            If an error occurs during connection, a message is printed.
        """

        try:

            if self.verbose: print("\nSSH Connecting to: Host-{}, Username-{}".format(self.host, self.username))
            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.connect(hostname=self.host, username=self.username)
            if self.verbose: print("Connected")

        except Exception as e:

            print("!!! ERROR: Unable to SSH connect; error message: [{}] !!!".format(e))

    def _ssh_sftp_connect(self):
        """
            This method will use the open_sftp() method to establish an SFTP connection with the ssh server

        """

        try:

            if self.verbose: print("\nSFTP Connecting")
            self.sftp = self.ssh.open_sftp()
            if self.verbose: print("Connected")

        except Exception as e:

            print("!!! ERROR: Unable to create an sftp connection; error message [{}] !!!".format(e))

    def _host_print(self, msg, end="\n"):
        """
            This is a simple helper message used to print a message from the ssh server. The output will clarify that
            the output is from the ssh server host.

            :param str msg: Message to print
            :param str end: Parameter to pass to print()
        """

        print("{}: {}".format(self.host, msg), end=end)

def main(host, username, verbose=False):
    """
        This is currently only used for testing.
    """
    ssh = ssh_agent(host=host, username=username, verbose=verbose)
    print(ssh.file_exists_on_server(file_path="/home"))
    ssh._run_command(command="sudo mkdir /opt/repos/test", get_pty=False)
    del ssh

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-H', '--host', dest='host', action='store', required=True, help='Host of SSH Server to connect to')
    parser.add_argument('-U', '--username', dest='username', action='store', required=True, help='Username used for SSH connection')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False, help='Turns on verbosity')

    args = parser.parse_args()

    main(host=args.host, username=args.username, verbose=args.verbose)
