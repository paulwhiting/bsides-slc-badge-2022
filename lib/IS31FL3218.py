class IS31FL3218:
    def __init__(self, i2c, address=0x54):
        import adafruit_bus_device.i2c_device as i2c_device
        try:
            self.i2c = i2c_device.I2CDevice(i2c, address)
        except ValueError as e:
            print(e)
            raise RuntimeError('Failed to find LED Driver IS31FL3218!')

        self.reset()
        self.setEnabled(True)

    def reset(self):
        with self.i2c:
            self.i2c.write(bytes([0x17, 0]))

    def setLed(self, led, value):
        value //= 8
        with self.i2c:
            self.i2c.write(bytes([led+1, value]))

    def enableLeds(self, led_list):
        for i in range(3):
            v = 0
            for j in range(6):
                if led_list[i*6+j]:
                    v |= (1<<j)
            with self.i2c:
                self.i2c.write(bytes([0x13+i, v]))

    def refresh(self):
        with self.i2c:
            self.i2c.write(bytes([0x16, 0]))

    def setEnabled(self, enabled):
        with self.i2c:
            if enabled:
                self.i2c.write(b'\x00\x01')
            else:
                self.i2c.write(b'\x00\x00')
