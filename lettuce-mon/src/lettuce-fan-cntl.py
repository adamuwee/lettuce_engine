'''
Service script that controls and monitors the fan speed of the lettuce farm.
'''

import datetime
import RPi.GPIO as GPIO
from threading import Lock

import logging
import paho.mqtt.client as mqtt

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
        self._last_tach_time = datetime.now()

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
        delta = datetime.now() - self._last_tach_time  
        self._last_tach_time = datetime.now()    

        # Calculate RPM
        with self._tach_lock:
            tach_counts_snap = dict(self._tach_counts)
            tach1 = tach_counts_snap[self._fan1_tach_pin] / delta * 60.0
            tach2 = tach_counts_snap[self._fan2_tach_pin] / delta * 60.0
            tach3 = tach_counts_snap[self._fan3_tach_pin] / delta * 60.0

            # Reset counters if requested
            if (reset_count):
                for tc in self._tach_counts:
                    self._tach_counts[tc] = 0
        
        return (tach1, tach2, tach3)

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
    Init mqtt client
    '''
    def __init__(self,
                    openhab_host : str = "debian-openhab",
                    mqtt_broker_port : int = 1883,
                    logger : logging.Logger = None):
        self._openhab_host = openhab_host
        self._mqtt_broker_port = mqtt_broker_port
        self._flag_connected = False
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.connect(self.openhab_host, self.mqtt_broker_port)
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

    # MQTT Client


    def is_connected(self) -> bool:
        return self._flag_connected

    def try_publish(self, topic: str, payload : str) -> tuple:
        publish_ok = False
        err_msg = "Unknown publish error"
        
        return (publish_ok, err_msg)
    '''
    Connect callback
    '''
    def _on_connect(self, client, userdata, flags, rc):
        self._flag_connected = 1
        self._log("Client connected.")

    '''
    Disconnect callback
    '''
    def _on_disconnect(self, client, userdata, rc):
        self._flag_connected = 0
        self._log("Client disconnected.")
    
    def _log(self, log_msg : str):
        if (self._logger != None):
            self._logger.info(f'MQTT Client: {log_msg}')


'''
Main Loop for Fan Controller
'''
def main():

    # Service Config
    loop_period_seconds = 10
    openhab_host = "debian-openhab"
    mqtt_broker_port = 1883

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

    # Initialize MQTT Client
    mqtt_client = mqtt.Client()

    # Infinite loop of reporting temperature and setting fan speed based on temperature
    while True:
        # Check MQTT Client Connection
        if flag_connected == False:
            client.loop_stop()
            client.connect(openhab_host, mqtt_broker_port)
            client.loop_start()
            logger.info(f'MQTT Client Connected: {client}')

        monitor_temp_update_fans()
        time.sleep(loop_period_seconds)

if __name__ == "__main__":
    main()