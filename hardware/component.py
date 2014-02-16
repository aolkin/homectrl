#
# Base classes for GPIO hardware
#

import RPi.GPIO as gpio
import time

def delay(microseconds):
    time.sleep(microseconds/1000000)

class Component:
    def __init__(self,outpins=(),inpins=()):
        self.__out_pins = outpins
        self.__in_pins = inpins
        self.__initialized = False

    def _checkInit(self,quiet=False):
        if quiet:
            return self.__initialized
        if not self.__initialized:
            raise RuntimeError("This {} has not been initialized yet!".format(
                    self.__class__.__name__))

    def init(self,wait_set_init=False):
        if self.__initialized:
            try:
                self.cleanup()
            finally:
                pass
            
        gpio.setmode(gpio.BOARD)

        for ch in self.__out_pins:
            gpio.setup(ch, gpio.OUT, initial=gpio.LOW)
        for ch in self.__in_pins:
            gpio.setup(ch, gpio.IN, initial=gpio.LOW)

        if not wait_set_init:
            self.__initialized = True

    def set_init(self):
        self.__initialized = True

    def cleanup(self):
        if not self.__initialized:
            return False
        self.__initialized = False
        for ch in self.__out_pins + self.__in_pins:
            gpio.cleanup(ch)
        
    def __enter__(self):
        self.init()
        return self

    def __exit__(self, type, value, tb):
        self.cleanup()
