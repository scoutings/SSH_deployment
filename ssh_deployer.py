"""
    Todo
"""

import argparse
import datetime
import json
import os
import time

from schema import Schema, And, Or, Use, Optional, SchemaError

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
        Todo
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
        Todo
        :return:
        """
        # Todo goal is to run a while true loop and diff

        last_repo_update = datetime.datetime.now()

        while True:
            # Todo loop stats? and print should be prettier

            scan_local_repo = self._get_local_directory_structure(directory=self.deployment_local)

            scan_server_repo = self.ssh_agent.get_server_directory_structure(self.deployment_server)

            if scan_local_repo != scan_server_repo:
                print(); print("=== Diff Detected ===")

                files_to_copy = self._get_copy_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)
                files_to_del = self._get_delete_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)

                for file in files_to_copy:
                    local_file = self.deployment_local + file
                    server_dir = os.path.dirname(self.deployment_server + file)
                    self.ssh_agent.copy_file_to_server(local_file=local_file, server_path=server_dir)

                for file in files_to_del:
                    server_file = self.deployment_server + file
                    self.ssh_agent.delete_file_from_server(file_path=server_file)

                last_repo_update = datetime.datetime.now()

            else:
                print(".", end="")

            time_since_update = datetime.datetime.now() - last_repo_update
            time_to_sleep = .5 if time_since_update.total_seconds() < 5 else 3
            time.sleep(time_to_sleep)

        # scan_local_repo = self._get_local_directory_structure(directory=self.deployment_local)
        # print(); print(json.dumps(scan_local_repo, indent=4))
        #
        # scan_server_repo = self.ssh_agent.get_server_directory_structure(self.deployment_server)
        # print(); print(json.dumps(scan_server_repo, indent=4))
        #
        # copy_paths = self._get_copy_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)
        # print(); print("Copy: {}".format(copy_paths))
        #
        # delete_paths = self._get_delete_actions_from_diff(local_tree=scan_local_repo, server_tree=scan_server_repo)
        # print();print("Delete: {}".format(delete_paths))

    # ////////////////////// Helpers ////////////////////// #

    def _get_all_directory_paths(self, directory_tree):
        """
        Todo
        :param directory_tree:
        :return:
        """
        ret_val = []

        for name, element in directory_tree.items():
            if type(element) == dict:
                new_files = self._get_all_directory_paths(directory_tree=element)
                new_files = [name + "/" + file for file in new_files]
                ret_val += new_files
            else:
                ret_val.append(name)

        return ret_val

    def _get_copy_actions_from_diff(self, local_tree, server_tree, ):
        """
        Todo
        :param local_tree:
        :param server_tree:
        :return:
        """
        ret_val = []

        for element_name, element_value in local_tree.items():

            element_exists_in_server = element_name in server_tree.keys()
            elements_differ = None
            both_are_dirs = None
            is_dir = type(element_value) == dict

            if element_exists_in_server:
                elements_differ = element_value != server_tree[element_name]
                both_are_dirs = type(element_value) == dict and type(server_tree[element_name]) == dict

            if not element_exists_in_server:
                if is_dir:
                    new_actions = self._get_all_directory_paths(directory_tree=element_value)
                    new_actions = [element_name + "/" + copy_path for copy_path in new_actions]
                    ret_val += new_actions
                else:
                    ret_val.append(element_name)
            elif elements_differ:
                if both_are_dirs:
                    new_actions = self._get_copy_actions_from_diff(local_tree=element_value, server_tree=server_tree[element_name])
                    new_actions = [element_name + "/" + copy_path for copy_path in new_actions]
                    ret_val += new_actions
                else:
                    ret_val.append(element_name)

        return ret_val

    def _get_delete_actions_from_diff(self, local_tree, server_tree):
        """
        Todo
        :param local_tree:
        :param server_tree:
        :return:
        """
        ret_val = []

        for element_name, element_value in server_tree.items():

            element_in_local = element_name in local_tree.keys()
            element_is_dir = type(element_value) == dict

            if not element_in_local:
                ret_val.append(element_name)
            elif element_is_dir:
                new_actions = self._get_delete_actions_from_diff(local_tree=local_tree[element_name], server_tree=element_value)
                new_actions = [element_name + "/" + delete_path for delete_path in new_actions]
                ret_val += new_actions

        return ret_val

    def _get_local_directory_structure(self, directory):
        """
            Todo
        :param directory:
        :return:
        """
        ret_val = {}

        directory_scan = os.scandir(directory)
        for element in directory_scan:
            element_name = element.name
            if element_name not in self.ignore_files:
                if element.is_dir():
                    ret_val[element_name] = self._get_local_directory_structure(directory="{}/{}".format(directory, element_name))
                elif element.is_file():
                    element_stat = element.stat()
                    ret_val[element_name] = element_stat.st_size
                else:
                    print("!!! ERROR: Did not recognize [{}] element type in directory: [{}] !!!".format(element_name, directory))

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
                if self.verbose: print("\t{}: {}".format(LOCAL_REPO_PATH_CFG_KEY, self.deployment_local))

                self.deployment_server = init_json[DEPLOYMENT_CFG_GROUP][SERVER_REPO_PATH_CFG_KEY]
                if self.verbose: print("\t{}: {}".format(SERVER_REPO_PATH_CFG_KEY, self.deployment_server))

                self.ignore_files = init_json[DEPLOYMENT_CFG_GROUP][IGNORED_FILES_CFG_KEY]
                if self.verbose: print("\t{}: {}".format(IGNORED_FILES_CFG_KEY, self.ignore_files))

                ret_val = True

            except SchemaError as e:
                print("!!! ERROR: CFG file not correct format; Schema Error: [{}] !!!".format(e))

            init_json_file.close()

        except Exception as e:
            print("!!! ERROR: An error occurred when parsing init file [{}] !!!".format(e))

        return ret_val


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