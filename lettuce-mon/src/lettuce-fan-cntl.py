'''
Service script that controls and monitors the fan speed of the lettuce farm.
'''

import datetime
import RPi.GPIO as GPIO
from threading import Lock

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
