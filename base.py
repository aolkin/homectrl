#!/usr/bin/python3
#
# Base script for the controller
#

import time, os, sys, threading, socket

from subprocess import check_output, STDOUT

from hardware import RFReceiver, AnimatedDisplay

from soco import SoCo, SonosDiscovery

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

class HomeCtrl:
    def __init__(self):
        self.display = AnimatedDisplay()
        self.rf = RFReceiver()
        self.sd = SonosDiscovery()

        self.players = {}
        self.current_player = -1

    def get_sonos_players(self):
        self.players = {}
        sonos_ips = self.sd.get_speaker_ips()
        for i in sonos_ips:
            try:
                soco = SoCo(i)
                self.players[soco.player_name] = soco
            except Exception as err:
                print(repr(err))
        return self.players

    def next_player(self,*args):
        self.lastPressTime = time.time()
        self.current_player += 1
        if self.current_player >= len(self.players):
            self.current_player = 0
        name = sorted(self.players.keys())[self.current_player]
        self.player = self.players[name]
        self.display.animateRow(1,name)

    def playpause(self,*args,noaction=False):
        if self.player.get_current_transport_info()["current_transport_state"] != "PLAYING":
            self.display.lit = True
            if not noaction:
                self.player.play()
        else:
            if not noaction:
                self.player.pause()

    def __darken_display(self):
        self.display.lit = False

    def __main(self):
        self.display.lit = True
        write_custom_chars(self.display)

        while len(self.players) < 1:
            try:
                self.display.displayLoadingAnimation()
                wifi_status = check_output(["/sbin/wpa_cli","status"],
                                           universal_newlines=True,
                                           stderr=STDOUT).replace("\n","; ")
                if "ssid=" in wifi_status:
                    ssid_start = wifi_status.find("; ssid")+7
                    ssid = wifi_status[ssid_start:wifi_status.find("; ",ssid_start)]
                self.display.animateRow(3,"Network: "+ssid)
                self.get_sonos_players()
            except socket.error as err:
                print(repr(err))
                self.display.stopLoadingAnimation(True)
                self.display.stopRow(3,True)
                self.display.insert(0,0,wifi_status,wrap=True)
                time.sleep(5)
                self.display.insert(0,0," "*20*4,wrap=True)

        nextbtn = self.rf.add_handler(self.next_player,0)
        self.display.stopLoadingAnimation()
        self.display.animateRow(2,"Press to change")
        self.display.animateRow(3,"Wait to select")
        self.next_player()
        while time.time()-self.lastPressTime < 3:
            time.sleep(0.5)
            
        self.rf.remove_handler(nextbtn,0)
        self.display.stopRows(2,3,clear=True)
        coordinator = self.player.get_group_coordinator(self.player.player_name)
        if self.player.speaker_ip != coordinator:
            self.player = SoCo(coordinator)
        self.display.animateRow(1,"Selected:")
        self.display.animateRow(2,self.player.player_name)
        time.sleep(1)

        self.rf.add_handler(self.playpause,0)
        self.go = True
        self.current_info = {}
        self.current_transport_state = None
        self.playpause(noaction=True)

        while self.go:
            try:
                info = self.player.get_current_track_info()
                status = self.player.get_current_transport_info()
                for n, i in enumerate(("title","artist","album")):
                    #print(self.display.rows[n].original_contents,info[i])
                    if self.display.rows[n].original_contents != info[i]:
                        self.display.animateRow(n,info[i])
                if (self.current_info.get("duration") != info["duration"] or
                    self.current_info.get("position") != info["position"] or
                    self.current_transport_state != status["current_transport_state"]):
                    status_msg = (" " + STATUS_CHARACTERS[status["current_transport_state"]] +
                                  " " + info["position"] + " / " + info["duration"])
                    self.display.animateRow(3,status_msg)
                if self.current_transport_state != status["current_transport_state"]:
                    if getattr(self,"display_timer",None):
                        self.display_timer.cancel()
                    if status["current_transport_state"] in (PAUSED,STOPPED):
                        self.display_timer = threading.Timer(5,self.__darken_display)
                        self.display_timer.start()
                    else:
                        self.display.lit = True
                self.current_info = info
                self.current_transport_state = status["current_transport_state"]
                time.sleep(0.5)
            except Exception as err:
                #print(repr(err),file=sys.stderr)
                self.display.animateRow(3,repr(err))
                time.sleep(10)

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
                #os.nice(-5)
                hc.main()
            else:
                return hc

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Must be run as root!",file=sys.stderr)
        exit(5)
    HomeCtrl.launch()
