
import os
import log
import analogio
import board
import wifi
from time import time, monotonic
import tune
import digitalio
from adafruit_debouncer import Debouncer
import socketpool

from led import Led
from ledcontrol import LedControl
from track import Track


if log.is_debug:
    debug = True
else:
    debug = False


def flash_start(red_led: Led, yellow_led: Led, green_led: Led):
    if log.is_debug:
        log.logger.debug("%s Running flash start", __file__)
    tune.START_UP.play()
    if log.is_debug:
        log.logger.debug("%s Flash leds", __file__)
    red_led.run()
    yellow_led.run()
    green_led.run()


def calibrate_current() -> float:
    """ Measure the current 10 times and average """
    with analogio.AnalogIn(board.GP26) as cI:
        i = 0
        count: float = 0.0
        while i < 10:
            count += (cI.value * 3.3) / 65536
            i += 1
        return count / 10


def _scan_wifi_for(ssid: str) -> bool:
    """ Scans for a specific ssid """
    rc = False
    for network in wifi.radio.start_scanning_networks():
        if log.is_debug:
            log.logger.debug("%s %s\tRSSI: %d\tChannel: %d", __file__, network.ssid, network.rssi, network.channel)
        if network.ssid == ssid:
            if log.is_debug:
                log.logger.debug("%s Found matching WiFi network:\t%s\tRSSI: %d\tChannel: %d", __file__,
                                 network.ssid, network.rssi, network.channel)
            rc = True
            break
    wifi.radio.stop_scanning_networks()
    return rc


def connect_to_wifi() -> (str, str):
    """ Make a temp connection to the WiFi network
        Throws Runtime - give up ... """
    wifi.radio.hostname = str(time())  # Set a garbage hostname to run search for other hosts
    if log.is_debug:
        log.logger.debug("%s Temp Hostname for scanning: %s", __file__, wifi.radio.hostname)
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")  # We'll use a conventional SSID, say slot-car-logger
    if not _scan_wifi_for(ssid):
        if log.is_debug:
            log.logger.debug("%s Unable to find default network ssid: %s", __file__, ssid)
        raise RuntimeError('No such ssid ' + ssid)
    else:
        if log.is_debug:
            log.logger.debug("%s Success: network %s found, connecting with default credentials.", __file__, ssid)

    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")  # We'll use a conventional password too, say sl0tc1r
    try:
        wifi.radio.connect(str(ssid), str(password))
    except ConnectionError:
        if log.is_debug:
            log.logger.debug("%s Unable to connect with default credentials", __file__)
        raise RuntimeError('Bad WiFi password')
    return ssid, password


def __flash_led(led: Led) -> None:
    ledcontrol = led.led_control
    ledcontrol.reps = 1
    ledcontrol.state = 'flash'
    ledcontrol.on_time = .2
    ledcontrol.off_time = .2
    led.run()


def _capture_yellow(yellow_debouncer: Debouncer, minimum: int, maximum: int,
                    red_led: Led, yellow_led: Led,
                    number: int = 0, tick: int = 0, start: float = 0.0) -> (bool, int, int, float):
    if not log.is_debug:
        log.logger.debug('%s capture_yellow min: %s max: %s number: %s tick: %s start: %4.2f',
                         __file__, minimum, maximum, number, tick, start)
    tick += 1
    if tick == 50000:
        tune.REMINDER.play()
        tick = 0
    if yellow_debouncer.fell:
        start = monotonic()
        tune.INPUT.play()  # Confirmation "click"
    elif yellow_debouncer.rose:
        elapse = monotonic() - start
        start = 0.0
        if log.is_debug:
            log.logger.debug('%s yellow button released, elapse: %4.4f', __file__,
                             elapse)
        if elapse <= .5:    # Short press < .5 sec, good count
            number += 1
            if log.is_debug:
                log.logger.debug('%s Short press, count: %s', __file__, number)
        else:               # Long press, leave if in range
            if log.is_debug:
                log.logger.debug("%s Long press, count: %s leave with the number if >= min %s <= max %s", __file__,
                                 number, minimum, maximum)
            if minimum <= number <= maximum:
                [tune.FEEDBACK.play() for _ in range(number)]  # confirm with beeps
                __flash_led(yellow_led)
                return True, number, tick, start
            else:
                if number > maximum:
                    number = 0
                __flash_led(red_led)
                tune.HI_LO.play()          # Keep inputting, less than min
    else:
        pass
    return False, number, tick, start


def input_number(red_led: Led, yellow_led: Led,
                 minimum: int, maximum: int) -> int:
    """ Press yellow button short press to increment, and long press to leave
        Black button to restart input """
    tune.INPUT_PROMPT.play()
    with digitalio.DigitalInOut(board.GP16) as black_pin:
        black_pin.direction = digitalio.Direction.INPUT
        black_pin.pull = digitalio.Pull.UP
        black_debouncer = Debouncer(black_pin)
        with digitalio.DigitalInOut(board.GP22) as yellow_pin:
            yellow_pin.direction = digitalio.Direction.INPUT
            yellow_pin.pull = digitalio.Pull.UP
            yellow_debouncer = Debouncer(yellow_pin)
            number = 0
            tick = 0
            start = 0.0
            while True:
                black_debouncer.update()
                yellow_debouncer.update()
                if black_debouncer.fell:
                    if log.is_debug:
                        log.logger.debug('%s black button pressed', __file__)
                    tune.INPUT.play()
                elif black_debouncer.rose:     # Go back/reset
                    if log.is_debug:
                        log.logger.debug('%s black button released', __file__)
                    rc, number, tick, start = _capture_yellow(yellow_debouncer, minimum, maximum,
                                                              red_led, yellow_led,
                                                              number=0, tick=0, start=0.0)
                    if rc:
                        return number
                else:
                    rc, number, tick, start = _capture_yellow(yellow_debouncer, minimum, maximum,
                                                              red_led, yellow_led,
                                                              number, tick, start)
                    if rc:
                        return number


def _look_for_host(hostname: str) -> str:
    """ Search for a specific hostname on the network """
    ip = None
    if log.is_debug:
        log.logger.debug("Looking for hostname: %s", hostname)
    temp_pool = socketpool.SocketPool(wifi.radio)
    try:
        [(family, socket_type, socket_protocol, flags, (ip, port))] = temp_pool.getaddrinfo(host=hostname,
                                                                                            port=80)  # port is required
        if log.is_debug:
            log.logger.debug("Found address: %s", ip)
    except OSError as ex:
        if log.is_debug:
            log.logger.debug("Hostname: %s not found ex: %s type: %s", hostname, ex, type(ex))
        rc = False
    return ip


def _uniqueify_hostname(hostname: str, track: Track) -> str:
    """ Looks for the hostname on the network. If not found tries suffixes until it finds
    one free that it can use """
    if log.is_debug:
        log.logger.debug('%s uniqueify_hostname() %s', __file__, hostname)
    # TODO recurses forever if all colors used up!
    ip = _look_for_host(hostname)
    if ip:  # found a match
        if str(ip) == str(wifi.radio.ipv4_address):  # If the IP address matches my hostname then reuse it
            if log.is_debug:
                log.logger.debug('ip: %s matches hostname: %s returning this hostname', ip, hostname)
            return hostname
        else:
            if log.is_debug:
                log.logger.debug('ip: %s does NOT match wifi ip: %s return hostname %s', ip, wifi.radio.ipv4_address, hostname)
        tokens = hostname.split("-")
        if len(tokens) > 1:
            color = tokens[1]
            if log.is_debug:
                log.logger.debug("%s Color suffix %s", __file__, color)
            for i, lane_color in enumerate(Track.TRACK_LANES[track.number_of_lanes]):  # Find the next color
                if log.is_debug:
                    log.logger.debug("%s lane color %s", __file__, lane_color)
                if color == lane_color:  # Match my current color - which is taken
                    if i == len(Track.TRACK_LANES[track.number_of_lanes]) - 1:  # Last one match - so it resets
                        i = -1
                    lane_colors = Track.TRACK_LANES[track.number_of_lanes]
                    hostname = tokens[0] + "-" + lane_colors[i + 1]
                    break
        else:
            # No suffix - pick the first one
            lane_colors = Track.TRACK_LANES[track.number_of_lanes]
            hostname = hostname + "-" + lane_colors[0]
        hostname = _uniqueify_hostname(hostname)
    else:  # hostname not found - use it
        pass
    return hostname


def connect_to_wifi_as_me(track: Track, ssid: str, password: str):
    hostname = _uniqueify_hostname("logger-" + track.my_lane_color, track)
    wifi.radio.stop_station()  # Discard temp connection

    if log.is_debug:
        log.logger.debug("Wifi connection: %s", wifi.radio.connected)
        log.logger.debug("Setting hostname to: %s before reconnecting", hostname)

    wifi.radio.hostname = str(hostname)
    try:
        wifi.radio.connect(str(ssid), str(password))
    except ConnectionError as e:
        # led_on(red_led)
        if log.is_debug:
            log.logger.debug("%s Unable to connect with default credentials %s", __file__, e)
        raise RuntimeError('Unable to connect to WiFi with:', ssid, password)

