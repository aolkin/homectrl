#!/usr/bin/env python3
#
# PINS:
# 4 RS: 24
# 6 EN: 25
# 7 DB: 4
# 6 DB: 17
# 5 DB: 21/27
# 4 DB: 22
#
# Backlight: 18
#

import RPi.GPIO as gpio
import time, threading

def delay(ms):
    time.sleep(ms/1000000)

RS = 18 # 24
EN = 22 # 25
D7 = 7  # 4
D6 = 11 # 17
D5 = 13 # 27
D4 = 15 # 22

BACKLIGHT = 12 # 18

ROWS = 4
COLS = 20

MODE_MASK  = 0b00001000
SHIFT_MASK = 0b00010000

RIGHT = 0b0100
LEFT  = 0b0000

class Display:
    def __init__(self,rs=RS,en=EN,d7=D7,d6=D6,d5=D5,d4=D4,bl=BACKLIGHT):
        self.RS = rs
        self.EN = en
        self.D7 = d7
        self.D6 = d6
        self.D5 = d5
        self.D4 = d4
        self.BACKLIGHT = bl
        self.data_pins = (d7, d6, d5, d4)
        self.all_pins = (rs, en, bl) + self.data_pins

        self.__initialized = False

        self.__mode = 0b000
        self.__lit = False

    def __checkInit(self,quiet=False):
        if quiet:
            return self.__initialized
        if not self.__initialized:
            raise RuntimeError("The Display has not been initialized yet!")

    @property
    def lit(self):
        return self.__lit

    @lit.setter
    def lit(self,state):
        if (not self.enabled) and state:
            self.enabled = True
        if self.__lit != state:
            self.__checkInit()
            gpio.output(self.BACKLIGHT,state)
            self.__lit = state

    def __changeMode(self,mask,state):
        if state:
            mode = self.__mode | mask
        else:
            mode = self.__mode & ~mask
        if mode != self.__mode:
            self.command(MODE_MASK | mode)
            self.__mode = mode

    @property
    def enabled(self):
        return bool(self.__mode & 0b100)

    @enabled.setter
    def enabled(self,state):
        if (not state) and self.lit:
            self.lit = False
        self.__changeMode(0b100,state)

    @property
    def cursor(self):
        return bool(self.__mode & 0b010)

    @cursor.setter
    def cursor(self,state):
        self.__changeMode(0b010,state)

    @property
    def blink(self):
        return bool(self.__mode & 0b001)

    @blink.setter
    def blink(self,state):
        self.__changeMode(0b001,state)

    def __pulseEnable(self):
        gpio.output(self.EN,0)
        delay(1)
        gpio.output(self.EN,1)
        delay(1)
        gpio.output(self.EN,0)
        delay(100)

    def __write4(self,val):
        for n, i in enumerate(self.data_pins):
            gpio.output(i, (val >> (3-n)) & 1)
        self.__pulseEnable()

    def write(self,val,mode=1):
        self.__checkInit()
        gpio.output(self.RS,mode)
        self.__write4(val>>4)
        self.__write4(val)
        
    def command(self,val):
        self.write(val,0)

    def clear(self):
        self.command(0b00000001)
        delay(1500)

    def move(self,pos):
        self.command(0b10000000 | pos)

    def shift(self,direction):
        self.command(SHIFT_MASK | direction)

    def printString(self,s):
        for i in s:
            self.write(ord(i))

    def init(self,bl=False):
        if self.__initialized:
            try:
                self.cleanup()
            finally:
                pass

        gpio.setmode(gpio.BOARD)
        
        for ch in self.all_pins:
            gpio.setup(ch, gpio.OUT, initial=gpio.LOW)

        self.__write4(0b0011) # Set to 8 bit mode
        self.__write4(0b0011) # Again, in case in 4 bit mode
        self.__write4(0b0010) # Set to 4 bit mode in 8 bit mode

        self.__initialized = True

        delay(500)
        self.command(0b00101000) # Set to use max number of lines and font 0
        self.clear()

        self.lit = bl

    def cleanup(self,quiet=False):
        if self.__checkInit(quiet):
            self.enabled = False
        self.__initialized = False
        for ch in self.all_pins:
            gpio.cleanup(ch)

    def __enter__(self):
        self.init(True)
        return self

    def __exit__(self, type, value, tb):
        self.cleanup()

ROW_ADDENDS = {0: 0, 1: 64, 2: COLS, 3: 64+COLS}

class ManagedDisplay(Display):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._contents = [[" " for j in range(COLS)] for i in range(ROWS)]
        
    def move(self,row,col):
        if 0 > col > COLS-1:
            raise ValueError("Invalid column ({})".format(col))
        try:
            super().move(ROW_ADDENDS[row] + col)
        except KeyError as err:
            raise ValueError("Invalid row ({})".format(row))

    def insert(self,row,col,contents,clear=False,wrap=False):
        if clear:
            self.clearRow(row)
        self.move(row,col)
        for i in contents:
            if col > COLS-1:
                if wrap:
                    col = 0
                    row += 1
                    if clear:
                        self.clearRow(row)
                    self.move(row,col)
                else:
                    return False
            self.printString(i)
            self._contents[row][col] = i
            col += 1
        return True

    def clearRow(self,row):
        self.insert(row,0," "*COLS,False,False)

    def __str__(self):
        return "\n".join(["".join(l) for l in self._contents])

    def redisplay(self,row=None):
        for i in range(row if row else 0, row+1 if row else ROWS):
            self.insert(i,0,"".join(self._contents[i]),clear=True)


class Done(Exception): pass

def wait_with_event(wait,event):
    for i in range(10):
        if event.is_set(): raise Done("{} was set.".format(event))
        time.sleep(wait/10)

class Row():
    def __init__(self,row):
        self.enabled = False
        self.row = row
        self.contents = ""
        self.pos = 0

    def setContents(self,val,pad=True):
        if len(val) > COLS:
            self.contents = " " + val + " "
        elif pad:
            self.contents = " " * int((COLS-len(val))/2) + val
        else:
            self.contents = val
        self.pos = 0

class AnimatedDisplay(ManagedDisplay):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.rows = [Row(i) for i in range(ROWS)]
        self.paused_event = threading.Event()
        self.thread = threading.Thread(target=self._animateRows)
        self.thread.daemon = True
        self.thread.start()

    def _animateRows(self):
        while True:
            for i in self.rows:
                if len(i.contents) > COLS and i.enabled:
                    part = i.contents[i.pos:min(i.pos+COLS,len(i.contents))]
                    part += i.contents[:COLS-len(part)]
                    self.insert(i.row,0,part,True)
                    i.pos += 1
                    if i.pos > len(i.contents):
                        i.pos = i.pos % len(i.contents) - 1
            self.paused_event.set()
            time.sleep(0.5)

    def displayLoadingAnimation(self,row=1):
        self.insert(row,5,"Loading",True)
        event = threading.Event()
        thread = threading.Thread(target=self.__displayLoadingAnimation,args=(row,event))
        thread.daemon = True
        thread.start()
        return event.set

    def __displayLoadingAnimation(self,row,event):
        try:
            while True:
                self.insert(row,12,"   ")
                wait_with_event(1,event)
                for i in range(12,15):
                    self.insert(row,i,".")
                    wait_with_event(.5,event)
                wait_with_event(.5,event)
        except Done:
            self.insert(row,8,"Done",True)

    def animateRow(self,row,content):
        self.stopRow(row)
        self.rows[row].setContents(content)
        self.insert(row,0,self.rows[row].contents,True)
        self.rows[row].enabled = True

    def stopRow(self,row,clear=False):
        self.rows[row].enabled = False
        self.paused_event.clear()
        self.paused_event.wait()
        if clear:
            self.insert(row,0,"",True)
        else:
            self.insert(row,0,self.rows[row].contents,True)

    def cleanup(self,*args,**kwargs):
        for i in range(ROWS):
            self.stopRow(i,True)
        super().cleanup(*args,**kwargs)

if __name__ == "__main__":
    with Display() as display:
        display.printString("Hello World")
        delay(1000000)
