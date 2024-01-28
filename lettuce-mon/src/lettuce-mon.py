print("lettuce!")

import time
import argparse
from board import SCL, SDA, D4
import busio
import digitalio

import paho.mqtt.client as mqtt

import ssd1305_display
import sensors

'''
Priority Development Order
1. Sensors: SHT31, HTS221 [done]
2. MQTT Publish [done]
3. Display [done]
4. Thermocouple for water temperature
'''

class TempHumiditySensor:

    _last_measurement = None
    '''
    Constructor
    '''
    def __init__(self, name : str, sensor_obj, base_mqtt_publish_topic : str):
        self._sensor_name = name
        self._sensor_obj = sensor_obj
        # Check if base topic has a trailing '/'
        if base_mqtt_publish_topic[-1] != "/":
            self._base_mqtt_publish_topic = base_mqtt_publish_topic + "/"
        else:
            self._base_mqtt_publish_topic = base_mqtt_publish_topic
    
    '''
    Update measurement from sensor (get)
    '''
    def update_measurement(self) -> (bool, str):
        read_okay = True
        ret_msg = ""
        self._last_measurement = None
        try:
            self._last_measurement = self._sensor_obj.read_temp_humidity()
        except:
            ret_msg = "Failed to read sensor"
            read_okay = False
        return (read_okay, ret_msg)
    
    '''
    Returns a mqtt-friendly topic string
    '''
    def get_mqtt_publish_topic(self) -> str:
        lower_name_no_spaces = self._sensor_name.lower().replace(" ", "_")
        mqtt_publish_topic = self._base_mqtt_publish_topic + lower_name_no_spaces + "/temp_humidity"
        return mqtt_publish_topic
    
    '''
    Returns a json formatted string to be published to mqtt
    '''
    def get_mqtt_measurement_string(self) -> str:
        if self._last_measurement is None:
            return ""
        else:
            return self._last_measurement.to_json()
    
    def get_last_temperature(self) -> float:
        if self._last_measurement is None:
            return float("NaN")
        else:
            return self._last_measurement.temperature
        
    def get_last_humidity(self) -> float:
        if self._last_measurement is None:
            return float("NaN")
        else:
            return self._last_measurement.humidity
    
    def get_name(self, limit_chars : int = 0) -> str:
        if limit_chars == 0:
            return self._sensor_name
        else:
            return self._sensor_name[0:limit_chars].ljust(limit_chars, " ")

class LettuceMonitor:

    # Defaults
    _oled_reset_pin = digitalio.DigitalInOut(D4)
    _display_i2c_addr = 0

    # Private Class Variables
    _sensors = list()

    '''
    Initialize the Lettuce Monitor object
    '''
    def __init__(self):
        
        # I2C Bus
        i2c = busio.I2C(SCL, SDA)

        # Initialize Display
        self._display = ssd1305_display.Display(i2c, self._display_i2c_addr, self._oled_reset_pin)

        # Create Sensor Objects
        mqtt_base_topic = "lettuce_box/"
        self._sensors.append(TempHumiditySensor("Seedling Box", sensors.sht31(i2c, 0x44), mqtt_base_topic))
        self._sensors.append(TempHumiditySensor("Main Box", sensors.sht31(i2c, 0x45), mqtt_base_topic))
        self._sensors.append(TempHumiditySensor("Room", sensors.hts221(i2c, 0x59), mqtt_base_topic))

        # Create MQTT Client
        self._mqtt_client = mqtt.Client()
        self._mqtt_client.on_connect = self._mqtt_on_connect
        self._mqtt_client.on_message = self._mqtt_on_message
        self._mqtt_client.connect("debian-openhab", 1883, 60)
        self._mqtt_client.loop_start()
    
    '''
    Read all the configured sensors and store results in memory
    '''
    def read_sensors(self) -> (bool, str):
        all_read_okay = True
        all_ret_msg = ""
        for sensor in self._sensors:
            (read_okay, ret_msg) = sensor.update_measurement()
            if read_okay == False:
                all_read_okay = False
                all_ret_msg = f"Failed to update measurement of {sensor.name}"
                break
        return (all_read_okay, all_ret_msg)
    
    '''
    Publish all the sensor data to the network.
    '''
    def publish_sensor_data(self) -> (bool, str):
        all_read_okay = True
        all_ret_msg = ""
        for sensor in self._sensors:
            if self._mqtt_client is not None:
                self._mqtt_client.publish(sensor.get_mqtt_publish_topic(), 
                                          sensor.get_mqtt_measurement_string(), 
                                          0, 
                                          True)
        return (all_read_okay, all_ret_msg)
    
    '''
    Display sensor data
    Limited to first three sensors
    '''
    def display_sensor_data(self) -> (bool, str):
        all_read_okay = True
        all_ret_msg = ""
        self._display.clear_screen()
        for index in range(3):
            sensor = self._sensors[index]
            sensor_str = f"{sensor.get_name(8)}     {sensor.get_last_temperature():0.1f}F    {sensor.get_last_humidity():0.1f}%"
            self._display.print_line(index, sensor_str)
        return (all_read_okay, all_ret_msg)
    
    # The callback for when the client receives a CONNACK response from the server.
    def _mqtt_on_connect(self, client, userdata, flags, rc):
        print("MQTT: Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        #client.subscribe("$SYS/#")

    # The callback for when a PUBLISH message is received from the server.
    def _mqtt_on_message(self, client, userdata, msg):
        print("MQTT: " + msg.topic+" "+str(msg.payload))

if __name__ == '__main__':

    # Parse CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--loop_count", type=int)
    parser.add_argument("-p", "--loop_period_seconds", type=int)
    args = parser.parse_args()

    loop_count = args.loop_count
    loop_period_seconds = args.loop_period_seconds

    # Optional Arg and bounds check
    if (loop_count == None or loop_count <= 0):
        loop_count = 1
        loop_period_seconds = 0
    print(f"Loop Count = {loop_count}")

    # Process Init
    lettuce = LettuceMonitor()

    # Process Loop
    for loop_index in range(loop_count):
        # Read the sensors
        (read_sensor_okay, err_msg) = lettuce.read_sensors()
        if not read_sensor_okay:
            print(err_msg)
            continue

        # MQTT Publish
        (publish_sensor_okay, err_msg) = lettuce.publish_sensor_data()
        if not publish_sensor_okay:
            print(err_msg)
            continue

        # Display
        (display_sensor_okay, err_msg) = lettuce.display_sensor_data()
        if not display_sensor_okay:
            print(err_msg)
            continue

        # Sleep
        if loop_period_seconds > 0:
            time.sleep(loop_period_seconds)
    