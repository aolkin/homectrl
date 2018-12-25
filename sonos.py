
from .screens import *

import soco, time

class PlayerSelection(Menu):        
    def get_options(self):
        self.display.displayLoadingAnimation()
        self.players = {}
        for i in soco.discover():
            self.players[i.player_name] = i
        self.display.stopLoadingAnimation()
        return self.players

    def selected(self, player):
        return PlayerMenu(player, self.display)

class PlayerMenu(Menu):
    def __init__(self, player, *args):
        super().__init__(*args)
        self.__player = player
        
    def get_options(self):
        return { "Now Playing" : NowPlaying(self.__player, self.display) }

class NowPlaying(Screen):
    def __init__(self, player, *args):
        super().__init__(*args)
        self.__player = player.group.coordinator
        self.__info = {}
        self.__state = None

        self.__volume_time = None
        self.__play_time = 0

    def input(self, button):
        if button in ARROWS:
            vol = self.__player.volume
            if button == UP:
                vol += 5
            elif button == DOWN:
                vol -= 5
            self.__player.volume = vol
            self.draw_volume(vol)
            self.__volume_time = time.time()
        elif button == A:
            if self.__player.get_current_transport_info()["current_transport_state"] != "PLAYING":
                self.display.lit = True
                self.player.play()
            else:
                self.player.pause()
        elif button == MENU:
            return None
        return self

    def tick(self):
        tt = time.time()
        if self.__tick_time + 0.5 > tt:
            return self
        try:
            info = self.player.get_current_track_info()
            status = self.player.get_current_transport_info()
            for n, i in enumerate(("title","artist","album")):
                if self.display.rows[n].original_contents != info[i]:
                    self.display.animateRow(n,info[i])
            if self.__volume_time:
                if self.__volume_time + 2 < tt:
                    self.draw_status()
                    self.__volume_time = None
                else:
                    pass # volume should already be drawn
            else:
                if self.__info.get("duration") != info["duration"]:
                    self.draw_duration(info["duration"])
                if self.__info.get("position") != info["position"]):
                    self.draw_position(info["position"])
                if self.__state != status["current_transport_state"]:
                    self.draw_state(status["current_transport_state"])
            if status["current_transport_state"] in (PAUSED,STOPPED):
                if self.__play_time + 5 < tt:
                    self.display.lit = False
            else:
                self.__play_time = tt
                self.display.lit = True
            self.__info = info
            self.__tick_time = tt
        except Exception as err:
            print(repr(err),file=sys.stderr)
            traceback.print_exc(file=sys.stdout)
            self.display.animateRow(3,repr(err))
            time.sleep(10)
            self.display.stopRow(3,clear=True)
        return self

    def draw_volume(self, v=None):
        vol = v or self.__player.volume
        self.display.insert(3,0,"Vol " + "\xff"*round(vol/6) + " "*(16-round(vol/6)))

    def draw_status(self):
        self.draw_duration()
        self.draw_position()
        self.draw_state()

    def draw_duration(self, d=None):
        if d:
            self.__info["duration"] = d
        self.display.insert(3, 10, " / " + self.__info["duration"])

    def draw_position(self, p=None):
        if p:
            self.__info["position"] = p
        self.display.insert(3, 3, self.__info["position"])

    def draw_state(self, s=None):
        if s:
            self.__state = s
        self.display.insert(
            3, 0, " " + STATUS_CHARACTERS[self.__state] + " ")
