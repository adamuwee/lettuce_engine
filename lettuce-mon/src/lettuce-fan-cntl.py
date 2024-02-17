'''
Service script that controls and monitors the fan speed of the lettuce farm.
'''

import datetime
import time
import RPi.GPIO as GPIO
from threading import Lock

import logging
import paho.mqtt.client as mqtt

import queue
import copy

class TripleFanController:

# Pi Pin Config

    # Private Class Members
    _pwm = None
    _tach_lock = None

    '''
    Object initialization
    '''
    def __init__(self, 
                    pwn_pin : int = 32 , 
                    fan1_tach_pin : int= 15 , 
                    fan2_tach_pin : int= 13 , 
                    fan3_tach_pin : int= 11,
                    pwm_freq : int = 10000):
        self._pwn_pin = pwn_pin
        self._fan1_tach_pin = fan1_tach_pin
        self._fan2_tach_pin = fan2_tach_pin
        self._fan3_tach_pin = fan3_tach_pin
        self._pwm_freq = pwm_freq
        self._last_tach_time = datetime.datetime.now()

        self._tach_counts = {
            self._fan1_tach_pin: 0,
            self._fan2_tach_pin: 0,
            self._fan3_tach_pin: 0
        }

        # Initialize GPIO
        self._init_pi_pins()
        # Lock for tach counts. Interrupt vs. user call.
        self._tach_lock = Lock()

    '''
    Set the fan speed duty cycle (0-100)
    '''
    def set_fan_pwm(self, duty_cycle : int):
        # Invert DC
        inv_dc = 100 - duty_cycle
        self._pwm.ChangeDutyCycle(inv_dc)

    '''
    Returns the three fan speeds in RPM.
    By default resets the counter
    '''
    def get_fan_speeds(self, reset_count : bool = True) -> tuple:
        # First calculate the time since the last tach event
        delta = datetime.datetime.now() - self._last_tach_time  
        self._last_tach_time = datetime.datetime.now()    

        # Calculate RPM
        with self._tach_lock:
            tach_counts_snap = dict(self._tach_counts)
            tach1 = int(tach_counts_snap[self._fan1_tach_pin] / delta.total_seconds() * 60.0)
            tach2 = int(tach_counts_snap[self._fan2_tach_pin] / delta.total_seconds() * 60.0)
            tach3 = int(tach_counts_snap[self._fan3_tach_pin] / delta.total_seconds() * 60.0)

            # Reset counters if requested
            if (reset_count):
                for tc in self._tach_counts:
                    self._tach_counts[tc] = 0
        
        return (tach1, tach2, tach3)
    
    '''
    Return fan speeds as console friendly string
    '''
    def get_fan_speeds_as_str(self) -> str:
        fan_speeds = self.get_fan_speeds()
        if fan_speeds is not None:
            return f"Fan 1 = {fan_speeds[0]:04d}\tFan 2 = {fan_speeds[1]:04d}\tFan 3 = {fan_speeds[2]:04d}"
        else:
            return "No fan speeds measured"
        pass

    '''
    Initialize GPIO for PWM control and tach measurement
    '''
    def _init_pi_pins(self):
        # Use BOARD mode
        GPIO.setmode(GPIO.BOARD)
        # Tach Input Pins
        GPIO.setup(self._fan1_tach_pin, GPIO.IN)
        GPIO.setup(self._fan2_tach_pin, GPIO.IN)
        GPIO.setup(self._fan3_tach_pin, GPIO.IN)
        GPIO.add_event_detect(self._fan1_tach_pin, GPIO.FALLING, callback=self._callback_fan_tach)
        GPIO.add_event_detect(self._fan2_tach_pin, GPIO.FALLING, callback=self._callback_fan_tach)
        GPIO.add_event_detect(self._fan3_tach_pin, GPIO.FALLING, callback=self._callback_fan_tach)
        # PWM Output Pin
        GPIO.setup(self._pwn_pin, GPIO.OUT)
        GPIO.output(self._pwn_pin, GPIO.LOW)
        self._pwm = GPIO.PWM(self._pwn_pin, self._pwm_freq)
        self._pwm.start(0)   

    '''
    Called once per fan revolution (tach pin falling edge)
    '''
    def _callback_fan_tach(self, tach_channel):
        with self._tach_lock:
            self._tach_counts[tach_channel] += 1


'''
Represents a MQTT client that connects to the OpenHAB MQTT broker
'''
class MqttClient:

    '''
    Represents one payload received for a given mqtt topic
    '''
    class MqttTopicQueueElement:
        def __init__(self, topic : str, payload):
            self.topic = topic
            self.payload = payload
            self.created = datetime.datetime.now()

    '''
    Init mqtt client
    '''
    def __init__(self,
                    openhab_host : str = "debian-openhab",
                    mqtt_broker_port : int = 1883,
                    logger : logging.Logger = None):
        
        # Class Locals
        self.log_key = "Mqtt Client"
        self._openhab_host = openhab_host
        self._mqtt_broker_port = mqtt_broker_port
        self._flag_connected = False
        self._sub_payload_queue = list()
        self._sub_payload_queue_lock = Lock()

        # Mqtt Client
        self._client = mqtt.Client()
        self._client.on_connect = self._on_client_connect
        self._client.on_disconnect = self._on_client_disconnect
        self._client.on_message = self._on_client_message
        self._client.connect(self._openhab_host, self._mqtt_broker_port)
        
        # Client Logger
        self._logger = logger
        self._log("MQTT Client Object Created.")


    '''
    Attempt to connect to the broker
    '''
    def try_connect(self) -> bool:     
        try:
            self._client.connect(self._openhab_host, self._mqtt_broker_port)
            self._client.loop_start()
        except:
            self._log('MQTT client connect failure')
            self._flag_connected = False
        if self._flag_connected == 1:
            self._client.loop_start()
        self._log(f'Connected = {(self._flag_connected == 1)}')
        return (self._flag_connected == 1)

    '''
    Returns true if the client is connected to the MQTT Broker.
    '''
    def is_connected(self) -> bool:
        return self._flag_connected

    '''
    Returns True if the payload was successfully published to the topic.
    Returns an error message if not.
    '''
    def try_publish(self, topic: str, payload) -> tuple:
        publish_ok = False
        err_msg = "msg init"
        try:
            mqtt_msg_info = self._client.publish(topic, payload)
            publish_ok = mqtt_msg_info.is_published()
            err_msg = f"Publish RCL {mqtt_msg_info.rc}"
        except:
            publish_ok = False
            err_msg = "Unknown publish error"
        return (publish_ok, err_msg)
    
    '''
    Subscribe to a topic
    '''
    def subscribe(self, topic : str):
        self._client.subscribe(topic)

    '''
    Get a copy of the 
    '''
    def flush_subscription_topic_queue(self) -> queue:
        with self._sub_payload_queue_lock:
            queue_copy = copy.deepcopy(self._sub_payload_queue)
            self._sub_payload_queue.clear()
            return queue_copy

    '''
    Connect callback
    '''
    def _on_client_connect(self, client, userdata, flags, rc):
        self._flag_connected = 1
        self._log("Client connected.")

    '''
    Disconnect callback
    '''
    def _on_client_disconnect(self, client, userdata, rc):
        self._flag_connected = 0
        self._log("Client disconnected.")

    '''
    Callback for receiving messages to subscribed mqtt topics
    '''
    def _on_client_message(self, client, userdata, message):
        mtte = MqttClient.MqttTopicQueueElement(message.topic, message.payload)
        self._log(f"Msg Recv'd: {message.topic} --> {message.payload}")
        with self._sub_payload_queue_lock:
            self._sub_payload_queue.append(mtte)
    
    '''
    Interal log method
    '''
    def _log(self, log_msg : str):
        if (self._logger != None):
            self._logger.info(f'MQTT Client: {log_msg}')
        print(f"{self.log_key}: {log_msg}")


'''
Main Loop for Fan Controller
'''
def main():

    # Service Config
    loop_period_seconds = 2
    openhab_host = "debian-openhab"
    mqtt_broker_port = 1883

    # Mqtt Topics
    fan_1_rpm_topic = "lettuce_box/seedling_box/fan_1/rpm"
    fan_2_rpm_topic = "lettuce_box/seedling_box/fan_2/rpm"
    fan_pwm_set_point_topic = "lettuce_box/seedling_box/fan/pwm"

    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    
    # Debug File Log
    file = logging.FileHandler("debug_lettuce_fan_controller.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_lettuce_fan_controller.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)

    # Create Fan Controller object
    fan_controller = TripleFanController()

    # Test RPM Set Point
    test_rpm_set_points = False
    if test_rpm_set_points:
        test_sleep_time = 5
        pwm_set_points = {0, 25, 50, 75, 100}
        for sp in pwm_set_points:
            fan_controller.set_fan_pwm(sp)
            time.sleep(test_sleep_time)
            print(f"Set Point = {sp}% :: {fan_controller.get_fan_speeds_as_str()}")

    # Initialize MQTT Client
    mqtt_client = MqttClient()
    mqtt_client.try_connect()

    # Subscribe to fan set point
    mqtt_client.subscribe(fan_pwm_set_point_topic)

    # Infinite loop of reporting temperature and setting fan speed based on temperature
    while True:

        if mqtt_client.is_connected():
            # Report fan speed
            fan_speeds = fan_controller.get_fan_speeds()
            mqtt_client.try_publish(fan_1_rpm_topic, fan_speeds[0])
            mqtt_client.try_publish(fan_2_rpm_topic, fan_speeds[1])

            # Check if a new set point is availble
            sub_messages = mqtt_client.flush_subscription_topic_queue()
            for msg in sub_messages:
                if msg.topic == fan_pwm_set_point_topic:
                    pwm_set_point = int(msg.payload)
                    fan_controller.set_fan_pwm(pwm_set_point)
                    print(f"New Set Point Received = {pwm_set_point}%")

        else:
            mqtt_client.try_connect()
            mqtt_client.subscribe(fan_pwm_set_point_topic)

        time.sleep(loop_period_seconds)

if __name__ == "__main__":
    main()