import os
import mdns
import asyncio
import microcontroller
import rtc
import socketpool
import time
from time import monotonic
import adafruit_datetime
import wifi
import ssl
import adafruit_requests
import board
import digitalio
import storage
import analogio
import circuitpython_csv as csv

from adafruit_httpserver import Server, Request, Response, FileResponse, MIMETypes, GET, JSONResponse, SSEResponse

"""
Slot Car Data Logger
--------------------

This code runs a Pi Pico W that runs a (flat track) slot car data logger. The device comprises a simple circuit that
measures positive and negative voltage and current, and normalizes this to a 0 - 3.3v signal for input to the Pi Pico 
on its 3 ADC inputs.

The device intermediates between a slot car track and the controller and collects data about varying controller 
current and voltage and the (mostly fixed at ~12vDC) track voltage in real time from a slot car controller 
and track supply. 

The information is useful to a driver (the person operating the controller) so that they can improve their lap times. 
Therefore the data shall be fed back to them in near realtime and retrospectively, in a way that it can easily be 
disseminated and put to use.

This might say be a continuously scrolling line graph of three traces displayed in a web browser on a connected device.
It would obviously be helpful to maintain an archive of this data for later examination.

The device is standalone and has no knowledge about the track layout, however perhaps in some later release we could
arrange a way to input track layout data to make traces more meaningful. However raw plots are expected to show 
correlations that should make the car's track position  tthe time clear - for example when a car starts, it's expected
to draw maximum current and voltage.

A typical lap time is in the order of 4 - 6 seconds on a track that can have between 4 and 8 lanes. Lanes are 
color-coded by convention. Each lane could have a logger. A race can last between 5 and 15 minutes.

To collect a meaningful dataset the data shall be sampled say at 100mSec (1/10 sec) intervals (this might be adjusted 
to longer to lower the amount of collected data). Therefore in say a 15 minute session a single controller is 
capturing say 15 * 60 * 10 * 3 = 27,000 tuples of timestamp, value, tag. As a character string this might be 
say ~23 bytes e.g. 206656250000,0.012085,V  Total ~1/2 MByte

The design is (simplistically): read from ADC, write to sink. Where the sink could be:

 - Remotely connected (track) computer or personal laptop - not saving any data locally.
 - Local filesystem (given the volumes a single race might just be accommodated on "CIRCUITPY".
 - Both - where the accumulated data id polled from the filesystem in near realtime, and later downloaded in its 
   entirety.

Device Specifics
----------------

Channels:

GP18 - external LED, low = ON
GP22 - Push button
GP26/ADC0 - Current
GP27/ADC1 - Controller + output voltage to track and motor 
GP28/ADC2 - Track incoming + supply voltage

Note: Set GP18 to output drive strength 12mA, to minimise volt-drop in the micro (PADS_BANK0: GPIOx Registers) 

Note: Worth experimenting with the SMPS mode pin (WL_GPIO1) to find out which
setting (low or high) gives the least noise in the ADC readings (with
the little test programme I got around 10 decimal variation, of a 12 bit
value, in the current zero value)

Please choose a pin to use as a program loop time indicator,
toggles from one state to another each time round the loop.

The original intention for the push button was to calibrate the zero
current value (nominal 1/2 the micro 3V3 supply) with the black output
lead disconnected, but it could also be used to calibrate the voltage
signals by setting them to an exact 12.00V.

Design Notes
------------

There only a push button for input (unless and until we have BT) :-( so the device needs to make some assumptions
about the WiFi network.

Tracks don't often have WiFi - so assume the owner (someone) will create a personal hotspot with a conventional name 
like: "slot-car-network*" and a conventional password "sl0tc1r" Search for this - if it's not found blink a red led, 
but continue to log data locally.

Assume each logger needs a unique hostname. Without BT these need to be assigned algorithmically.
No real way to match lane to a controller color but it's sensible to use this scheme.
So the code needs to look for hostname clashes and uniqueify its own name by suffixing.  

With a network connection file(s) can be opened and the ADC inputs can be started, then the web server started to
serve up the collected data.


TODO:

Simplify the design to display values on a Web pages as they are read rather than trying queue and write them?
Use the async_button class https://circuitpython-async-button.readthedocs.io/en/latest/
File system logging
Run calibration when enter the state. 
How do we set a specific place to write the data? Use bonjour/zeroconf - hierarchy say? main one/personal
network partner based on a convention.

BT.
Better errors

Issues:

How to stream data out.

"""


def scan_wifi_for(ssid: str) -> bool:
    """Scans for a specific ssid"""
    # TODO regex name
    rc = False
    for network in wifi.radio.start_scanning_networks():
        if network.ssid == ssid:
            print("\t%s\t\tRSSI: %d\tChannel: %d" % (str(network.ssid, "utf-8"), network.rssi, network.channel))
            rc = True
            break
    wifi.radio.stop_scanning_networks()
    return rc


def look_for_host(hostname: str) -> bool:
    """Search for a specific hostname on the network"""
    rc = True
    print("Looking for hostname:", hostname)
    temp_pool = socketpool.SocketPool(wifi.radio)
    try:
        addrinfo = temp_pool.getaddrinfo(host=hostname, port=80)  # port is required
        print("Found address:", addrinfo)
    except:
        print("Hostname", hostname, "not found")
        rc = False
    return rc


the_time = str(time.time())
print("Time", the_time)  # 10 digits - bug in hostname setting, merges not replaces
# the_time = (the_time[:14] + 'x') if len(the_time) > 14 else the_time
wifi.radio.hostname = str(the_time)  # Set a garbage hostname to run search for other hosts
print("Temp Hostname:", wifi.radio.hostname)

ssid = os.getenv("CIRCUITPY_WIFI_SSID")  # We'll use a conventional SSID, say slot-car-logger
if not scan_wifi_for(ssid):
    print("Unable to find default network ssid: ", ssid)
else:
    print("Success: network", ssid, "found, connecting with default credentials.")

password = os.getenv("CIRCUITPY_WIFI_PASSWORD")  # We'll use a conventional password too, say sl0tc1r
try:
    wifi.radio.connect(str(ssid), str(password))
except ConnectionError:
    print("Unable to connect with default credentials")
    # TODO flash the red led
    # TODO wait/retry some time say for the network to be set up, note code will reload on its own


def uniqueify_hostname(hostname: str) -> str:
    """Looks for the hostname on the network. If found tries suffixes until it finds
    one free that it can use"""
    # TODO recurses forever if all colors used up!
    colors4 = ['yel', 'blu', 'whi', 'red']  # Three chars to cover the 10 char hostname bug
    # TODO more colors
    if look_for_host(hostname):  # Found, so need to suffix
        tokens = hostname.split("-")
        if len(tokens) > 1:
            color = tokens[1]
            print("Color suffix", color)
            if color == 'def':
                hostname = tokens[0] + "-" + colors4[0]
            else:
                for i, lane_color in enumerate(colors4):
                    print("lane color", lane_color)
                    if color == lane_color:
                        if i == colors4.count:
                            i = -1
                        hostname = tokens[0] + "-" + colors4[i + 1]
        else:
            # No prefix - add the first one
            hostname = hostname + "-" + colors4[0]
        hostname = uniqueify_hostname(hostname)
    else:
        pass
    return hostname


# Look for this host on the network, use it if not found
hostname = uniqueify_hostname("logger-def")  # This name covers the 10 digit time string

wifi.radio.stop_station()

print("Wifi connection:", wifi.radio.connected)
print("Setting hostname to", hostname, "before reconnecting")

wifi.radio.hostname = str(hostname)

try:
    wifi.radio.connect(str(ssid), str(password))
except ConnectionError as e:
    print("Unable to connect with default credentials", str(e))
    # TODO flash the red led
    # TODO wait/retry from the start after waiting for the network to be set up, note code will reload on its own

# TODO Set hostname in DNS - this fails Out of MDNS service slots
try:
    mdns_server = mdns.Server(wifi.radio)
    mdns_server.hostname = wifi.radio.hostname
    mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)
except RuntimeError as e:
    print("MDNS setting failed:", str(e))

MIMETypes.configure(
    default_to="text/plain",
    # Unregistering unnecessary MIME types can save memory
    keep_for=[".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico"],
    # Assume we'll stream csv back - for now
    register={".csv": "text/csv", },
)

pool = socketpool.SocketPool(wifi.radio)


def set_clock():
    """Set the clock from ntp server - the long way"""
    request = adafruit_requests.Session(pool, ssl.create_default_context())
    print("Getting current time from ntp server:")
    response = request.get("http://worldtimeapi.org/api/ip")
    time_data = response.json()
    tz_hour_offset = int(time_data['utc_offset'][0:3])
    tz_min_offset = int(time_data['utc_offset'][4:6])
    if tz_hour_offset < 0:
        tz_min_offset *= -1
    unixtime = int(time_data['unixtime'] + (tz_hour_offset * 60 * 60)) + (tz_min_offset * 60)
    print("Time date", time_data)
    print("URL time:", response.headers['date'])
    rtc.RTC().datetime = time.localtime(unixtime)  # create time struct and set RTC with it
    print("current datetime:", time.localtime())  # time.* now reflects current local time


set_clock()
# Start server
server = Server(pool, "/static", debug=True)


@server.route("/cpu-information", append_slash=True)
def cpu_information_handler(request: Request):
    """
    Return the current CPU temperature, frequency, and voltage as JSON.
    """

    cpu_data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }

    return JSONResponse(request, cpu_data)


@server.route("/data", GET)
def data(request: Request):
    """
    Serves the file /data/data.csv.
    """
    return FileResponse(request, "data.csv", "/data")


class ConnectedClient:
    def __init__(self, response: SSEResponse = None):
        self.response = response
        self.next_message = 0

    @property
    def ready(self):
        return self.response and self.next_message < monotonic()

    def send_message(self):
        self.response.send_event(f"CPU: {round(microcontroller.cpu.temperature, 2)}°C")
        self.next_message = monotonic() + 1


connected_client = ConnectedClient()

HTML_TEMPLATE = """
<html lang="en">
    <head>
        <title>Server-Sent Events Clients</title>
    </head>
    <body>
        <script>
            const eventSource = new EventSource('/connect-client');

            eventSource.onmessage = event => console.log('Event data:', event.data);
            eventSource.onerror = error => console.error('SSE error:', error);
        </script>
        <p>Hi there</p>
    </body>
</html>
"""


@server.route("/client", GET)
def client(request: Request):
    return Response(request, HTML_TEMPLATE, content_type="text/html")


@server.route("/connect-client", GET)
def connect_client(request: Request):
    response = SSEResponse(request)

    if connected_client.response is not None:
        connected_client.response.close()  # Close any existing connection
    connected_client.response = response

    return response


async def read_adc(pin: microcontroller.Pin, tag: str, writer):
    with analogio.AnalogIn(pin) as adc:
        while True:
            local_value = (adc.value * 3.3) / 65536
            # TODO add/subtract the zero calibration value
            print("Current time (GMT +1):", adafruit_datetime.datetime.now().isoformat())
            print("Adc value for tag", tag, "is", local_value, "at", time.monotonic_ns())
            # TODO Write it locally and over the connection, HOW???
            rec = [tag, time.monotonic_ns(), local_value]
            # writer.writerow(rec)
            await asyncio.sleep(0.1)  # 100mS


# Main coroutine
async def main():
    fp = None
    header = ['tag', 'time', 'value']
    writer = None
    """
    Leave this for the moment ...
    try:
        fp = open("/data/data1.csv", mode="w", encoding='utf-8')
        writer = csv.writer(fp)
        print("Writer:", writer)
        writer.writerow(header)
    except OSError as e:
        print("Error: unable to open and write header\n", str(e))
        print("Have you forgotten to remount the fs as writable?")
        print("Resetting mcu in 10 seconds")
        time.sleep(10)
        microcontroller.reset()
    """
    controller_current_task = asyncio.create_task(read_adc(board.GP26, 'I', writer))
    controller_voltage_task = asyncio.create_task(read_adc(board.GP27, 'V', writer))
    track_voltage_task = asyncio.create_task(read_adc(board.GP28, 'X', writer))
    await asyncio.gather(controller_current_task, controller_voltage_task, track_voltage_task)


# start the main coroutine - to collect data and listen for the button press
# asyncio.run(main())

server.serve_forever(str(wifi.radio.ipv4_address))

while True:
    try:
        # Do something useful in this section,
        # for example read a sensor and capture an average,
        # or a running total of the last 10 samples

        # Process any waiting requests
        server.poll()

        # If you want you can stop the server by calling server.stop() anywhere in your code
    except OSError as error:
        print(error)
        continue
