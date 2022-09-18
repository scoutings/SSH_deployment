#!/usr/bin/env python3

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
import re

class SSHAgent():
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

        # Closed connection with the SSH server
        if self.verbose: print("\nClosing SHH Connection")
        self.ssh.close()
        if self.verbose: print("Connection to {} closed.".format(self.host))

        # Closes SFTP connection
        if self.verbose: print("\nClosing SFTP Connection")
        self.sftp.close()
        if self.verbose: print("Closed")

    def get_server_directory_structure(self, directory, do_not_delete):
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

            if element_name not in do_not_delete:

                # If the element is a directory we recursively call this method to get the structure of the directory
                if stat.S_ISDIR(element.st_mode):

                    ret_val[element_name] = self.get_server_directory_structure(directory="{}/{}".format(directory, element_name), do_not_delete=do_not_delete)

                # If the element is a file, we set the element's value to the file size
                elif stat.S_ISREG(element.st_mode):

                    self._run_command(f"sha1sum {directory}/{element_name}", get_pty=True)
                    ret_val[element_name] = self._extract_hash(self.streams["out"].readlines()[0])

                else:

                    print("!!! ERROR: Did not recognize [{}] element type in directory: [{}] !!!".format(element_name, directory))

        return ret_val

    def copy_file_to_server(self, local_file, server_path):
        """
            This method will use the put() method to copy a file over to the ssh server from the local machine.

            :param str local_file: The local path to the file that needs to be copied.
            :param str server_path: The server path to the local to copy the local file.

            Todo remove the tmp file location as I do not wantt o support sudo right now

        """

        if self.verbose: print("Copying {} to {}/".format(local_file, server_path))

        server_path_exists = self.file_exists_on_server(file_path=server_path)

        if not server_path_exists:
            self._run_command(command="mkdir {}".format(server_path))

        file_name = os.path.split(local_file)[1]
        self.sftp.put(local_file, "/tmp/{}".format(file_name))
        self._run_command("mv /tmp/{} {}/".format(file_name, server_path), get_pty=True)

    def delete_file_from_server(self, file_path):
        """
            This method will delete a file in the ssh server.

            :param str file_path: The path to the file that needs to be deleted
        """
        if self.verbose: print("Deleting {}".format(file_path))
        self._run_command("rm -rf {}".format(file_path), get_pty=True)

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

    def _run_command(self, command, get_pty=False):
        """
            This is a simple wrapper method around exec_command() that stores stdin, stdout, and stderr in the streams
            class variable.

            :param str command: Command to run
        """

        stdin, stdout, stderr = self.ssh.exec_command(command, get_pty=get_pty)
        # print(stdout.readlines())
        self.streams["in"] = stdin
        self.streams["out"] = stdout
        self.streams["err"] = stderr

    def _ssh_connect(self):
        """
            This method will connect to an ssh server given its class variables instantiated int the init method.
            If an error occurs during connection, a message is printed.
        """

        if self.verbose: print("\nSSH Connecting to: Host-{}, Username-{}".format(self.host, self.username))
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.connect(hostname=self.host, username=self.username, password="")
        if self.verbose: print("Connected")

    def _ssh_sftp_connect(self):
        """
            This method will use the open_sftp() method to establish an SFTP connection with the ssh server

        """

        if self.verbose: print("\nSFTP Connecting")
        self.sftp = self.ssh.open_sftp()
        if self.verbose: print("Connected")

    def _extract_hash(self, output):
        ret_val = None
        hash = re.findall("[0-9a-f]{5,40}", output)
        if  len(hash) == 1:
            ret_val = hash[0]
        return ret_val

def main(host, username, verbose=False):
    """
        This is currently only used for testing.
    """
    ssh = SSHAgent(host=host, username=username, verbose=verbose)
    print(ssh.file_exists_on_server(file_path="/home/justin/deployer_repos/"))
    print(ssh.get_server_directory_structure("/home/justin/deployer_repos/", []))
    del ssh

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-H', '--host', dest='host', action='store', required=True, help='Host of SSH Server to connect to')
    parser.add_argument('-U', '--username', dest='username', action='store', required=True, help='Username used for SSH connection')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False, help='Turns on verbosity')

    args = parser.parse_args()

    main(host=args.host, username=args.username, verbose=args.verbose)
