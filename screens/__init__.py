
import queue, time

A = SELECT = OK = 0
B = PREV = UP   = 1
C = MENU = BACK = 2
D = NEXT = DOWN = 3
ARROWS = (UP, DOWN)

class Manager:
    def __init__(self, dis, rf):
        self.display = dis
        self.rf = rf

        self.events = queue.Queue()
        self.screens = []
        
        self.rf.add_handler(self.events.put, generic=True)

    @property
    def screen(self):
        return (self.screens or None) and self.screens[-1]
        
    def launch(self, screen):
        assert len(self.screens) == 0
        with self.display, self.rf:
            self.update(screen)
            while self.screen:
                self.update(self.screen.tick())
                try:
                    while self.screen:
                        pin = self.events.get_nowait()
                        self.update(self.screen.input(pin))
                except queue.Empty:
                    pass
                time.sleep(0.05)

    def update(self, ns):
        if ns != self.screen:
            self.screen and self.screen.exit()
            if ns is None:
                self.screens.pop()
            else:
                self.screens.append(ns)
            self.screen and self.screen.enter()

class Screen:
    def __init__(self, dis):
        self.__display = dis

    @property
    def display(self):
        return self.__display
        
    def tick(self):
        return self

    def input(self, button):
        return self

    def enter(self):
        self.display.lit = True

    def exit(self):
        self.display.enabled = False
    
class Menu(Screen):
    def get_options(self):
        return {}

    def selected(self, option):
        return option

    def get_keys(self, options):
        return list(options.keys())
    
    def make_menu(self):
        self.__options = self.get_options()
        self.__keys = self.get_keys(self.__options)
        self.__selected = 0
        self.__displayed = 0

    def input(self, button):
        if button in ARROWS:
            self.__selected += 1 if button == DOWN else -1
            self.__selected = self.__selected % len(self.__keys)
            if (self.__selected // 4) != (self.__displayed // 4):
                self.draw_items()
            if self.__selected != self.__displayed:
                self.draw_cursor()
        elif button == SELECT:
            for i in range(4):
                if self.__selected % 4 != i:
                    self.display.clearRow(i)
            #time.sleep(0.5)
            ns = self.selected(
                self.__options[self.__keys[self.__selected]])
            if ns == self:
                self.draw_items()
                self.draw_cursor()
            return ns
        elif button == BACK:
            return None
        return self

    def enter(self):
        super().enter()
        self.make_menu()
        self.draw_items()
        self.draw_cursor()

    def draw_items(self):
        index = (self.__selected // 4) * 4
        for i in range(4):
            if index + i + 1 > len(self.__keys):
                self.display.clearRow(i)
            else:
                self.display.insert(i, 2, self.__keys[index+i], clear=True)

    def draw_cursor(self):
        self.display.insert(self.__displayed % 4, 0, "  ")
        self.display.insert(self.__selected % 4, 0, "> ")
        self.__displayed = self.__selected
            
            
