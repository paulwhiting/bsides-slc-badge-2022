class STK8321:
    def __init__(self, i2c, address=0x0f):
        import adafruit_bus_device.i2c_device as i2c_device
        try:
            self.i2c = i2c_device.I2CDevice(i2c, address)
        except ValueError as e:
            print(e)
            raise RuntimeError('Failed to find Accelerometer STK8321!')

        if self.test() == False:
            raise RuntimeError('Failed to id STK8321!')

    def reset(self):
        with self.i2c:
            self.i2c.write(b'\x14')

    def test(self):
        id = bytearray(1)
        with self.i2c:
            self.i2c.write_then_readinto(b'\0', id)
        return 0x23 == id[0] # Documentation says 0x21 but chip returns 0x23

    def get_raw_values(self):
        a = bytearray(6)
        with self.i2c:
            self.i2c.write_then_readinto(b'\x02', a)
        return a

    def toint(self, b):
        val = (b[0]>>4) | (b[1] << 4)
        if val > 2047:
            val = val - (1<<12)
        return val

    def hasMoved(self):
        a = bytearray(1)
        with self.i2c:
            self.i2c.write_then_readinto(b'\x09', a)
        return (a[0] & 0x4)==4

    def get_values(self):
        raw = self.get_raw_values()
        vals={}
        vals['X'] = self.toint(raw[0:2])
        vals['Y'] = self.toint(raw[2:4])
        vals['Z'] = self.toint(raw[4:6])
        return vals

    def enableMotionInterrupt(self):
        with self.i2c:
            self.i2c.write(b'\x27\x00') #slope high
            self.i2c.write(b'\x28\x14') #slope low (0x14)
            self.i2c.write(b'\x20\x05') #Active high, Push-pull
            self.i2c.write(b'\x21\x03') #update every 1s
            self.i2c.write(b'\x16\x07') #ANY motion any axis
            self.i2c.write(b'\x2a\x04') #Enable Any motion
            self.i2c.write(b'\x19\x05') #INT1 on SIG and ANY
            self.i2c.write(b'\x1a\x00') #INT1 clear others


