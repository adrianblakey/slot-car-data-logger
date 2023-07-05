"""
Copyright (c) 2023 Adrian Blakey
"""
import os
import sys
from stat import S_ISREG, ST_CTIME, ST_MODE
import ipaddress
import wifi
import socketpool
import asyncio
import board
import digitalio
import time
import microcontroller
from ulab import numpy as np
import analogio
import multiprocessing
from abc import ABC, abstractmethod
import csv

"""
Channels:

GP18 - LED, low = ON
GP22 - Push button
GP26/ADC0 - Current
GP27/ADC1 - Controller + output voltage to track and motor 
GP28/ADC2 - Track incoming + supply voltage

Set GP18 to output drive strength 12mA, to minimise volt-drop in the micro (PADS_BANK0: GPIOx Registers) 

Note: Worth experimenting with the SMPS mode pin (WL_GPIO1) to find out which
setting (low or high) gives the least noise in the ADC readings (with
the little test programme I got around 10 decimal variation, of a 12 bit
value, in the current zero value)

Please choose a pin to use as a programme loop time indicator,
toggles from one state to another each time round the loop.

The original intention for the push button was to calibrate the zero
current value (nominal 1/2 the micro 3V3 supply) with the black output
lead disconnected, but it could also be used to calibrate the voltage
signals by setting them to an exact 12.00V.

Assume there is a WiFi AP named "Slot Car Net" with password of sl0tc1r, connect to it - maybe if we ever get 
bluetooth we'll provide a way to enter a SSID/pwd.
Create a web server on this network with the hostname "Data Logger n" - increment the n value to find a unique id.


TODO:
Lots
Simplify the design to display values on a Web pages as they are read rather than trying queue and write them?
Use the async_button class https://circuitpython-async-button.readthedocs.io/en/latest/
Asynchronous queues?
How to add wifi params? choose a fixed ssid/pwd?
Run calibration when enter the state. 
Read the GPIO's continuously
Timer
Write the values to a IP address? 
How do we set a specific place to write the data? Use bonjour/zeroconf - hierarchy say? main one/personal
Each device will be flashed with a unique id. It'll look to find its network partner based on a convention.
e.g if I am sc-2139. I'll look for sc-2139-server, and sc-server say.
Add bluetooth when it's available
"""


class FlashSequence:
    """Class to hold a flash sequence
    Hold this as an array of on time/off time tuples and a separator to the next flash.
    """

    # Morse durations
    DI = .2  # 200msec shortest duration eye can see led on?
    DAH = 3 * DI
    SEP = 3 * DI

    QUICK_FLASHES = [(DI, DI)]  # on 200mSec, off 200mSec
    SOLID_ON = [(1, 0)]  # on, not off
    H_FLASH = [(DI, DI), (DI, DI), (DI, DI), (DI, DI)]
    C_FLASH = [(DAH, DI), (DI, DI), (DAH, DI), (DI, DI)]
    V_FLASH = [(DI, DI), (DI, DI), (DI, DI), (DAH, DI)]
    SEPARATOR_FLASH = [(0, DI + DI + DI)]     # off, not on for 3
    START_UP_QUICK_FLASH = [(DI, 0)]       # quick flash then off

    def __init__(self):
        self.flashes = FlashSequence.SOLID_ON
        self.separator = None

    def __str__(self) -> str:
        # TODO make this more useful
        for flashes in self._flashes:
            print(flashes[0], flashes[1])
        if self._separator is not None:
            for sep_flashes in self._separator:
                print(sep_flashes[0], sep_flashes[1])
        else:
            print("No separator between flashes")

    @property
    def flashes(self) -> [()]:
        return self._flashes

    @flashes.setter
    def flashes(self, flash_sequence: [(int, int)]):
        print("flashes setter")
        self._flashes = flash_sequence
        if np.all(np.equal(self._flashes, FlashSequence.QUICK_FLASHES)):
            print("setting quick flashes")
            self._separator = None
        elif np.all(np.equal(self._flashes, FlashSequence.SOLID_ON)):
            print("setting solid on")
            self._separator = None
        else:
            self._separator = FlashSequence.SEPARATOR_FLASH

    @property
    def separator(self) -> [()]:
        return self._separator

    @separator.setter
    def separator(self, value: [()]):
        self._separator = value


class Electricity(ABC):
    """Abstract base class for voltages and current"""
    @abstractmethod
    def value(self) -> int:
        pass

    @abstractmethod
    def value(self, value: int):
        pass


class Voltage(Electricity):
    """ADC read voltage"""
    def __init__(self):
        self.value = 0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value


class Current(Electricity):
    """ADC read current"""
    def __init__(self):
        self.value = 0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float):
        self._value = value


class Calibrate:
    """ Class to hold the state of the modal calibration button.
        Modal:
            Initial state = no calibration
            Current calibration
            Voltage calibration
        """
    # Main modes
    OFF = 0                     # calibration off
    CURRENT = 1                 # current calibration
    VOLTAGE = 2                 # voltage calibration

    # Sub state modes
    WAITING_TO_REMOVE_BLACK = 0
    WAITING_TO_ATTACH_BLACK = 0

    def __init__(self):
        self.calibration = Calibrate.OFF

    def __str__(self) -> str:
        if self.calibration == Calibrate.OFF:
            return "Off"
        elif self.calibration == Calibrate.CURRENT:
            return "Current"
        elif self.calibration == Calibrate.VOLTAGE:
            return "Voltage"

    @property
    def calibration(self) -> int:
        return self._calibration

    @calibration.setter
    def calibration(self, value: int):
        self._calibration = value


    # Bumps the mode up based on current value
    def bump_mode(self):
        if self._calibration == Calibrate.OFF:
            self._calibration = Calibrate.CURRENT
        elif self._calibration == Calibrate.CURRENT:
            self._calibration = Calibrate.VOLTAGE
        elif self._calibration == Calibrate.VOLTAGE:
            self._calibration = Calibrate.OFF

    def is_off(self) -> bool:
        return self._calibration == Calibrate.OFF

    def is_current(self) -> bool:
        return self._calibration == Calibrate.CURRENT

    def is_voltage(self) -> bool:
        return self._calibration == Calibrate.VOLTAGE


def flash_error():
    print("Error")
    #TODO flash an error that no network connection


def scan_wifi():
    print("Available networks")
    for network in wifi.radio.start_scanning_networks():
        print("\t%s\t\tRSSI: %d\tChannel: %d" % (str(network.ssid,"utf-8"), network.rssi, network.channel))
    wifi.radio.stop_scanning_networks()


def scan_wifi_for(ssid: str):
    return_network = None
    for network in wifi.radio.start_scanning_networks():
        if network.ssid == ssid:
            print("\t%s\t\tRSSI: %d\tChannel: %d" % (str(network.ssid, "utf-8"), network.rssi, network.channel))
            return_network = network
            break
    wifi.radio.stop_scanning_networks()
    if return_network is None:
        flash_error()  # Flash error - flash both leds quickly?
        raise RuntimeError("Can't find a network named " + ssid)
    return


def connect_as(ssid: str, hostname: str, suffix='_red', count=1, tries=8):
    wifi.radio.hostname = hostname + suffix
    wifi.radio.connect(ssid, os.getenv('CIRCUITPY_WIFI_PASSWORD'))
    if wifi.radio.connected is True:
        print("Connected to WiFi")
        pool = socketpool.SocketPool(wifi.radio)
        #  prints MAC address to REPL
        print("My MAC addr:", [hex(i) for i in wifi.radio.mac_address])
        #  prints IP address to REPL
        print("My IP address is", wifi.radio.ipv4_address)
        print("My hostname is", wifi.radio.hostname)
    else:
        if count != tries:
            count += 1
            # TODO this is a hack to set hostnames like lane colors
            if suffix == '_red':
                suffix = '_green'
            elif suffix == '_green':
                suffix = '_blue'
            elif suffix == '_blue':
                suffix = '_white'
            elif suffix == '_white':
                suffix = '_black'
            elif suffix == '_black':
                suffix = '_purple'
            else:
                suffix = ''
            connect_as(ssid, hostname, suffix, count, tries)  # 8 lanes - first one red
        else:
            print("not connected - name conflicts?")
            flash_error()  # Flash error - flash both leds quickly?
            raise RuntimeError("Can't connect to wifi network named " + ssid)


def connect_to_wifi():
    print()
    print("Connecting to WiFi")
    ssid = os.getenv('CIRCUITPY_WIFI_SSID')
    scan_wifi_for(ssid)
    #  connect to your SSID from values in settings.toml
    connect_as(ssid, 'slot_car_logger', '_red', 1, 8)  # 8 lanes - first one red


def ping_google():
    #  pings Google
    ipv4 = ipaddress.ip_address("8.8.4.4")
    print("Ping google.com: %f ms" % (wifi.radio.ping(ipv4)*1000))


def led_on(pin, drive_mode: digitalio.DriveMode) -> None:
    # Turn on the led on the specific pin
    with digitalio.DigitalInOut(pin) as led:
        led.switch_to_output(value=True, drive_mode=drive_mode)
        led.direction = digitalio.Direction.OUTPUT
        print(pin, " led on")


def quick_flash(pin):
    with digitalio.DigitalInOut(pin) as led:
        print("flash led")
        led.switch_to_output()
        if led.value:  # Turn off the led for 100mS
            led.value = not led.value
        led.value = True  # turn on
        time.sleep(0.5)
        led.value = False  # turn off


async def flash_led(pin, flash_sequence: [()]):
    with digitalio.DigitalInOut(pin) as led:
        print("flash led")
        led.switch_to_output()
        if led.value:                            # Turn off the led for 100mS
            led.value = not led.value
        while True:
            print("flash the seqn ", flash_sequence)
            for flashes in flash_sequence.flashes:   # iterate through the on off tuples
                on_time = flashes[0]
                off_time = flashes[1]
                print("On time: ", str(on_time), " Off time: ", str(off_time))
                led.value = True  # turn on
                await asyncio.sleep(on_time)
                led.value = not led.value  # turn off
                await asyncio.sleep(off_time)   # wait off time
            if flash_sequence.separator is not None:
                print("flash seq separator", flash_sequence.separator)
                for flashes_sep in flash_sequence.separator:
                    on_time = flashes_sep[0]
                    off_time = flashes_sep[1]
                    print("Sep On time: ", str(on_time), " Sep Off time ", str(off_time))
                    if on_time != 0:
                        led.value = True  # turn on
                        await asyncio.sleep(on_time)
                    led.value = False  # turn off
                    await asyncio.sleep(off_time)  # wait off time


async def monitor_push_button(calibration_setting, board_flash_sequence, controller_flash_sequence):
    """Monitor the push button: each press changes the state.
    TODO: run the associated calibration"""
    with digitalio.DigitalInOut(board.GP22) as button:
        button.direction = digitalio.Direction.INPUT
        while True:
            if not button.value:
                print("Button pressed, this mode " + str(calibration_setting))
                calibration_setting.bump_mode()
                print("New mode " + str(calibration_setting))
                if calibration_setting.is_current():
                    board_flash_sequence.flashes = FlashSequence.C_FLASH
                    board_flash_sequence.separator = FlashSequence.SEPARATOR_FLASH
                elif calibration_setting.is_voltage():
                    board_flash_sequence.flashes = FlashSequence.V_FLASH
                    board_flash_sequence.separator = FlashSequence.SEPARATOR_FLASH
                else:
                    board_flash_sequence.flashes = FlashSequence.SOLID_ON
                    board_flash_sequence.separator = None

                # TODO if we enter current mode - remind the user to disconnect black and
                # TODO when they are ready hit the button again to run the calibration. Then
                # TODO replace the lead and hit button again to indicate end of calibration.
                # TODO maybe have some quick presses to just exit the calibration mode? x
            await asyncio.sleep(1)      # keep your finger on it for a second to change state


async def read_adc(pin: microcontroller.Pin, electricity: Electricity):
    with analogio.AnalogIn(pin) as adc:
        while True:
            electricity.value = (adc.value * 3.3) / 65536
            # TODO add/subtract the zero calibration value?
            print("adc value ", electricity.value)
            write_electric_value(electricity)
            await asyncio.sleep(0.1)     # 100mS






def open_electric_value(electricity: Electricity, tag: str):
    if isinstance(electricity, Voltage) & tag == 'C':
        name = '/data/' + file_prefix + '/' + 'cont_v.csv'
        header = ['time', 'voltage']
    elif isinstance(electricity, Voltage) & tag == 'T':
        name = '/data/' + file_prefix + '/'  'trak_v.csv'
        header = ['time', 'voltage']
    elif isinstance(electricity, Current):
        name = '/data/' + file_prefix + '/'  'cont_i.csv'
        header = ['time', 'current']
    else:
        pass
    try:
        with open(name, "w", encoding='UTF-8', newline='') as fp:
            writer = csv.writer(fp)
            writer.write(header)
    except OSError as e:
        pass


def write_controller_voltage():

def write_electric_value(electricity: Electricity, tag: str):
    row = [str(time.time()), '{0:f}'.format(electricity.value)]
    if isinstance(electricity, Voltage) & tag == 'C':
        name = '/data/' + file_prefix + '/'  'cont_v.csv'
    elif isinstance(electricity, Voltage) & tag == 'T':
        name = '/data/' + file_prefix + '/'  'trak_v.csv'
    elif isinstance(electricity, Current):
        name = '/data/' + file_prefix + '/'  'cont_i.csv'
    else:
        pass
    try:
        with open(name, "a", encoding='UTF-8', newline='') as fp:
            writer = csv.writer(fp)
            writer.writerow(row)
    except OSError as e:
        pass


async def main(board_led_task: asyncio.Task, controller_led_task: asyncio.Task,
               board_flash_sequence: FlashSequence, controller_flash_sequence: FlashSequence):
    print("create the calibration")
    calibration_setting = Calibrate()
    print("start the button task")
    button_task = asyncio.create_task(monitor_push_button(calibration_setting, board_flash_sequence, controller_flash_sequence))
    print("start the current reading task")
    controller_current = Current()
    controller_voltage = Voltage()
    track_voltage = Voltage()
    open_electric_value(controller_current)
    open_electric_value(controller_voltage, 'C')
    open_electric_value(track_voltage, 'T')
    controller_current_task = asyncio.create_task(read_adc(board.GP26, controller_current))  # ADC0
    controller_voltage_task = asyncio.create_task(read_adc(board.GP27, controller_voltage))
    track_voltage_task = asyncio.create_task(read_adc(board.GP28, track_voltage))
    await asyncio.gather(board_led_task, controller_led_task, button_task, controller_current_task,
                         controller_voltage_task, track_voltage_task)  # Don't forget the await!


def startup(board_flash_sequence: FlashSequence, controller_flash_sequence: FlashSequence):
    """initialization function"""
    quick_flash(board.LED)
    quick_flash(board.GP18)
    led_on(board.LED, digitalio.DriveMode.PUSH_PULL)
    led_on(board.GP18, digitalio.DriveMode.OPEN_DRAIN)

    # ext_led_task = asyncio.create_task(flash_led(board.GP18, 0.25, 10))
    """Start the led flashing tasks - need these to indicate issues from now on"""
    print("flash the pico board led")
    board_led_task = asyncio.create_task(flash_led(board.LED, board_flash_sequence))  # flash the pico board led
    print("flash the controller board led")
    controller_led_task = asyncio.create_task(flash_led(board.GP18, controller_flash_sequence))  # flash the controller board led

    scan_wifi()
    connect_to_wifi()
    # Cleanup or make the data directory
    if os.path.isdir('/data'):
        entries = [f for f in os.path.listdir('/data') if os.path.isfile(os.path.join('/data', f))]
        entries = ((os.stat(path), path) for path in entries)
        # leave only regular files, insert creation date
        entries = ((stat[ST_CTIME], path)
                   for stat, path in entries if S_ISREG(stat[ST_MODE]))
        i = 0
        for cdate, path in sorted(entries):
            print(time.ctime(cdate), os.path.basename(path))
            i += 1
            if i > 3:
                os.remove(path)
    else:
        os.mkdir('/data/' + file_prefix)

    return board_led_task, controller_led_task


file_prefix = str(time.time())

# This is the main program
try:
    print("Starting")
    board_flash_sequence = FlashSequence()
    controller_flash_sequence = FlashSequence()
    (board_led_task, controller_led_task) = startup(board_flash_sequence, controller_flash_sequence)
    asyncio.run(main(board_led_task, controller_led_task, board_flash_sequence, controller_flash_sequence))
    print("done")
except Exception as e:
    print("Error:\n", str(e))
    print("Resetting mcu in 10 seconds")
    time.sleep(10)
    microcontroller.reset()
