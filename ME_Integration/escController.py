import os  # importing os library so as to communicate with the system
import time  # importing time library to make Rpi wait because its too impatient
from enum import Enum

os.system("sudo pigpiod")  # Launching GPIO library
time.sleep(1)  # As i said it is too impatient and so if this delay is removed you will get an error
import pigpio  # importing GPIO library

ESC_LEFT = 4  # Connect the ESC_LEFT in this GPIO pin
ESC_RIGHT = 8  # second motor

pi = pigpio.pi();
pi.set_servo_pulsewidth(ESC_LEFT, 0)
pi.set_servo_pulsewidth(ESC_RIGHT, 0)

max_value = 2000  # change this if your ESC_LEFT's max value is different or leave it be
min_value = 700  # change this if your ESC_LEFT's min value is different or leave it be
curr_value_l = 0
curr_value_r = 0


class Direction(Enum):
    FORWARD = 0,
    RIGHT = 1,
    BACK = 2,
    LEFT = 3


def setDirection(direction, speed):
    pass


def setMotors(float1, float2):
    pass


def setSpeed(pickMotor, newSpeed):
    global curr_value_l, curr_value_r
    if pickMotor == ESC_LEFT:
        curr_speed = curr_value_l
    else:
        curr_speed = curr_value_r

    if curr_speed * newSpeed < 0:
        pi.set_servo_pulsewidth(pickMotor, 1500)
        time.sleep(1)
    pwmVal = int(1500 + (float(newSpeed) * 500))
    print(pwmVal)
    if -.15 < newSpeed < .15:
        pi.set_servo_pulsewidth(pickMotor, 1500)
    else:
        pi.set_servo_pulsewidth(pickMotor, pwmVal)

    if pickMotor == ESC_LEFT:
        curr_value_l = newSpeed
    else:
        curr_value_r = newSpeed


def arm():  # This is the arming procedure of an ESC_LEFT
    pi.set_servo_pulsewidth(ESC_LEFT, 0)
    pi.set_servo_pulsewidth(ESC_RIGHT, 0)
    time.sleep(1)
    pi.set_servo_pulsewidth(ESC_LEFT, max_value)
    pi.set_servo_pulsewidth(ESC_RIGHT, max_value)
    time.sleep(1)
    pi.set_servo_pulsewidth(ESC_LEFT, min_value)
    pi.set_servo_pulsewidth(ESC_RIGHT, min_value)
    time.sleep(1)


def stop():  # This will stop every action your Pi is performing for ESC_LEFT ofcourse.
    pi.set_servo_pulsewidth(ESC_LEFT, 0)
    pi.set_servo_pulsewidth(ESC_RIGHT, 0)
    pi.stop()
