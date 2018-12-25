#!/usr/bin/python3
#
# Base script for the controller
#

import time, os, sys

from hardware import RFReceiver, AnimatedDisplay

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Must be run as root!",file=sys.stderr)
        exit(5)
    os.nice(-10)
    manager = Manager(AnimatedDisplay(), RFReceiver())
    top = sonos.PlayerSelection(manager.display)
    manager.launch(top)
