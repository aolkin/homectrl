#!/usr/bin/python3
#
# Base script for the controller
#

import time, os, sys, threading

from hardware import RFReceiver, AnimatedDisplay

from soco import SoCo, SonosDiscovery

STATUS_CHARACTERS = {
    "PLAYING": chr(0),
    "PAUSED_PLAYBACK": chr(1),
    "STOPPED": chr(2),
    "TRANSITIONING": chr(3)
}

class HomeCtrl:
    def __init__(self):
        self.display = AnimatedDisplay()
        self.rf = RFReceiver()

        self.players = {}
        self.current_player = -1

    def get_sonos_players(self):
        self.players = {}
        sd = SonosDiscovery()
        sonos_ips = sd.get_speaker_ips()
        for i in sonos_ips:
            if i != "192.168.1.45":
                soco = SoCo(i)
                self.players[soco.player_name] = soco
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
        if getattr(self,"display_timer",None):
            self.display_timer.cancel()
        if self.player.get_current_transport_info()["current_transport_state"] != "PLAYING":
            self.display.lit = True
            if not noaction:
                self.player.play()
        else:
            self.display_timer = threading.Timer(3,lambda d=self.display: setattr(d,"lit",False))
            if not noaction:
                self.player.pause()

    def __main(self):
        self.display.lit = True
        self.display.displayLoadingAnimation()
        self.display.writeChar(0x08,0x0c,0x0e,0x0f,0x0e,0x0c,0x08,0x00)
        self.display.writeChar(0x1b,0x1b,0x1b,0x1b,0x1b,0x1b,0x1b,0x00)
        self.display.writeChar(0x00,0x1f,0x1f,0x1f,0x1f,0x1f,0x00,0x00)
        self.display.writeChar(0x00,0x1f,0x1f,0x1f,0x1f,0x1f,0x00,0x00)
        self.get_sonos_players()
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
                    if self.current_info.get(i) != info[i]:
                        self.display.animateRow(n,info[i])
                if (self.current_info.get("duration") != info["duration"] or
                    self.current_info.get("position") != info["position"] or
                    self.current_transport_state != status["current_transport_state"]):
                    status_msg = (STATUS_CHARACTERS[status["current_transport_state"]] +
                                  " " + info["position"] + " / " + info["duration"])
                    self.display.animateRow(3,status_msg)
                self.current_info = info
                self.current_transport_state = status["current_transport_state"]
                time.sleep(0.5)
            except Exception as err:
                #print(repr(err),file=sys.stderr)
                self.display.animateRow(3,repr(err))
                time.sleep(5)

    def main(self):
        with self.display, self.rf:
            self.__main()

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
