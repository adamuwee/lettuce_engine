'''
Service script that controls and monitors the fan speed of the lettuce farm.
'''

import datetime
import RPi.GPIO as GPIO

class TripleFanController:

# Pi Pin Config

    '''
    Object initialization
    '''
    def __init__(self, 
                    pwn_pin : int = 32 , 
                    fan1_tach_pin : int= 15 , 
                    fan2_tach_pin : int= 13 , 
                    fan3_tach_pin : int= 11,
                    pwm_freq : int = 10000):
        self.pwn_pin = pwn_pin
        self.fan1_tach_pin = fan1_tach_pin
        self.fan2_tach_pin = fan2_tach_pin
        self.fan3_tach_pin = fan3_tach_pin
        self.pwm_freq = pwm_freq
        self._last_tach_time = datetime.now()

    def _init_pi_pins(self):
        # Use BOARD mode
        GPIO.setmode(GPIO.BOARD)
        # Tach Input Pins
        GPIO.setup(tach1_pin, GPIO.IN)
        GPIO.setup(tach2_pin, GPIO.IN)
        GPIO.setup(tach3_pin, GPIO.IN)
        GPIO.add_event_detect(tach1_pin, GPIO.FALLING, callback=count_tach_pulse)
        GPIO.add_event_detect(tach2_pin, GPIO.FALLING, callback=count_tach_pulse)
        GPIO.add_event_detect(tach3_pin, GPIO.FALLING, callback=count_tach_pulse)
        # PWM Output Pin
        GPIO.setup(pwm_pin, GPIO.OUT)
        GPIO.output(pwm_pin, GPIO.LOW)
        global pwm
        pwm = GPIO.PWM(pwm_pin, pwm_freq)
        pwm.start(0)   

    def set_fan_pwm(duty_cycle):
        # Invert DC
        inv_dc = 100 - duty_cycle
        pwm.ChangeDutyCycle(inv_dc)
    '''
    Called once per fan revolution
    '''
    def _callback_fan_tach(self, channel):
        pass
