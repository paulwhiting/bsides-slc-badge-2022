import board
import busio
import displayio
import time
import math
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

i2c = busio.I2C(board.GP17, board.GP16)

# Make the display context
testdata = displayio.Group()
display.show(testdata)

joy_pos = Circle(54, 38, 5, fill=0xFF0000)
acc_pos = Circle(116, 36, 5, fill=0xFF0000)
acc_z = Rect(156, 4, 4, 2, fill=0x808080)
bitmap = displayio.OnDiskBitmap("/eyebg.bmp")
tile_grid = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
testdata.append(tile_grid)
testdata.append(joy_pos)
testdata.append(acc_pos)
#testdata.append(acc_z)

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
        running = jp['Button']
        joy_pos.x0 = 54 + jp['X']//32
        joy_pos.y0 = 38 + jp['Y']//32
        joy_pos.fill = 0x00FF00 if not jp['Button'] else 0x202020
    if accel:
        al = accel.get_values()
        acc_pos.fill = 0x00FF00 if not btn.value else 0x202020
        acc_pos.x0 = 116 + al['X']//64
        acc_pos.y0 = 36 + al['Y']//64
        acc_z.y = 40 + al['Z']//64
    time.sleep(.025)


PRESSED_SHORT = 1
PRESSED_LONG = 2

class Button:
    def __init__(self, joy):
        self.joy = joy
        self.registered = False
        self.waiting_for_release = False
        self.long_press_delay = 1.5

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
                    return PRESSED_LONG
            else:
                self.registered = False
                if diff < self.long_press_delay:
                    return PRESSED_SHORT
                else:
                    return PRESSED_LONG
        return False

    def _read(self):
        if self._depressed():
            if not self.registered and not self.waiting_for_release:
                self.waiting_for_release = True
                self.registered = time.monotonic()

    def _depressed(self):
        pressed = not self.joy.getPos()['Button']
        if not pressed:
            self.waiting_for_release = False
        return pressed

joy_button = Button(joy)


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
    

class Menu:
    EXIT = 0
    REDRAW = 1
    
    def __init__(self, title, options):
        self.title = title
        self.options = options
        self.labels = []
        self.y_off = 20
        self.y_size = 15
        self.group = None
        
    def display(self, ptr):
        font = terminalio.FONT
        items = displayio.Group()
        items.append(ptr.ptr)
        items.append(Label(font, text=self.title, x=5, y=5, color=0x00FF00))
        i = 0
        for k in self.options:
            if i >= 5:
                l = Label(font, text=k, x=80, y=self.y_off+(i-5)*self.y_size, color=0xFFFF00)
                self.labels.append(l)
                items.append(l)
            else:
                l = Label(font, text=k, x=0, y=self.y_off+i*self.y_size, color=0xFFFF00)
                self.labels.append(l)
                items.append(l)
            i += 1

        display.show(items)
        self.group = items
        
    def run(self):
        ptr = Cursor(joy)
        self.display(ptr)
        while joy_button.pressed():
            time.sleep(0.01)
        while True:
            time.sleep(0.10)
            ptr.update()
            if joy_button.pressed():
                if ptr.x < 80:
                    i = int((ptr.y - self.y_off)/self.y_size)

                    fn = self.options[list(self.options)[i]]
                    if fn == None:
                        break
                    else:
                        redraw = fn()
                        redraw = True
                        if redraw is not None:
                            if redraw == Menu.EXIT:
                                break
                            else:
                                #self.display(ptr)
                                display.show(self.group)



LED_COUNT = 12

def turn_off_lights():
    for i in range(LED_COUNT):
        led_controller.setLed(i, 0)
    led_controller.refresh()


light = 0
def single_light():
    global light
    for i in range(LED_COUNT):
        if i == light:
            led_controller.setLed(i,100)
        else:
            led_controller.setLed(i,5)
    led_controller.refresh()
    light = (light+1) % LED_COUNT
    

def running_light():
    global light
    font = terminalio.FONT
    items = displayio.Group()
    items.append(Label(font, text="Short press for speed.", x=0, y=5, color=0xFFFFFF))
    items.append(Label(font, text="Long press to exit.", x=0, y=20, color=0xFFFFFF))
    display.show(items)
    speed = 0
    speeds = [1000,500,250,100,50,25,10,0]
    #while not joy_button.pressed():
    while True:
        press = joy_button.multi_pressed()
        if press:
            if press == PRESSED_SHORT:
                speed = (speed+1)%len(speeds)
            else:
                break
        for i in range(LED_COUNT):
            if i == light:
                led_controller.setLed(i,100)
            else:
                led_controller.setLed(i,5)
        led_controller.refresh()
        light = (light+1) % LED_COUNT
        time.sleep(speeds[speed]/1000.0)


def bubble():
    size = 5
    x = DISPLAY_WIDTH / 2
    y = DISPLAY_HEIGHT / 2
    items = displayio.Group()
    acc_pos = Circle(x, y, size, fill=0xFFFF00)
    items.append(acc_pos)
    display.show(items)
    while not joy_button.pressed():
        al = accel.get_values()
        #acc_pos.x0 = 116 + al['X']//64
        #acc_pos.y0 = 36 + al['Y']//64
        #acc_z.y = 40 + al['Z']//64

        vals = mems.get_values()
        newx = x + (al['Y'] / 1000.0) * 10
        newx = max(newx, size)
        newx = min(newx, DISPLAY_WIDTH - size)
        newy = y + (al['X'] / 1000.0) * 10
        newy = max(newy, size)
        newy = min(newy, DISPLAY_HEIGHT - size)


class Guesser():
    def __init__(self):
        self.answer = random.choice(range(0,255))
        self.attempts = 0
 
    def check_number(self):
        val = read_switch_int()
        tft1.fill(0)
        if self.answer == val:
            tft1.text(font, f"You got it!  ({self.answer})   ", 0, 20, st7789.YELLOW)
            return Menu.EXIT
        elif val < self.answer:
            tft1.text(font, f"Too low                   ", 0, 20, st7789.YELLOW)
        else:
            tft1.text(font, f"Too high                  ", 0, 20, st7789.YELLOW)

    @staticmethod
    def run():
        g = Guesser()
        tft0.fill(0)
        tft0.text(font, "Guess the number 0-255...   ", 0, 20, st7789.YELLOW)
        menu = Menu("Guess the #", OrderedDict([
            ("guess", g.check_number),
            ("back", None),
        ]))
        menu.run()
        return Menu.REDRAW


color = 0
colors = [
    0x000000,
    0xFF0000,
    0xFFFF00,
    0x00FF00,
    0x00FFFF,
    0x0000FF,
    0xFFFFFF,
]

def fill():
    global color
    color = (color+1)%len(colors)
    items = displayio.Group()
    items.append(Rect(0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT, fill=colors[color]))
    display.show(items)

def video():
    total = 0
    for i in range(1,76):
        a = utime.ticks_ms()
        if i < 10:
            i = f"0{i}"
        tft1.jpg(f'video/video-{i}.jpg', 0, 0)
        b = utime.ticks_ms()
        print(b-a)
        total += (b-a)
    print(76.0/total)


def rotation_puzzle():
    answer = 39918
    #def check_bit(i, s):
    #    if bool(answer & ((15-i) << 1)) == bool(s):
    #        return True
    #    return False

    def show_piece(x, y, rot):
        buffer, width, height = tft1.jpg_decode(f"flip/logo.jpg-{rot}.jpg", x, y, 40, 40)
        tft1.blit_buffer(buffer, x, y, width, height)

#    puzzle = "logo"
    while not joy_button.pressed():
        rot_ul = read_switch_int(2, 0) * 90
        rot_ur = read_switch_int(2, 2) * 90
        rot_bl = read_switch_int(2, 4) * 90
        rot_br = read_switch_int(2, 6) * 90
        show_piece(0, 0, rot_ul)
        show_piece(40, 0, rot_ur)
        show_piece(0, 40, rot_bl)
        show_piece(40, 40, rot_br)


main_menu = Menu("BSidesSLC 2022", OrderedDict([
#    ("test", test),
    ("single LED", single_light),
    ("running LED", running_light),        
#    ("bubble", bubble),
#    ("guess", Guesser.run),
#    ("puzzle", rotation_puzzle),
#    ("video", video),
]))


main_menu.run()
