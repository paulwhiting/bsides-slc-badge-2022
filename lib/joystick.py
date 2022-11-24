import struct
import math
class Joystick:
    def __init__(self, i2c, address=0x42):
        import adafruit_bus_device.i2c_device as i2c_device
        try:
            self.i2c = i2c_device.I2CDevice(i2c, address)
        except ValueError as e:
            print(e)
            raise RuntimeError('Failed to find Joystick!')

    def getPos(self):
        a = bytearray(6)
        with self.i2c:
            self.i2c.readinto(a)
        x,y,b,m = struct.unpack("<hhBB", a)
        return {'X':x//4,'Y':y//-4,'Button':b}

    def getRawData(self):
        a = bytearray(6)
        with self.i2c:
            self.i2c.readinto(a)
        x,y,b,m = struct.unpack("<hhBB", a)
        return {'X':x,'Y':y,'Button':b}