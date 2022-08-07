#!/usr/bin/env python3

import argparse
import signal
import datetime
import time
import sys
import json
import os

from ssh_deployer.init_file_parser.init_file_parser import InitFileParser
from ssh_deployer.ssh_agent.ssh_agent import SSHAgent

loop_start_msg = "+---------- Start of loop ----------+"
loop_end_msg = "+---------- End of loop ----------+"

running = True


def main():
    
    def loop_print(msg):

        if v:
            current_time = datetime.datetime.now()
            current_timestamp = current_time.strftime("%Y/%m/%d/%H/%M/%S")
            print(f"{current_timestamp}: {msg}")

    signal.signal(signal.SIGINT, sigint_handler)

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i', '--init_path', dest='init_path', action='store', required=True,
                        help='Specify the path of the ssh_deployer_init.json file')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False,
                        help='Turns on verbosity')

    args = parser.parse_args()
    v = args.verbose

    fp = InitFileParser(init_file_path=args.init_path)

    if not fp.parse_init_file():
        raise ValueError("Init file was not correctly parsed")

    ssh_agent = SSHAgent(fp.ssh_host, fp.ssh_user, verbose=v)

    while running:
        loop_print(loop_start_msg)

        pause, shutdown, loop_delay = fp.parse_cfg_from_init_json()

        if shutdown:

            loop_print("Deployer shutting down")
            break

        elif pause:

            loop_print("Deployer is paused")
            pass

        else:

            # Check the structures of each repo
            scan_local_repo = get_local_directory_structure(fp.deployment_local, fp.ignore_files)
            scan_server_repo = ssh_agent.get_server_directory_structure(fp.deployment_server, fp.do_not_delete)

            loop_print("Server repo structure:")
            loop_print(json.dumps(scan_server_repo, indent=4))

            if scan_local_repo != scan_server_repo:

                files_to_copy = get_copy_actions_from_diff(scan_local_repo, scan_server_repo)
                files_to_del = get_delete_actions_from_diff(scan_local_repo, scan_server_repo)

                for file in files_to_copy:
                    local_file = fp.deployment_local + file
                    server_dir = os.path.dirname(fp.deployment_server + file)
                    ssh_agent.copy_file_to_server(local_file, server_dir)

                for file in files_to_del:
                    server_file = fp.deployment_server + file
                    ssh_agent.delete_file_from_server(server_file)

            else:

                loop_print("Repo is up to date")

        loop_print(f"Sleeping {loop_delay}(s)")
        time.sleep(loop_delay)

        loop_print(loop_end_msg)

    del fp
    del ssh_agent

    sys.exit(0)


def get_local_directory_structure(directory_path, ignore_files):
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

        # If the name is not a part of the ignored files list we check the structure
        element_path = os.path.abspath(directory_path + element_name)
        if element_path not in ignore_files:

            # If the element is a directory we recursively call this method to get the structure of the directory
            if element.is_dir():

                dir_full_path = os.path.abspath("{}/{}".format(directory_path, element_name))
                ret_val[element_name] = get_local_directory_structure(dir_full_path, ignore_files)

            # If the element is a file, we set the element's value to the file size
            elif element.is_file():

                element_stat = element.stat()
                ret_val[element_name] = element_stat.st_size

            # else print the file size is not recognized, this is for debugging.
            else:
                print("!!! ERROR: Did not recognize [{}] element type in directory: [{}] !!!".format(element_name, directory_path))

    return ret_val


def get_copy_actions_from_diff(local_tree, server_tree):
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

                new_actions = get_all_directory_paths(element_value)
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

                new_actions = get_copy_actions_from_diff(element_value, server_tree[element_name])
                new_actions = [element_name + "/" + copy_path for copy_path in new_actions]
                ret_val += new_actions

            # Otherwise if the elements differ add to the copy list
            else:

                ret_val.append(element_name)

    return ret_val


def get_delete_actions_from_diff(local_tree, server_tree):
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

            new_actions = get_delete_actions_from_diff(local_tree[element_name], element_value)
            new_actions = [element_name + "/" + delete_path for delete_path in new_actions]
            ret_val += new_actions

    return ret_val


def get_all_directory_paths(directory_tree):
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

            new_files = get_all_directory_paths(element)
            new_files = [name + "/" + file for file in new_files]
            ret_val += new_files

        # If the element is a file then we add the file name to the list
        else:

            ret_val.append(name)

    return ret_val


def loop_print(msg, v):

    if v:
        current_time = datetime.datetime.now()
        current_timestamp = current_time.strftime("%Y/%m/%d/%H/%M/%S")
        print(f"{current_timestamp}: {msg}")


def sigint_handler(signum, frame):

    print("Cleaning up, please wait")
    global running
    running = False


if __name__ == "__main__":
    # This should only be ran for testing
    # main()
    pass
