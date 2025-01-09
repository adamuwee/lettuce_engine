import time

from busio import I2C
from adafruit_bus_device import i2c_device
from board import SCL, SDA

from ht16k33 import HT16K33Segment14

class FourDigitDisplay:

    '''
    Initialize I2C bus and display
    '''
    def __init__(self, i2c_bus : int = 1, i2c_address : int = 0x70):
        self.display = HT16K33Segment14(I2C(SCL, SDA),
                                        board=HT16K33Segment14.SPARKFUN_ALPHA)
        self.display.set_brightness(2)
        self.display.clear()

    def write_digit(self, position, digit):
        if position < 0 or position > 3:
            return
        self.display.set_character(digit, position)
        
    def display_number(self, number):
        str_number = f"{number:04d}"  # Ensure the number is 4 digits with leading zeros
        self.display.clear()
        for position, c in enumerate(str_number):
            self.write_digit(position, c)
        self.display.draw()

if __name__ == "__main__":
    display = FourDigitDisplay()
    display.display_number(-123)
    for i in range(5555):
        display.display_number(i)
        print(f"Displaying {i}")
        time.sleep(0.1)
