
import threading
import random
import time
import datetime
import platform
import json

import paho.mqtt.client as mqtt
from board import SCL, SDA
from busio import I2C
from gpiozero import Button

import logger
import config
import sensors
import depth_sensor

'''
TODO:
1. Add Tare Button function
'''

class HydroTankMonitor:

    '''
    Initialize app logger and config; prepare to start monitoring.
    Note: Keeping the top-level class as generic as possible for reusability.
    Design Pattern: 
        Initialize
        Read Sensors and Inputs
        Publish to Display and OpenHAB
        Repeat
    Sensors:
        1. Water Depth
        2. Environment Temperature and Humidity
        3. Water Temperature
    Input/Output:
        1. Zero Depth Button
        2. Local Display
        3. MQTT to OpenHAB
    '''
    def __init__(self, config_file_name : str = "default.conf"):
        self._log_key = "main"
        self._app_logger = logger.Logger()
        self._app_logger.write(self._log_key, "Initializing...", logger.MessageLevel.INFO)  

        # Load config
        self._app_config = config.ConfigManager(config_file_name, self._app_logger)

        # Create and connect to MQTT Broker - fail if unable to connect
        self._mqtt_client_connect()
        
        # Create I2C Bus and initialize sensors
        # Water Depth Sensor (TCT40)
        i2c_addr_water_depth_sensor = self._app_config.active_config["sensors"]["water_depth"]["i2c_addr"]
        self.ultra_sonic_sensor = depth_sensor.TCT40Sensor(bus_number=1, address=i2c_addr_water_depth_sensor)
        # Environment Temperature and Humidity Sensor (SHT31)
        i2c_addr_env_sensor = self._app_config.active_config["sensors"]["env_temp_humidity"]["i2c_addr"]
        self._sensor_environment_temp_humidity = sensors.sht31(I2C(SCL, SDA), i2c_addr_env_sensor)
        # Water Temperature (MCS3421 Thermistor)
        i2c_addr_water_temperature = self._app_config.active_config["sensors"]["water_temperature"]["i2c_addr"]
        self._sensor_water_temperature = sensors.mcp3421Thermistor(I2C(SCL, SDA), i2c_addr_water_temperature)

        # Intialize Digital Input for zero button
        self._init_zero_button()
        self._zero_offset = 0
    
        # Initialization complete.
        self._app_logger.write(self._log_key, "Initialized.", logger.MessageLevel.INFO) 

    '''
    Start the read / publish thread.
    '''
    def start(self):
        # Build and start processing thread
        self._app_logger.write(self._log_key, "Starting monitoring thread...", logger.MessageLevel.INFO)    
        self._data_processing_thread = threading.Thread(target=self._sensor_read_publish_thread)
        self._data_processing_thread.start()
        self._app_logger.write(self._log_key, "Monitoring thread started.", logger.MessageLevel.INFO) 
    '''
    Stop the read / publish thread.
    '''
    def stop(self):
        self._app_logger.write(self._log_key, "Stopping monitoring thread...", logger.MessageLevel.INFO) 
        self._data_processing_thread.stop()
        self._app_logger.write(self._log_key, "Monitoring thread stopped.", logger.MessageLevel.INFO) 
    
    ''' ------ Private Functions ------'''
    '''
    Main program thread: read sensors and publish data
    '''
    def _sensor_read_publish_thread(self):
        sensor_sample_period_seconds = self._app_config.active_config["sensor_sample_period_seconds"]
        sensor_sample_period_seconds = 1
        while True:
            # Read Sensors
            sensor_data = dict()
            sensor_data["timestamp_iso"] = datetime.datetime.now().isoformat()
            
            sensor_data["env_temperature_f"] = self._sensor_environment_temp_humidity.read_temp_humidity().temperature
            sensor_data["env_humidity"] = self._sensor_environment_temp_humidity.read_temp_humidity().humidity
            sensor_data["water_temperature_f"] = self._sensor_water_temperature.read_temp_humidity().temperature

            # Water Depth
            water_depth_inverted = -1 * self.ultra_sonic_sensor.read_distance_inches()
            sensor_data["water_depth"] = water_depth_inverted + self._zero_offset
            sensor_data["water_depth_offset"] = self._zero_offset
            
            # Update Display
            # TODO: Update Display

            # Publish Sensor Data to OpenHab
            topic_parts = [self._app_config.active_config['mqtt']['base_topic']]
            if self._app_config.active_config['mqtt']['use_host_name_in_mqtt_topic'] is True:
                topic_parts.append(platform.node())
            else:
                topic_parts.append(self._app_config.active_config['mqtt']['not_host_hame']) 
            topic_parts.append(self._app_config.active_config['mqtt']['sensor_topic'])
            sensor_mqtt_topic = self._mqtt_topic_join(topic_parts)
            
            data_json_str = json.dumps(sensor_data)
            self._mqtt_publish(sensor_mqtt_topic, data_json_str)

            # Sleep
            time.sleep(sensor_sample_period_seconds)
    
    '''
    Join MQTT topic parts into a single string with single slashes
    '''
    def _mqtt_topic_join(self, topic_parts: list) -> str:
        topic_parts = [part.strip("/") for part in topic_parts]
        return "/".join(topic_parts)

    '''
    Creates the mqtt client and connects to the broker
    '''
    def _mqtt_client_connect(self):
        client_id = f'python-mqtt-{random.randint(0, 1000)}'
        self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
        self._mqtt_client.on_connect = self._mqtt_on_connect
        self._mqtt_client.on_publish = self._mqtt_on_publish
        
        server_url = self._app_config.active_config["mqtt"]["server_url"]
        server_port = self._app_config.active_config["mqtt"]["server_port"]
        mqtt_conn_code = self._mqtt_client.connect(server_url, server_port, 60)
        self._mqtt_client.loop_start()
        self._app_logger.write(self._log_key, f"MQTT Client Connect Code: {mqtt_conn_code}", logger.MessageLevel.INFO)
        time.sleep(0.5)
        mqtt_connected = self._mqtt_client.is_connected()
        if mqtt_connected is False:
            mqtt_client_err_msg = "Client failed to connect to MQTT Broker."
            self._app_logger.write(self._log_key, mqtt_client_err_msg, logger.MessageLevel.ERROR)
            raise Exception(mqtt_client_err_msg)
    
    '''
    Publish a message to the MQTT Broker
    '''
    def _mqtt_publish(self, mqtt_topic, json_str_msg, validate_connection=True):
        # Validate connection (if enabled)
        if validate_connection is True:
            if self._mqtt_client is None or self._mqtt_client.is_connected() is False:
                self._mqtt_client_connect()
        # Publish message
        qos = 2
        retain = True
        mqtt_msg_info = self._mqtt_client.publish(mqtt_topic, 
                                                 json_str_msg, 
                                                 qos, 
                                                 retain)
        self._app_logger.write("mqtt", f"Message published w/ code: {mqtt_msg_info.rc}", logger.MessageLevel.INFO)
        
    '''
    The callback for when the client receives a CONNACK response from the server.
    '''
    def _mqtt_on_connect(self, client, userdata, flags, rc):
        self._app_logger.write("mqtt", "Connected with result code "+str(rc), logger.MessageLevel.INFO)

    '''
    The callback for when a message is published to the server
    '''
    def _mqtt_on_publish(self, client, userdata, msg):
        self._app_logger.write("mqtt", f"Message published: {msg}", logger.MessageLevel.INFO)

    '''
    Initialize the digital input for zero water distance button
    '''
    def _init_zero_button(self):    
        button_gpio_pin = self._app_config.active_config['zero_button_pin']
        button_gpio_pin = 17
        self._zero_button = Button(button_gpio_pin)
        self._zero_button.when_pressed = self._zero_button_pressed_callback
        # Set up GPIO using BCM numbering
    
    '''
    Called when button press is detected. Capture the current distance as an offset
    '''
    def _zero_button_pressed_callback(self, channel):
        self._app_logger.write("digital_input", "Zero button pressed.", logger.MessageLevel.INFO)
        # Add logic to handle zeroing the water depth sensor
        self._zero_offset = self.ultra_sonic_sensor.read_distance_inches()
        self._app_logger.write("digital_input", f"Setting offset to {self._zero_offset:.2f}", logger.MessageLevel.INFO)
        
if __name__ == "__main__":
    monitor = HydroTankMonitor()
    monitor.start()
