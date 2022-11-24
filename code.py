import board
import busio
import displayio
import time
import math
import random
import struct
import binascii
import terminalio
from digitalio import DigitalInOut, Direction, Pull
from STK8321 import STK8321
from IS31FL3218 import IS31FL3218
from joystick import Joystick
from adafruit_st7735r import ST7735R
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.rect import Rect
from adafruit_display_text.label import Label
from collections import OrderedDict

btn = DigitalInOut(board.GP21)
btn.direction = Direction.INPUT
btn.pull = Pull.UP


DISPLAY_WIDTH = 160
DISPLAY_HEIGHT = 80

JOY_MIN = -512
JOY_MAX = 512

displayio.release_displays()
spi = busio.SPI(board.GP2, board.GP3, board.GP4)
displayio.release_displays()
display_bus = displayio.FourWire(spi, command=board.GP5, chip_select=board.GP7, reset=board.GP6)
display = ST7735R(display_bus, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, colstart=24, rotation=270, backlight_pin=board.GP8)

font = terminalio.FONT

i2c = busio.I2C(board.GP17, board.GP16)

INPUT_DELAY = 0.05
LED_COUNT = 12

try:
    joy = Joystick(i2c)
except RuntimeError as e:
    print(e)
    joy = None

try:
    led_controller = IS31FL3218(i2c)
    led_controller.enableLeds([
        True,  True,  True,  True,  True,  True,
        True,  True,  True,  True,  True,  True,
        False, False, False, False, False, False])
    for i in range(13):
        if i>0:
            led_controller.setLed(i-1, 0)
        if i<13:
            led_controller.setLed(i, 255)
        led_controller.refresh()
except RuntimeError as e:
    print(e)
    led_controller = None

try:
    accel = STK8321(i2c)
    accel.enableMotionInterrupt()
    print(accel.get_values())
except RuntimeError as e:
    print(e)
    accel = None

class Button:
    PRESSED_SHORT = 1
    PRESSED_LONG = 2

    def __init__(self, joy):
        self.joy = joy
        self.registered = False
        self.waiting_for_release = False
        self.long_press_delay = 0.4

    def pressed(self):
        self._read()
        if self.registered:
            self.registered = False
            return True
        return False

    def wait_for(self):
        while not self.pressed():
            time.sleep(.001)

    def multi_pressed(self):
        self._read()
        if self.registered:
            diff = (time.monotonic() - self.registered)
            if self._depressed():
                if diff >= self.long_press_delay:
                    self.registered = False
                    return Button.PRESSED_LONG
            else:
                self.registered = False
                if diff < self.long_press_delay:
                    return Button.PRESSED_SHORT
                else:
                    return Button.PRESSED_LONG
        return False

    def _read(self):
        if self._depressed():
            if not self.registered and not self.waiting_for_release:
                self.waiting_for_release = True
                self.registered = time.monotonic()

    def _depressed(self):
        if not self.joy:
            return False
        pressed = not self.joy.getPos()['Button']
        if not pressed:
            self.waiting_for_release = False
        return pressed

joy_button = Button(joy)


def eyes(cursor):
    eye_color = 0
    colors = [0x000000, 0xFF0000, 0xffa000, 0xFFFF00, 0x00FF00, 0x0000FF, 0xFF00FF]
    # Make the display context
    testdata = displayio.Group()
    display.show(testdata)

    joy_pos = Circle(54, 38, 5, fill=colors[eye_color])
    acc_pos = Circle(116, 36, 5, fill=colors[eye_color])
    acc_z = Rect(156, 4, 4, 2, fill=0x808080)
    bitmap = displayio.OnDiskBitmap("/eyebg.bmp")
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
    testdata.append(tile_grid)
    testdata.append(joy_pos)
    testdata.append(acc_pos)
    #testdata.append(acc_z)


    c=0
    running = True
    if joy:
        jp = joy.getPos()

    while running:
        if led_controller:     
            for i in range(12):
                m = 127.0
                v = int(m+m*math.sin(c+i*.5))
                led_controller.setLed(i, v)
            c+=.3
            if c > 2* math.pi:
                c -= 2*math.pi
            led_controller.refresh()
        if joy:
            jp = joy.getPos()
            press = joy_button.multi_pressed()
            if press:
                if press == Button.PRESSED_SHORT:
                    eye_color = (eye_color+1)%len(colors)
                    joy_pos.fill = colors[eye_color]
                    acc_pos.fill = colors[eye_color]
                else:
                    running = False
            joy_pos.x0 = 54 + jp['X']//32
            joy_pos.y0 = 38 + jp['Y']//32
        if accel:
            al = accel.get_values()
            acc_pos.fill = 0x00FF00 if not btn.value else 0x202020
            acc_pos.x0 = 116 + al['X']//64
            acc_pos.y0 = 36 + al['Y']//64
            acc_z.y = 40 + al['Z']//64
        time.sleep(.025)


eyes(None)



class Cursor:
    def __init__(self, joy):
        self.joy = joy
        self.x = DISPLAY_WIDTH // 2
        self.y = DISPLAY_HEIGHT // 2
        self.size = 3
        self.ptr = Circle(self.x, self.y, self.size, fill=0xFFFFFF)
        self.rate = 10

    def update(self):
        pos = self.joy.getPos()
        self.x += int((pos['X'] / JOY_MAX) * self.rate)
        self.x = min(self.x, DISPLAY_WIDTH)
        self.x = max(self.x, 0)
        self.y += int((pos['Y'] / JOY_MAX) * self.rate)
        self.y = min(self.y, DISPLAY_HEIGHT)
        self.y = max(self.y, 0)

        self.ptr.x = self.x - self.size
        self.ptr.y = self.y - self.size

def center_offset(text):
    return (DISPLAY_WIDTH - len(text) * 6) // 2

class Menu:
    def __init__(self, title, options):
        self.title = title
        self.options = options
        self.labels = []
        self.y_off = 20
        self.y_size = 15
        self.group = None
        
    def display(self, cursor):
        font = terminalio.FONT
        items = displayio.Group()
        items.append(cursor.ptr)
        items.append(Label(font, text=self.title, x=center_offset(self.title), y=5, color=0x00FF00))
        i = 0
        for k in self.options:
            if i >= 5:
                # +5 for the y offset to position the text correctly
                l = Label(font, text=k, x=80, y=self.y_off+(i-5)*self.y_size+5, color=0xFFFF00)
                self.labels.append(l)
                items.append(l)
            else:
                # +5 for the y offset to position the text correctly
                l = Label(font, text=k, x=80, y=self.y_off+(i-5)*self.y_size+5, color=0xFFFF00)
                l = Label(font, text=k, x=0, y=self.y_off+i*self.y_size+5, color=0xFFFF00)
                self.labels.append(l)
                items.append(l)
            i += 1

        display.show(items)
        self.group = items

    def run(self):
        cursor = Cursor(joy)
        self.display(cursor)
        while joy_button.pressed():
            time.sleep(INPUT_DELAY)
        while True:
            time.sleep(INPUT_DELAY)
            cursor.update()
            if joy_button.pressed():
                if cursor.x < 80 and cursor.y >= self.y_off:
                    i = int((cursor.y - self.y_off)/self.y_size)

                    if i < len(self.options):
                        fn = self.options[list(self.options)[i]]
                        if fn == None:
                            break
                        else:
                            self.group.remove(cursor.ptr)
                            fn(cursor)
                            self.group.append(cursor.ptr)
                            display.show(self.group)



LED_COUNT = 12

def turn_off_lights():
    for i in range(LED_COUNT):
        led_controller.setLed(i, 0)
    led_controller.refresh()


light = 0
def single_light(cursor):
    global light
    for i in range(LED_COUNT):
        if i == light:
            led_controller.setLed(i,100)
        else:
            led_controller.setLed(i,5)
    led_controller.refresh()
    light = (light+1) % LED_COUNT
    

def running_light(cursor):
    global light
    items = displayio.Group()
    items.append(Label(font, text="Short press for speed.", x=0, y=5, color=0xFFFFFF))
    items.append(Label(font, text="Long press to exit.", x=0, y=20, color=0xFFFFFF))
    display.show(items)
    speed = 0
    speeds = [1000,500,250,100,50,25,10,1]
    #while not joy_button.pressed():
    running = True
    while running:
        for i in range(LED_COUNT):
            if i == light:
                led_controller.setLed(i,100)
            else:
                led_controller.setLed(i,5)
        led_controller.refresh()
        light = (light+1) % LED_COUNT
        left = speeds[speed]/1000.0
        while left:
            to_sleep = min(INPUT_DELAY, left)
            time.sleep(to_sleep)
            left -= to_sleep
            press = joy_button.multi_pressed()
            if press:
                if press == Button.PRESSED_SHORT:
                    speed = (speed+1)%len(speeds)
                else:
                    running = False
                break


def mines(cursor):
    size = 16
    width = int(DISPLAY_WIDTH / size)
    height = int(DISPLAY_HEIGHT / size)
    area = width*height
    count = 7
    non_mines = area - count
    x_offset = 5  # text offset
    y_offset = 6  # text offset

    mines = []

    for i in range(LED_COUNT):
        if i < count:
            led_controller.setLed(i, 255)
        else:
            led_controller.setLed(i, 0)
    led_controller.refresh()

    class Location:
        def __init__(self, x, y, is_mine):
            self.neighbors = 0
            self.mine = is_mine
            self.x = x
            self.y = y
            self.rect = Rect(x*size, y*size, size-1, size-1, fill=0x808080)
            self.revealed = False
            self.flagged = False

        def increment_count(self):
            self.neighbors += 1

        def flag(self):
            nonlocal count
            if self.revealed:
                return
            if self.flagged:
                self.rect.fill = 0x808080
                self.flagged = False
                if count >= 0:
                    led_controller.setLed(count, 255)
                count += 1
            else:
                self.rect.fill = 0xFF8080
                self.flagged = True
                count -= 1
                if count >= 0:
                    led_controller.setLed(count, 0)
            led_controller.refresh()

        def reveal(self, items):
            to_reveal = []
            revealed = 0
            if not self.revealed:
                if self.flagged:
                    self.flag()
                if self.mine:
                    # boom
                    revealed = -1
                    self.rect.fill = 0xFF0000
                else:
                    self.revealed = True
                    revealed = 1
                    self.rect.fill = 0x202020
                    if self.neighbors > 0:
                        items.append(Label(font, text=str(self.neighbors), x=self.x*size+x_offset, y=self.y*size+y_offset, color=0x00FF00))
                    else:
                        for x in [-1, 0, 1]:
                            for y in [-1, 0, 1]:
                                newx = self.x + x
                                newy = self.y + y
                                if newx >= 0 and newx < width and newy >= 0 and newy < height:
                                    to_reveal.append(mines[newx][newy])
            return revealed, to_reveal
                    

    items = displayio.Group()

    for x in range(width):
        col = []
        for y in range(height):
            col.append(Location(x, y, False))
        mines.append(col)

    available = list(range(area))
    for n in range(count):
        loc = random.choice(available)
        available.remove(loc)
        x = int(loc % width)
        y = int(loc / width)
        mines[x][y] = Location(x, y, True)

    for col in mines:
        for item in col:
            items.append(item.rect)
            if item.mine:
                for x in [-1, 0, 1]:
                    for y in [-1, 0, 1]:
                        newx = item.x + x
                        newy = item.y + y
                        if newx >= 0 and newx < width and newy >= 0 and newy < height:
                            mines[newx][newy].increment_count()

    items.append(cursor.ptr)
    display.show(items)

    while True:
        press = joy_button.multi_pressed()
        if press:
            x = cursor.x // size
            y = cursor.y // size
            if x < width and y < height:
                if press == Button.PRESSED_SHORT:
                    x = cursor.x // size
                    y = cursor.y // size
                    if x < width and y < height:
                        to_reveal = [mines[x][y]]
                    while to_reveal:
                        item = to_reveal.pop()
                        revealed, reveal_mines = item.reveal(items)
                        if revealed == -1:
                            non_mines = -1
                            break
                        non_mines -= revealed
                        to_reveal += reveal_mines
                    if non_mines <= 0:
                        text = "You won!" if non_mines == 0 else "You lost!"
                        display.show(Label(font, text=text, x=center_offset(text), y=40, color=0xFFFFFF))
                        time.sleep(3)
                        break
                else:
                    mines[x][y].flag()
        time.sleep(INPUT_DELAY)
        cursor.update()

    items.remove(cursor.ptr)

def pong(cursor):
    items = displayio.Group()
    cursor.update()
    pass

main_menu = Menu("BSidesSLC 2022", OrderedDict([
    ("Eyes", eyes),
    ("Mines", mines),
    ("Running LED", running_light),        
    #("Single LED", single_light),
    ("Pong", pong),
]))

main_menu.run()
