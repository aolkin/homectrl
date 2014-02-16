#!/usr/bin/env python3
#
# PINS:
# A D3: CE1
# B D2: CE0
# C D1: RXD
# D D0: TXD
#

import RPi.GPIO as gpio
from time import sleep
from collections import defaultdict

try:
    from .component import Component
except ValueError:
    from component import Component

A = 26 # CE1
B = 24 # CE0
C = 10 # RXD
D = 8  # TXD

class RFReceiver(Component):
    def __init__(self,a=A,b=B,c=C,d=D):
        self.pins = (a, b, c, d)
        self.handlers = defaultdict(dict)
        self.__next_id = -1
        super().__init__(inpins=self.pins)

    def init(self):
        super().init()
        for n, i in enumerate(self.pins):
            gpio.add_event_detect(i, gpio.RISING, bouncetime=100,
                                  callback=lambda x,n=n: self._handle_pin(n))

    def cleanup(self):
        for i in self.pins:
            gpio.remove_event_detect(i)
        super().cleanup()

    def _handle_pin(self,pin):
        for i in self.handlers["generic"].values():
            i(pin)
        for i in self.handlers[pin].values():
            i(pin)

    def __get_handlers(self,pin=None,generic=False):
        if (pin is None) and (not generic):
            raise TypeError("Must supply pin for non generic handler!")
        return self.handlers["generic"] if generic else self.handlers[pin]

    def add_handler(self,callback,pin=None,generic=False):
        self.__next_id += 1
        self.__get_handlers(pin,generic)[self.__next_id] = callback
        return self.__next_id

    def remove_handler(self,hid,pin=None,generic=False):
        del self.__get_handlers(pin,generic)[hid]

if __name__ == "__main__":
    def echo(pin):
        print("Press on button:", pin)
    rf = RFReceiver()
    rf.add_handler(echo,generic=True)
    with rf:
        while True:
            sleep(1)
    
