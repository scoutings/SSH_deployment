"""
    Created by Justin Marion 2021.

    This python file holds the ssh_deployer. The ssh_deployer is meant to be ran in permanence as a deployer to
    an ssh server in order to have a copy of a working local repo on another machine.

    The ssh_deployer will take a path to its init file as ana argument. This file must follow a particular format
    and must hold the following information:

        - The host name of the ssh server.
        - The name of the user that will be used when establishing an ssh connection.
        - The path to a local repo that will be copied to the ssh server.
        - The path to the local in the ssh server that the repo will be copied to.
        - A list of all ignored files that will be ignored by the deployer.

    The deployer will run in an infinite loop until the init file specifies to be shutdown and will constantly update
    the repo on the server with any changes made to the local repo.
"""

import argparse
import datetime
import json
import os
import time

from schema import Schema, SchemaError

from ssh_agent import ssh_agent

SSH_CONNECTION_CFG_GROUP = "SSH Connection"
HOST_CFG_KEY = "Host"
USER_CFG_KEY = "User"

DEPLOYMENT_CFG_GROUP = "Deployment"
LOCAL_REPO_PATH_CFG_KEY = "Local Repo Path"
SERVER_REPO_PATH_CFG_KEY = "Server Repo Path"
IGNORED_FILES_CFG_KEY = "Ignored Files"

CFG_FILE_VALIDATION = Schema({
    SSH_CONNECTION_CFG_GROUP: {
        HOST_CFG_KEY: str,
        USER_CFG_KEY: str
    },
    DEPLOYMENT_CFG_GROUP: {
        LOCAL_REPO_PATH_CFG_KEY: str,
        SERVER_REPO_PATH_CFG_KEY: str,
        IGNORED_FILES_CFG_KEY: list
    }
})

class ssh_deployer():
    """
        This is the ssh_deployer class. When instantiated, it will parse the init json file and Establish a connection
        with the given server. Calling the run() method will start an infinite loop that will constantly update a repo
        on the serve based on the repo in local.
    """
    def __init__(self, cfg_path, verbose=False):

        self.verbose = verbose

        self.ssh_host = None
        self.ssh_user = None
        self.deployment_local = None
        self.deployment_server = None
        self.ignore_files = None
        self._parse_init_json(init_json_path=cfg_path)

        self.ssh_agent = ssh_agent(host=self.ssh_host, username=self.ssh_user, verbose=self.verbose)

    def __del__(self):
        del self.ssh_agent

    # ////////////////////// Run ////////////////////// #

    def run(self):
        """
            This is the main method that will run in permanence until told to shutdown. The work flow od this method is to
            first check the structure of both repos local and on the server. It will instantly compare the two structures.
            If the two differ the method will use some logic to find out the actions needed to take on the repo deployed
            on the server to make the two structure similar.
        """

        last_repo_update = datetime.datetime.now()

        while True:

            self._loop_print(message="+---------- Start of loop ----------+")

            # Check the structures of each repo
            scan_local_repo = self._get_local_directory_structure(directory_path=self.deployment_local)
            scan_server_repo = self.ssh_agent.get_server_directory_structure(self.deployment_server)

            self._loop_print(message="Server repo structure:")
            print(json.dumps(scan_server_repo, indent=4))

            # If they differ -> investigate
            if scan_local_repo != scan_server_repo:

                # Get all actions needed to be done on the server repo.
                files_to_copy = self._get_copy_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)
                files_to_del = self._get_delete_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)

                for file in files_to_copy:
                    local_file = self.deployment_local + file
                    server_dir = os.path.dirname(self.deployment_server + file)
                    self.ssh_agent.copy_file_to_server(local_file=local_file, server_path=server_dir)

                for file in files_to_del:
                    server_file = self.deployment_server + file
                    self.ssh_agent.delete_file_from_server(file_path=server_file)

            else:
                self._loop_print(message="Repos match -> no actions needed")

            self._loop_print(message="Sleeping...")
            time.sleep(3)

            self._loop_print(message="+---------- End of loop ----------+")

    # ////////////////////// Helpers ////////////////////// #

    def _get_all_directory_paths(self, directory_tree):
        """
            This method takes in a directory structure and returns the path to each file in the directory as list of strings.

            :param dict directory_tree: This is a directory structure in a dictionary.

            :return: A list of all paths to each file in the dictionary.
        """
        ret_val = []

        # Iterate through the directory and append to the ret_val list with the path to each file
        for name, element in directory_tree.items():

            # If the element is a directory then recursively call the method and append to the two lists together
            if type(element) == dict:

                new_files = self._get_all_directory_paths(directory_tree=element)
                new_files = [name + "/" + file for file in new_files]
                ret_val += new_files

            # If the element is a file then we add the file name to the list
            else:

                ret_val.append(name)

        return ret_val

    def _get_copy_actions_from_diff(self, local_tree, server_tree, ):
        """
            This method will go through each file in the local repo and check to see if the same file exists in the server
            repo. It will the use the logic below to determine and return a list of files to copy over to the server repo.

                If the server does not have the file -> file needs to be copied to the server.
                If the server has the file but they differ -> file needs to be copied to the sever.
                If the server has the file and the are the same -> no action.

            :param dict local_tree: The repo structure of the repo on the local machine.
            :param server_tree: The repo structure of the repo on the server machine.

            :return: A list of files needed to be copied on the server machine.
        """

        ret_val = []

        # Iterate through each element of the local repo
        for element_name, element_value in local_tree.items():

            # Get some boolean values to perform logic above.
            element_exists_in_server = element_name in server_tree.keys()
            is_dir = type(element_value) == dict
            elements_differ = None
            both_are_dirs = None
            # If the element exists in the server we can update the two boolean values set to None above
            if element_exists_in_server:
                elements_differ = element_value != server_tree[element_name]
                both_are_dirs = type(element_value) == dict and type(server_tree[element_name]) == dict


            if not element_exists_in_server:

                # If the element does not exist on the server repo and is a directory we get the paths of all files
                # in the directory and add them all to the copy list
                if is_dir:

                    new_actions = self._get_all_directory_paths(directory_tree=element_value)
                    new_actions = [element_name + "/" + copy_path for copy_path in new_actions]
                    ret_val += new_actions

                # If the element does not exist on the sever repo and is a file we add it to the copy list.
                else:

                    ret_val.append(element_name)

            # Else, the element does exist in the server so we check if the elements differ
            elif elements_differ:

                # If the elements are both directories then we recursively call this method to further get all needed
                # copy actions
                if both_are_dirs:

                    new_actions = self._get_copy_actions_from_diff(local_tree=element_value, server_tree=server_tree[element_name])
                    new_actions = [element_name + "/" + copy_path for copy_path in new_actions]
                    ret_val += new_actions

                # Otherwise if the elements differ add to the copy list
                else:

                    ret_val.append(element_name)

        return ret_val

    def _get_delete_actions_from_diff(self, local_tree, server_tree):
        """
            This method will go through each elements in the server repo structure and will compare with the local repo
            structure. It will use some logic to determine what files need to be deleted from the server repo in order to
            keep both structures consistent.

                If the element in the server does not exist in the local repo -> element needs to the deleted from the server
                If the element is a directory -> recursively call the method to find any files needed to be deleted

            :param dict local_tree: The repo structure of the repo on the local machine.
            :param dict server_tree: The repo structure of the repo on the server machine.

            :return: A list of files/directories needed to be deleted on the serer machine.
        """
        ret_val = []

        # Go through each element in the server repo
        for element_name, element_value in server_tree.items():

            # Perform some boolean operations to perform logic
            element_in_local = element_name in local_tree.keys()
            element_is_dir = type(element_value) == dict

            # If the element does not exist in local repo, we must deleted it from the server
            if not element_in_local:

                ret_val.append(element_name)

            # Else if it exists in the local repo and it is a directory, recursively call the method to find any deleted files
            elif element_is_dir:

                new_actions = self._get_delete_actions_from_diff(local_tree=local_tree[element_name], server_tree=element_value)
                new_actions = [element_name + "/" + delete_path for delete_path in new_actions]
                ret_val += new_actions

        return ret_val

    def _get_local_directory_structure(self, directory_path):
        """
            This method will use the os library to scan the local directory and populate a directory structure of the local
            repo. The structure of the repo will be denoted by a dictionary with each key being the name of an element in
            the repo. The value to each element will either be an integer representing the file size of element, or a
            dictionary representing the directory of the element. Therefore checking the type of the value of a key in
            repo structure will let you know whether the element is either a directory or a file. If while going through the
            repo, an element is a part of the ignored files list, it is skipped and will not appear in the returned structure.

            example_repo_structure = {
                "foo": 42,
                "bar": { ... }
            }

            :param str directory: The path to the local directory/repo.

            :return: The structure of the repo in type dictionary.
        """

        ret_val = {}

        # Scan te directory and iterate through all elements
        directory_scan = os.scandir(directory_path)
        for element in directory_scan:

            element_name = element.name

            # If the name is not a a part of the ignored files list we check the structure
            element_path = os.path.abspath(directory_path + element_name)
            if element_path not in self.ignore_files:

                # If the element is a directory we recursively call this method to get the structure of the directory
                if element.is_dir():

                    dir_full_path =  os.path.abspath("{}/{}".format(directory_path, element_name))
                    ret_val[element_name] = self._get_local_directory_structure(directory_path=dir_full_path)

                # If the element is a file, we set the element's value to the file size
                elif element.is_file():

                    element_stat = element.stat()
                    ret_val[element_name] = element_stat.st_size

                # else print the file size is not recognized, this is for debugging.
                else:
                    print("!!! ERROR: Did not recognize [{}] element type in directory: [{}] !!!".format(element_name, directory_path))

        return ret_val

    def _parse_init_json(self, init_json_path):
        """
            This method will use the Schema library to validate the CFG file being passed to the deployer. Once
            validated the init file will be parsed to store the information in the file.

            :param str init_json_path: Path to the init file to be parsed.

            :return: True / False based on success
        """
        ret_val = False

        if self.verbose: print("Parsing init:")

        try:
            init_json_file = open(init_json_path)
            init_json = json.load(init_json_file)

            try:

                CFG_FILE_VALIDATION.validate(init_json)

                self.ssh_host = init_json[SSH_CONNECTION_CFG_GROUP][HOST_CFG_KEY]
                if self.verbose: print("\t{}: {}".format(HOST_CFG_KEY, self.ssh_host))

                self.ssh_user = init_json[SSH_CONNECTION_CFG_GROUP][USER_CFG_KEY]
                if self.verbose: print("\t{}: {}".format(USER_CFG_KEY, self.ssh_user))

                self.deployment_local = init_json[DEPLOYMENT_CFG_GROUP][LOCAL_REPO_PATH_CFG_KEY]
                self.deployment_local = os.path.abspath(self.deployment_local) + "/"
                if self.verbose: print("\t{}: {}".format(LOCAL_REPO_PATH_CFG_KEY, self.deployment_local))

                self.deployment_server = init_json[DEPLOYMENT_CFG_GROUP][SERVER_REPO_PATH_CFG_KEY]
                self.deployment_server = os.path.abspath(self.deployment_server) + "/"
                if self.verbose: print("\t{}: {}".format(SERVER_REPO_PATH_CFG_KEY, self.deployment_server))

                self.ignore_files = init_json[DEPLOYMENT_CFG_GROUP][IGNORED_FILES_CFG_KEY]
                self.ignore_files = [os.path.abspath(self.deployment_local + "/" + ignore_file) for ignore_file in self.ignore_files]
                if self.verbose: print("\t{}: {}".format(IGNORED_FILES_CFG_KEY, self.ignore_files))

                ret_val = True

            except SchemaError as e:
                print("!!! ERROR: CFG file not correct format; Schema Error: [{}] !!!".format(e))

            init_json_file.close()

        except Exception as e:
            print("!!! ERROR: An error occurred when parsing init file [{}] !!!".format(e))

        return ret_val

    def _loop_print(self, message):
        """
            This method is a simple wrapper around print that will add a time stamp to the front of the message.

            :param message: Message to print.

        """
        current_time = datetime.datetime.now()
        current_timestamp = current_time.strftime("%Y/%m/%d/%H/%M/%S")
        print("{}: {}".format(current_timestamp, message))

def main(cfg_path, verbose=False):
    ssh_dep = ssh_deployer(cfg_path=cfg_path, verbose=verbose)
    ssh_dep.run()
    del ssh_dep

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False, help='Turns on verbosity')
    parser.add_argument('-c', '--config_path', dest='cfg_path', action='store', required=True, help='Specify the path of the ssh_deployer_init.json file')

    args = parser.parse_args()

    main(cfg_path=args.cfg_path, verbose=args.verbose)