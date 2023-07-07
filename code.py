# SPDX-FileCopyrightText: 2023 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

from time import monotonic, monotonic_ns,

import microcontroller
import socketpool
import time
import wifi
import board
import analogio
import adafruit_datetime

from adafruit_httpserver import Server, Request, Response, SSEResponse, GET


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


class ConnectedClient:
    def __init__(self, response: SSEResponse = None):
        self._response = response
        self._next_message = 0
        self._collected = 0

    @property
    def response(self) -> SSEResponse:
        return self._response

    @response.setter
    def response(self, response: int):
        self._response = response

    @property
    def next_message(self) -> int:
        return self._next_message

    @next_message.setter
    def next_message(self, value: int):
        self._next_message = value

    @property
    def ready(self):
        return self._response and self._next_message < monotonic_ns() + 5000

    @property
    def collected(self):
        return self._collected

    @collected.setter
    def collected(self, value: int):
        self._collected = value

    def send_message(self):
        # print("Current time (GMT +1):", adafruit_datetime.datetime.now().isoformat())
        if self._collected > 0:
            self._response.send_event(f"{self._collected}", event='mark')
            self._collected = 0
        with analogio.AnalogIn(board.GP26) as cI, \
                analogio.AnalogIn(board.GP27) as cV, \
                analogio.AnalogIn(board.GP28) as tV:
            # TODO add/subtract the zero calibration value
            self._response.send_event(
                f"{monotonic_ns()},{(cI.value * 3.3) / 65536},{(cV.value * 3.3) / 65536},{(tV.value * 3.3) / 65536}",
                event='data')
        self._next_message = monotonic_ns() + 5000


connected_client = ConnectedClient()

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
        height:500px;
        }
        </style>
        <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
        <script type="text/javascript">
            google.charts.load('current', {'packages':['line']});
            google.charts.setOnLoadCallback(init);

            function init() {

                var data = new google.visualization.DataTable();
                data.addColumn('number', 'Elapse');
                data.addColumn('number', 'Controller Voltage');
                data.addColumn('number', 'Controller Current');
                data.addColumn('number', 'Track Voltage');
                // data.addRow([70000000000000,1.0,0.01,0.01]);

                var materialOptions = {
                    chart: {
                        title: 'Controller Voltage and Current, Track Voltage'
                    },
                    width: '100%',
                    height: 500,
                    series: {
                        // Gives each series an axis name that matches the Y-axis below.
                        0: {axis: 'Voltage'},
                        1: {axis: 'Current'}
                    },
                    axes: {
                        // Adds labels to each axis; they don't have to match the axis names.
                        y: {
                            Voltage: {label: 'Voltage (vDC)'},
                            Current: {label: 'Current (mAmps)'}
                        }
                    },
                    animation: {
                        startup: true,
                        duration: 20,
                        easing: 'linear'
                    }
                };
      
                var chart = new google.charts.Line(document.getElementById('linechart_material'));
                
                function initializeEventSource() {
                    console.log("Opening eventsource connection");
                    const eventSource = new EventSource('/connect-client');
                    eventSource.onerror = onError;
                    eventSource.addEventListener("data", onMessage);
                    eventSource.addEventListener("mark", onMark);
                    // eventSource.onmessage = onMessage;
                    eventSource.onopen = onOpen;
                }
                var redraw = 0
                var msgCt = 0
                function onOpen(event) {
                    console.log("Starting connection to eventsource.");
                }
                function onError(event) {
                    console.log("SSE error", event);
                    if (event.readyState === EventSource.CLOSED) {
                        console.log('Connection was closed', event);
                    } else {
                        console.log('An unknown error occurred:', event);
                    }
                }
                function onMark(event) {
                    console.log("received mark event", event.data);
                    // todo insert this into the graph - result of button marker
                }
                function onMessage(event) {
                    // console.log("EventSource message received:", event);
                    updateValues(event.data);
                    // redraw every 10
                    redraw++;
                    if (msgCt == 0 || redraw == 10) {
                        console.log("redraw", msgCt, redraw)
                        chart.draw(data, google.charts.Line.convertOptions(materialOptions));
                        redraw = 0;
                    }
                    msgCt++;
                }
                function updateValues(edata) {
                    tok = edata.split(',');
                    console.log("Update values", tok[0], tok[1], tok[2], tok[3]);
                    if (data.getNumberOfRows() > 200) {
                        console.log("Garbage collect", data.getNumberOfRows(), 0, 100);
                        data.removeRows(0, 100);
                    }
                    //el = tok[0].substring(1);   // lop the first char off
                    data.addRow([parseInt(tok[0]),parseFloat(tok[1]),parseFloat(tok[2]),parseFloat(tok[3])]);
                } 
                initializeEventSource();
                chart.draw(data, google.charts.Line.convertOptions(materialOptions));
                
            } // end init
      
        </script>
        <title>Server-Sent Events Clients</title>
    </head>
    <body>
        <div id="chart_wrap">
            <div id="linechart_material" style="width: 900px; height: 500px"></div>
        </div>
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


server.start(str(wifi.radio.ipv4_address))
while True:
    pool_result = server.poll()

    if connected_client.ready:
        lt = monotonic_ns()
        if lt % 5 == 0:  # simulate a button press
            connected_client.collected = lt
        connected_client.send_message()
