#!/usr/bin/env python3

import json
import os

from schema import Schema, SchemaError

SSH_CONNECTION_CFG_GROUP = "SSH Connection"
HOST_CFG_KEY = "Host"
USER_CFG_KEY = "User"

DEPLOYMENT_CFG_GROUP = "Deployment"
LOCAL_REPO_PATH_CFG_KEY = "Local Repo Path"
SERVER_REPO_PATH_CFG_KEY = "Server Repo Path"
IGNORED_FILES_CFG_KEY = "Ignored Files"
DO_NOT_DELETE_CFG_KEY = "Do Not Delete"

CONFIG_CFG_GROUP = "Config"
PAUSE_CFG_KEY = "Pause"
SHUTDOWN_CFG_KEY = "Shutdown"
LOOP_DELAY_CFG_KEY = "Loop Delay"

CFG_FILE_VALIDATION = Schema({
    SSH_CONNECTION_CFG_GROUP: {
        HOST_CFG_KEY: str,
        USER_CFG_KEY: str
    },
    DEPLOYMENT_CFG_GROUP: {
        LOCAL_REPO_PATH_CFG_KEY: str,
        SERVER_REPO_PATH_CFG_KEY: str,
        IGNORED_FILES_CFG_KEY: list,
        DO_NOT_DELETE_CFG_KEY: list
    },
    CONFIG_CFG_GROUP: {
        PAUSE_CFG_KEY: bool,
        SHUTDOWN_CFG_KEY: bool,
        LOOP_DELAY_CFG_KEY: int
    }
})

class InitFileParser():

    def __init__(self, init_file_path):

        self.init_file_path = init_file_path

        self.attributes = {
            "ssh_host": None,
            "ssh_user": None,
            "deployment_local": None,
            "deployment_server": None,
            "ignore_files": None,
            "do_not_delete": None
        }

        self.parse_init_file()

    def parse_init_file(self):
        """
            Todo Please
        """
        ret_val = False

        try:
            init_json_file = open(self.init_file_path)
            init_json = json.load(init_json_file)

            try:

                CFG_FILE_VALIDATION.validate(init_json)

                self.attributes["ssh_host"] = init_json[SSH_CONNECTION_CFG_GROUP][HOST_CFG_KEY]

                self.attributes["ssh_user"] = init_json[SSH_CONNECTION_CFG_GROUP][USER_CFG_KEY]

                deployment_local = init_json[DEPLOYMENT_CFG_GROUP][LOCAL_REPO_PATH_CFG_KEY]
                self.attributes["deployment_local"] = os.path.abspath(deployment_local) + "/"

                deployment_server = init_json[DEPLOYMENT_CFG_GROUP][SERVER_REPO_PATH_CFG_KEY]
                self.attributes["deployment_server"] = os.path.abspath(deployment_server) + "/"

                ignore_files = init_json[DEPLOYMENT_CFG_GROUP][IGNORED_FILES_CFG_KEY]
                self.attributes["ignore_files"] = [os.path.abspath(self.attributes["deployment_local"] + "/" + ignore_file) for ignore_file in ignore_files]

                self.attributes["do_not_delete"] = init_json[DEPLOYMENT_CFG_GROUP][DO_NOT_DELETE_CFG_KEY]

                ret_val = True

            except SchemaError as e:
                print("!!! ERROR: CFG file not correct format; Schema Error: [{}] !!!".format(e))

            init_json_file.close()

        except Exception as e:
            print("!!! ERROR: An error occurred when parsing init file [{}] !!!".format(e))

        return ret_val

    def parse_cfg_from_init_json(self):
        """
            Todo Please
        """

        pause_value = None
        shutdown_value = None
        loop_delay_value = None

        try:
            init_json_file = open(self.init_file_path)
            init_json = json.load(init_json_file)

            try:

                CFG_FILE_VALIDATION.validate(init_json)

                pause_value = init_json[CONFIG_CFG_GROUP][PAUSE_CFG_KEY]

                shutdown_value = init_json[CONFIG_CFG_GROUP][SHUTDOWN_CFG_KEY]

                loop_delay_value = init_json[CONFIG_CFG_GROUP][LOOP_DELAY_CFG_KEY]

            except SchemaError as e:
                print("!!! ERROR: CFG file not correct format; Schema Error: [{}] !!!".format(e))

            init_json_file.close()

        except Exception as e:
            print("!!! ERROR: An error occurred when parsing init file [{}] !!!".format(e))

        return pause_value, shutdown_value, loop_delay_value

    def __getattr__(self, item):
        ret_val = None
        if item in self.attributes:
            ret_val = self.attributes[item]
        else:
            raise AttributeError("No such attribute: " + item)
        return ret_val

if __name__ == "__main__":

    # Testing purposing
    fp = InitFileParser(init_file_path="../../ssh_deployer_init.json")
    print(fp.ssh_host)
    print(fp.parse_cfg_from_init_json())