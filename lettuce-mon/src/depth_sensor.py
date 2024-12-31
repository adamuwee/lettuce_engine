import smbus2
import time

class TCT40Sensor:
    '''
    Operating Voltage 3.3V
    Detecting Angle: 80 degrees
    Sensor range: 2cm to 400cm
    Accuracy: 3mm
    MCU on board: STM8L051F3
    Default I2C Address: 0x2F
    Dimensions: 1.75" x 0.85"
    '''
    _WRITE_READ_DELAY_SECS = 0.10

    def __init__(self, bus_number=1, address=0x2F):
        self.bus = smbus2.SMBus(bus_number)
        self.address = address

    def read_distance(self):
        try:
            # Write to initiate measurement
            self.bus.write_byte(self.address, 0x01)
            time.sleep(self._WRITE_READ_DELAY_SECS)  # Wait for measurement to complete

            # Read 2 bytes of data
            data = self.bus.read_i2c_block_data(self.address, 0x01, 2)
            distance = ((data[0] & 0x7F) << 8) + data[1]
            return distance
        except Exception as e:
            print(f"Error reading distance: {e}")
            return None
    
    def print_distance(self, include_bar=True):
        distance = self.read_distance()
        if distance == 0:
            print("[Ultrasonic] Out of range")
        elif distance is not None:
            distance_cm = distance / 10
            distance_in = distance_cm / 2.54
            meas_str = f"Ultrasonic] Distance: {distance_in:.2f} in [Raw: 0x{distance:04X}]"
            if include_bar:
                max_distance = 100
                max_bars = 80
                bars = int((distance_cm / max_distance) * max_bars)
                meas_str += "[:->"
                for i in range(bars):
                    meas_str += "#"
            print(meas_str)

if __name__ == "__main__":
    ultra_sonic_sensor = TCT40Sensor()
    while True:
        ultra_sonic_sensor.print_distance()
        time.sleep(0.1)