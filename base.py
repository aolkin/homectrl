#!/usr/bin/python3
#
# Base script for the controller
#

import time, os, sys, threading, socket, traceback

from subprocess import check_output, STDOUT, CalledProcessError

from hardware import RFReceiver, AnimatedDisplay

from soco import SoCo, discover

PLAYING = "PLAYING"
PAUSED  = "PAUSED_PLAYBACK"
STOPPED = "STOPPED"
TRANSITIONING = "TRANSITIONING"

STATUS_CHARACTERS = {
    PLAYING: chr(1),
    PAUSED: chr(2),
    STOPPED: chr(3),
    TRANSITIONING: chr(4)
}

def write_custom_chars(display):
    display.writeChar(*[0x00 for i in range(8)])
    display.writeChar(0x08,0x0c,0x0e,0x0f,0x0e,0x0c,0x08,0x00)
    display.writeChar(0x1b,0x1b,0x1b,0x1b,0x1b,0x1b,0x1b,0x00)
    display.writeChar(0x00,0x1f,0x1f,0x1f,0x1f,0x1f,0x00,0x00)
    display.writeChar(0x00,0x0e,0x1f,0x1f,0x1f,0x0e,0x00,0x00)

def get_wifi_status():
    try:
        wifi_str = check_output(["/sbin/wpa_cli","status"],
                                universal_newlines=True,
                                stderr=STDOUT)
    except CalledProcessError as err:
        wifi_str = err.output
    wifi_lines = wifi_str.split("\n")
    wifi_dict = {}
    for i in wifi_lines:
        line = i.rpartition("=")
        if line[0]:
            wifi_dict[line[0]] = line[2]
        else:
            pass
    return wifi_str, wifi_dict

class HomeCtrl:
    def __init__(self):
        self.display = AnimatedDisplay()
        self.rf = RFReceiver()

        self.players = {}
        self.current_player = -1

    def get_sonos_players(self):
        self.players = {}
        for i in discover():
            self.players[i.player_name] = i
        return self.players

    def next_player(self,*args):
        self.current_player += 1
        if self.current_player >= len(self.players):
            self.current_player = 0
        name = sorted(self.players.keys())[self.current_player]
        self.player = self.players[name]
        self.display.animateRow(0,name)

    def select_player(self,*args):
        self.player_selected = True

    def playpause(self,*args,noaction=False):
        if self.player.get_current_transport_info()["current_transport_state"] != "PLAYING":
            self.display.lit = True
            if not noaction:
                self.player.play()
        else:
            if not noaction:
                self.player.pause()

    def skip(self,ch):
        self.player.next()

    def volume(self,ch):
        vol = self.player.volume
        if ch == 1:
            vol += 5
        elif ch == 3:
            vol -= 5
        self.player.volume = vol
        self.display.insert(3,0,"Vol " + "\xff"*round(vol/6) + " "*(16-round(vol/6)))

        if getattr(self,"volume_timer",None):
            self.volume_timer.cancel()
        self.volume_timer = threading.Timer(2,lambda s=self:
                                                s.display.insert(
                3,0," " + STATUS_CHARACTERS[self.current_transport_state] + " " +
                s.current_info.get("position") + " / " + s.current_info.get("duration")))
        self.volume_timer.start()

    def __darken_display(self):
        self.display.lit = False

    def __main(self):
        self.display.lit = True
        write_custom_chars(self.display)
        
        while len(self.players) < 1:
            try:
                self.display.displayLoadingAnimation()
                wifi_str, wifi_status = get_wifi_status() 
                if "ssid" in wifi_status:
                    self.display.animateRow(3,"Wifi: "+wifi_status["ssid"])
                elif "wpa_state" in wifi_status:
                    self.display.animateRow(3,wifi_status["wpa_state"])
                self.get_sonos_players()
            except socket.error as err:
                print(repr(err))
                self.display.stopLoadingAnimation(True)
                self.display.stopRow(3,True)
                self.display.insert(0,0,wifi_str,wrap=True)
                time.sleep(5)
                self.display.insert(0,0," "*20*4,wrap=True)

        nextbtn = self.rf.add_handler(self.next_player,0)
        selectbtn = self.rf.add_handler(self.select_player,1)
        self.player_selected = False
        self.display.stopLoadingAnimation()
        self.display.clearRow(1)
        self.display.animateRow(2,"A to change")
        self.display.animateRow(3,"B to select")
        self.next_player()
        while self.player_selected == False:
            time.sleep(0.1)
            
        self.rf.remove_handler(nextbtn,0)
        self.rf.remove_handler(selectbtn,1)
        self.display.stopRows(2,3,clear=True)
        self.player = self.player.group.coordinator
        self.display.clearRow(0)
        self.display.animateRow(1,"Selected:")
        self.display.animateRow(2,self.player.player_name)
        time.sleep(1)

        self.rf.add_handler(self.playpause,0)
        self.rf.add_handler(self.volume,1)
        self.rf.add_handler(self.volume,3)
        self.rf.add_handler(self.skip,2)

        self.go = True
        self.current_info = {}
        self.current_transport_state = None
        self.playpause(noaction=True)

        while self.go:
            try:
                info = self.player.get_current_track_info()
                status = self.player.get_current_transport_info()
                for n, i in enumerate(("title","artist","album")):
                    if self.display.rows[n].original_contents != info[i]:
                        self.display.animateRow(n,info[i])
                if self.current_info.get("duration") != info["duration"]:
                    self.display.insert(3,10," / " + info["duration"])
                if ((not self.display.getRow(3).startswith("Vol")) and
                    self.current_info.get("position") != info["position"]):
                    self.display.insert(3,3,info["position"])
                if self.current_transport_state != status["current_transport_state"]:
                    self.display.insert(3,0," "+STATUS_CHARACTERS[status["current_transport_state"]]+" ")
                    if getattr(self,"display_timer",None):
                        self.display_timer.cancel()
                    if status["current_transport_state"] in (PAUSED,STOPPED):
                        self.display_timer = threading.Timer(5,self.__darken_display)
                        self.display_timer.start()
                    else:
                        self.display.lit = True
                self.current_info = info
                self.current_transport_state = status["current_transport_state"]
                active_threads = threading.enumerate()
                if False and len(active_threads) > 1:
                    print(active_threads)
                time.sleep(0.5)
            except Exception as err:
                print(repr(err),file=sys.stderr)
                traceback.print_exc(file=sys.stdout)
                self.display.animateRow(3,repr(err))
                time.sleep(10)
                self.display.stopRow(3,clear=True)

    def main(self):
        with self.display, self.rf:
            try:
                self.__main()
            except KeyboardInterrupt:
                self.display.enabled = False

    @classmethod
    def launch(cls):
        hc = cls()
        if len(sys.argv) > 1:
            hc.main()
        else:
            if os.fork() == 0:
                os.nice(-15)
                hc.main()
            else:
                return hc

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Must be run as root!",file=sys.stderr)
        exit(5)
    HomeCtrl.launch()
