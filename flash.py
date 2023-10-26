from machine import Pin
from utime import sleep

led = Pin("LED", Pin.OUT)

print("Start flashing")

while True:
    led.toggle()
    sleep(1)
    
