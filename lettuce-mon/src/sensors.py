from busio import I2C
from adafruit_bus_device import i2c_device

import adafruit_hts221

import adafruit_mcp3421.mcp3421 as ADC
from adafruit_mcp3421.analog_in import AnalogIn

import datetime
import json
import math

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
    def __init__(self, i2c : I2C, i2c_addr : int = 0x44) -> None:
        self.i2c_device = i2c_device.I2CDevice(i2c, i2c_addr)

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
                 i2c_addr : int = 0x68) -> None:
        self.adc_device = ADC.MCP3421(i2c)
        self.adc_device.gain = 1
        self.adc_device.resolution = 18
        self.adc_device.continuous_mode = True
        self.adc_channel = AnalogIn(self.adc_device)

    def read_temp_humidity(self) -> float:
        raw = self.adc_channel.value
        # Convert bin to float
        v_out = raw / 131072 * 2.048
        # Convert Voltage to Resistance
        v_in = 5.4
        shunt_resistor = 32020
        r_thermistor = (v_out * shunt_resistor) / (v_in - v_out) 
        # Convert Resistance to Temperature (thermistor)
        f_temperature = -44.91*math.log(r_thermistor)+493.17
        print(f"MCP3421 Voltage:\t{v_out:0.3f}V\tThermistor: {int(r_thermistor)}ohms\tTempature: {f_temperature:0.1f}degF")   
        return SingleTempHumidityMeasurement(f_temperature, 0)