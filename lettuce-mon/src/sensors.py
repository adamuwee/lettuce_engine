import busio
from busio import I2C
from adafruit_bus_device import i2c_device
from board import SCL, SDA

import smbus2

import adafruit_hts221

import adafruit_mcp3421.mcp3421 as ADC
from adafruit_mcp3421.analog_in import AnalogIn

import datetime
import json
import math
import time

class SingleTempHumidityMeasurement:
        
    timestamp_isostr = None 
    temperature = None
    humidity = None

    def __init__(self, temperature : float, humidity : float):
        self.timestamp_isostr = datetime.datetime.now().isoformat()
        self.temperature = temperature
        self.humidity = humidity
    
    def to_json(self) -> str:
        json_dict = dict()
        json_dict["iso_timestamp"] = self.timestamp_isostr
        json_dict["temperature"] = self.temperature
        json_dict["humidity"] = self.humidity
        return json.dumps(json_dict)

class TemperatureHumiditySensor:
    def read_temp_humidity(self) -> SingleTempHumidityMeasurement:
        pass

class sht31(TemperatureHumiditySensor):
    def __init__(self, i2c : I2C, i2c_addr : int = 0x44, print_reads=True) -> None:
        self.i2c_device = i2c_device.I2CDevice(i2c, i2c_addr)
        self._print_reads = print_reads

    def read_temp_humidity(self) -> SingleTempHumidityMeasurement:
        wr_data = bytearray(2)
        wr_data[0] = 0x2C
        wr_data[1] = 0x06
        self.i2c_device.write(wr_data)
        # SHT31 address, 0x44(68)
        # Read data back from 0x00(00), 6 bytes
        # Temp MSB, Temp LSB, Temp CRC, Humididty MSB, Humidity LSB, Humidity CRC
        data = bytearray(6)
        self.i2c_device.readinto(data)
        # Convert the data
        temp = data[0] * 256 + data[1]
        cTemp = -45 + (175 * temp / 65535.0)
        fTemp = -49 + (315 * temp / 65535.0)
        humidity = 100 * (data[3] * 256 + data[4]) / 65535.0
        # Output data to screen and return
        if self._print_reads:
            print(f"SHT31 0x{self.i2c_device.device_address:02x} Temperature:\t\t{fTemp:0.1f} F")
            print(f"SHT31 0x{self.i2c_device.device_address:02x} Relative Humidity:\t{humidity:0.1f}%")
        return SingleTempHumidityMeasurement(fTemp, humidity)

class hts221(TemperatureHumiditySensor):
    def __init__(self, i2c : I2C, i2c_addr : int = 0x59) -> None:
        self.hts = adafruit_hts221.HTS221(i2c)
        data_rate = adafruit_hts221.Rate.label[self.hts.data_rate]  

    def read_temp_humidity(self) -> SingleTempHumidityMeasurement:
        f_temp = self.hts.temperature * (9.0/5.0) + 32.0
        humidity = self.hts.relative_humidity
        print(f"HTS221 Temperature:\t\t{f_temp:0.1f} F")
        print(f"HTS221 Relative Humidity:\t{humidity:0.1f}%")
        return SingleTempHumidityMeasurement(f_temp, humidity)
    
class mcp3421Thermistor(TemperatureHumiditySensor):
    def __init__(self, i2c : I2C, 
                 i2c_addr : int = 0x68,
                 print_reads=True) -> None:
        self.adc_device = ADC.MCP3421(i2c)
        self.adc_device.gain = 1
        self.adc_device.resolution = 18
        self.adc_device.continuous_mode = True
        self.adc_channel = AnalogIn(self.adc_device)
        self._print_reads = print_reads

    def read_temp_humidity(self) -> float:
        raw = self.adc_channel.value
        # Convert bin to float
        v_out = raw / 131072 * 2.048
        # Convert Voltage to Resistance
        v_in = 3.3
        shunt_resistor = 32020
        r_thermistor = (v_out * shunt_resistor) / (v_in - v_out) 
        # Convert Resistance to Temperature (thermistor)
        f_temperature = -44.91*math.log(r_thermistor)+493.17
        if self._print_reads:
            print(f"MCP3421 Voltage:\t{v_out:0.3f}V\tThermistor: {int(r_thermistor)}ohms\tTempature: {f_temperature:0.1f}degF")   
        return SingleTempHumidityMeasurement(f_temperature, 0)

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

    def __init__(self, 
                i2c_bus_number : int = 1, 
                i2c_addr : int = 0x2F):
        self.i2c_bus_number = i2c_bus_number
        self.address = i2c_addr

    def read_distance_inches(self):
        bus = smbus2.SMBus(self.i2c_bus_number)
        try:
            # Write to initiate measurement
            bus.write_byte(self.address, 0x01)
            time.sleep(self._WRITE_READ_DELAY_SECS)  # Wait for measurement to complete

            # Read 2 bytes of data
            data = bus.read_i2c_block_data(self.address, 0x01, 2)
            bus.close()
            distance = ((data[0] & 0x7F) << 8) + data[1]
            distance_cm = distance / 10
            distance_in = distance_cm / 2.54
            return distance_in
        except Exception as e:
            print(f"Error reading distance: {e}")
            return None
    
    def print_distance(self, include_bar=True):
        distance_in = self.read_distance_inches()
        if distance_in == 0:
            print("[Ultrasonic] Out of range")
        elif distance_in is not None:
            meas_str = f"Ultrasonic] Distance: {distance_in:.2f}]"
            if include_bar:
                max_distance = 100
                max_bars = 80
                bars = int((distance_in / max_distance) * max_bars)
                meas_str += "[:->"
                for i in range(bars):
                    meas_str += "#"
            print(meas_str)

if __name__ == "__main__":
    ultra_sonic_sensor = TCT40Sensor()
    temp_humidity_sensor = sht31(I2C(SCL, SDA), i2c_addr=0x45)
    thermistor = mcp3421Thermistor(I2C(SCL, SDA), i2c_addr=0x68)
    while True:
        ultra_sonic_sensor.print_distance()
        temp_humidity_sensor.read_temp_humidity()
        thermistor.read_temp_humidity()
        time.sleep(0.1)