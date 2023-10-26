# Copyright @ 2023, Adrian Blakey. All rights reserved
from microdot import Microdot
from machine import Pin

import bluetooth
from ble_simple_peripheral import BLESimplePeripheral
import logging

log = logging.getLogger("main")

app = Microdot()
app.debug = True
@app.route('/')
def index(request):
    return 'Hello, from Pico'
        
# app.run()

# Create a Bluetooth Low Energy (BLE) object
ble = bluetooth.BLE()

# Create an instance of the BLESimplePeripheral class with the BLE object
sp = BLESimplePeripheral(ble)

# Create a Pin object for the onboard LED, configure it as an output
led = Pin("LED", Pin.OUT)

# Initialize the LED state to 0 (off)
led_state = 0

# Define a callback function to handle received data
def on_rx(data):
    log.debug("Bluetooth data received: ", data)  # Print the received data
    global led_state  # Access the global variable led_state
    if data == b'toggle':  # Check if the received data is "toggle"
        log.debug("Matches")
        led.value(not led_state)  # Toggle the LED state (on/off)
        led_state = 1 - led_state  # Update the LED state

# Start an infinite loop
if __name__ == "__main__":
    app.run(port=80)
    while True:
        if sp.is_connected():  # Check if a BLE connection is established
            sp.on_write(on_rx)  # Set the callback function for data reception


