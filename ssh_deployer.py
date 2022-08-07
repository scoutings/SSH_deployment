#!/usr/bin/env python3
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

from ssh_deployer.__main__ import main

if __name__ == "__main__":

    main()