"""
    Todo
"""

import argparse
import json

from ssh_agent import ssh_agent

class ssh_deployer():
    """
        Todo
    """
    def __init__(self, verbose=False):
        self.verbose = verbose

        f = open("ssh_deployer_init.json")
        raw_init_json = json.load(f)

        self._parse_init_json(init_json=raw_init_json)

        f.close()

        self.ssh_agent = ssh_agent(host=self.ssh_host, username=self.ssh_user, verbose=self.verbose)

    def __del__(self):
        del self.ssh_agent

    # ////////////////////// Run ////////////////////// #

    def run(self):
        # Currently this is just for testing
        self.ssh_agent.list_directory(args="-al")
        self.ssh_agent.run_python(path_to_python="Desktop/hello.py", print_stdout=True, sudo=True)

    # ////////////////////// Helpers ////////////////////// #

    def _parse_init_json(self, init_json):
        if self.verbose: print("Parsing init:")

        self.ssh_host = init_json["SSH Connection"]["Host"]
        if self.verbose: print("\tHost: {}".format(self.ssh_host))
        self.ssh_user = init_json["SSH Connection"]["User"]
        if self.verbose: print("\tUser: {}".format(self.ssh_user))

        self.deployment_local = init_json["Deployment"]["Local Path"]
        if self.verbose: print("\tLocal path: {}".format(self.deployment_local))
        self.deployment_server = init_json["Deployment"]["Server Path"]
        if self.verbose: print("\tServer path: {}".format(self.deployment_server))

        if self.verbose: print("Done parsing init")


def main(verbose=False):
    ssh_dep = ssh_deployer(verbose=verbose)
    ssh_dep.run()
    del ssh_dep

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False, help='Turns on verbosity')

    args = parser.parse_args()

    main(verbose=args.verbose)