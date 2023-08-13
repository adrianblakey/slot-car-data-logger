# Copyright @ 2023 Adrian Blakey, All rights reserved.

from time import monotonic_ns

import board
import digitalio
from adafruit_debouncer import Debouncer
from adafruit_httpserver import (Server, Request, Response, FileResponse, MIMETypes, GET,
                                 JSONResponse, SSEResponse)
import socketpool
import mdns
import wifi
import microcontroller
import log
from calibration import Calibration
from connectedclient import ConnectedClient

if log.is_debug:
    debug = True
else:
    debug = False

ID = "Slot Car Data Logger V1.0"
GIT = "https://github.com/adrianblakey/slot-car-data-logger"


def __advertise_service():
    """ Advertise the service to mdns """
    try:
        if log.is_debug:
            log.logger.debug("MDNS advertisement")
        mdns_server = mdns.Server(wifi.radio)
        mdns_server.hostname = wifi.radio.hostname
        mdns_server.instance_name = 'Slot car data logger'
    #    mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)
    except RuntimeError as e:
        if log.is_debug:
            log.logger.debug("MDNS setting failed: %s", str(e))


connected_client: ConnectedClient = ConnectedClient()
pool = socketpool.SocketPool(wifi.radio)
server: Server = Server(pool, debug=debug, root_path='/static')


def run(calibration: Calibration):
    global connected_client
    connected_client.calibration = calibration
    global server
    if log.is_debug:
        log.logger.debug("%s Advertise service", __file__)
    __advertise_service()
    if log.is_debug:
        log.logger.debug("%s Start server", __file__)
    MIMETypes.configure(default_to="text/plain",
                        keep_for=[".html", ".css", ".js", ".ico"])
    server.start(str(wifi.radio.ipv4_address))
    # [flash_led(yellow_led) for _ in range(5)]
    pin = digitalio.DigitalInOut(board.GP22)
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP
    button = Debouncer(pin)
    while True:
        pool_result = server.poll()
        button.update()
        if button.fell:
            if log.is_debug:
                log.logger.debug('yellow button Just pressed')
            connected_client.collected = monotonic_ns()
        elif button.rose:
            if log.is_debug:
                log.logger.debug('yellow button Just released')
        else:
            pass
        try:
            if connected_client.ready:
                connected_client.send_message()
        except OSError as e:
            log.logger.error("%s Exception in send_message %s", __file__, e)
            pass


@server.route("/cpu-information", append_slash=True)
def cpu_information_handler(request: Request):
    """
    Return the current CPU temperature, frequ           ency, and voltage as JSON.
    """

    cpu_data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }

    return JSONResponse(request, cpu_data)


HTML_TEMPLATE = """
<html lang="en">
    <head>
        <style>
        chart_wrap {
            position: relative;
            padding-bottom: 100%;
            height: 0;
            overflow:hidden;
        }
        linechart_material {
            position: absolute;
            top: 0;
            left: 0;
            width:100%;
            height:600px;
        }
        </style>
        <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
        <script type="text/javascript" src="js/app.js"></script>
        <title>Server-Sent Events Clients</title>
    </head>
    <body>
        <div id="chart_wrap">
            <div id="linechart_material" style="width: auto; height: 600px"></div>
        </div>
        <div id="databases_wrap">
            <div id="databases" style="width: auto">
            <!-- TODO put this in its own page -->
            </div>
        </div>
    </body>
</html>
"""

MY_ID = """
<html lang="en">
    <head>
        <title>My ID</title>
    </head>
    <body>
    <h1>""" + ID + """</h1>
    Hostname: """ + wifi.radio.hostname + """<br>
    Ip: """ + str(wifi.radio.ipv4_address) + """<br>
    Git: <a href='""" + GIT + """'>""" + GIT + """</a><br>
    </body>
</html>
"""


@server.route("/js/app.js")
def home(request: Request) -> Response:
    return FileResponse(request, "app.js", "/js")


@server.route("/js/chart.min.js")
def home(request: Request) -> Response:
    return FileResponse(request, "chart.min.js", "/js")


@server.route("/id", GET)
def client(request: Request) -> Response:
    return Response(request, MY_ID, content_type="text/html")


@server.route("/client", GET)
def client(request: Request) -> Response:
    return Response(request, HTML_TEMPLATE, content_type="text/html")


@server.route("/connect-client", GET)
def connect_client(request: Request) -> Response:
    global connected_client
    response = SSEResponse(request)
    try:
        if connected_client.response is not None:
            connected_client.response.close()  # Close any existing connection
    except OSError as e:
        pass
    connected_client.response = response
    return response
