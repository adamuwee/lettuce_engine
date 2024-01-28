from board import SCL, SDA, D4
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1305
import digitalio

class Display:
    

    def __init__(self, i2c, i2c_addr, reset_pin):

        self._disp = adafruit_ssd1305.SSD1305_I2C(128, 32, i2c, reset=reset_pin)

        # Clear display.
        self._disp.fill(0)
        self._disp.show()

        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        self._width = self._disp.width
        self._height = self._disp.height
        self._image = Image.new("1", (self._width, self._height))

        # Get drawing object to draw on image.
        self._draw = ImageDraw.Draw(self._image)

        # Draw a black filled box to clear the image.
        self._draw.rectangle((0, 0, self._width, self._height), outline=0, fill=0)

        # Draw some shapes.
        # First define some constants to allow easy resizing of shapes.
        padding = -2
        self._top = padding
        self._bottom = self._height - padding
        # Move left to right keeping track of the current x position for drawing shapes.
        x = 0

        # Load default font.
        self._font = ImageFont.load_default()

        self._draw.text((x, self._top + 0), "Display Init...", font=self._font, fill=255)
        self._disp.image(self._image)
        self._disp.show()

    def clear_screen(self):
        self._draw.rectangle((0, 0, self._width, self._height), outline=0, fill=0)
        self._disp.image(self._image)
        self._disp.show()

    def print_line(self, line_index : int, text : str):
        self._draw.text((0, self._top + line_index*11), text, font=self._font, fill=255)
        self._disp.image(self._image)
        self._disp.show()