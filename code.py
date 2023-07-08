# SPDX-FileCopyrightText: 2023 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import os
from time import monotonic, monotonic_ns, time

import socketpool
import wifi
import mdns
import board
import analogio

from adafruit_httpserver import Server, Request, Response, SSEResponse, GET


def scan_wifi_for(ssid: str) -> bool:
    """Scans for a specific ssid"""
    # TODO regex name - we'll scan for anything like say slot-car-network-*
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
        (x, y, z, a, (ip, port)) = temp_pool.getaddrinfo(host=hostname, port=80)  # port is required
        print("Found address:", ip)
    except Exception as e:
        print("Hostname", hostname, "not found", str(e))
        rc = False
    return rc


def uniqueify_hostname(hostname: str) -> str:
    """Looks for the hostname on the network. If found tries suffixes until it finds
    one free that it can use"""
    # TODO recurses forever if all colors used up!
    colors4 = ['yel', 'blu', 'whi', 'red']  # Three chars to cover the 10 char hostname bug
    # TODO more colors
    if look_for_host(hostname):  # Found, already taken, so need to suffix
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
    else:                              # hostname not found - use it
        pass
    return hostname


def connect_to_wifi():
    the_time = str(time())
    print("Time", the_time)  # 10 digits - bug in hostname setting, merges not replaces
    # the_time = (the_time[:14] + 'x') if len(the_time) > 14 else the_time
    wifi.radio.hostname = str(the_time)  # Set a garbage hostname to run search for other hosts
    print("Temp Hostname for scanning:", wifi.radio.hostname)
    # use my ip to find existing hostname

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


    # Look for this host on the network, use it if not found
    hostname = uniqueify_hostname("logger-yel")  # This name covers the 10 digit time string

    wifi.radio.stop_station()    # Discard temp connection

    print("Wifi connection:", wifi.radio.connected)
    print("Setting hostname to", hostname, "before reconnecting")

    wifi.radio.hostname = str(hostname)
    try:
        wifi.radio.connect(str(ssid), str(password))
    except ConnectionError as e:
        print("Unable to connect with default credentials", str(e))
        # TODO flash the red led
        # TODO wait/retry from the start after waiting for the network to be set up, note code will reload on its own


def advertize_service():
    try:
        print("mdns advert")
        mdns_server = mdns.Server(wifi.radio)
        mdns_server.hostname = wifi.radio.hostname
        mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)
        # (foo) = mdns_server.find(service_type="_http", protocol="_tcp")
        # print("MDNS", foo)
    except RuntimeError as e:
        print("MDNS setting failed:", str(e))


connect_to_wifi()
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)
advertize_service()


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
        mark = '0'
        if self._collected > 0:
            mark = '1'
            self._collected = 0
        with analogio.AnalogIn(board.GP26) as cI, \
                analogio.AnalogIn(board.GP27) as cV, \
                analogio.AnalogIn(board.GP28) as tV:
            # TODO add/subtract the zero calibration value
            self._response.send_event(
                f"{monotonic_ns()},{(cI.value * 3.3) / 65536},{(cV.value * 3.3) / 65536},{(tV.value * 3.3) / 65536},{mark}")
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

            let db;
            const DB_NAME = 'logger_db_' + Date.now(); // TODO one database a day?
            const OS_NAME = 'logger_os';
            
            function init() {

                var data = new google.visualization.DataTable();
                data.addColumn('number', 'Elapse');
                data.addColumn('number', 'Controller Current');
                data.addColumn('number', 'Controller Voltage');
                data.addColumn('number', 'Track Voltage');

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
                
                function initDb() {
                    const openRequest = window.indexedDB.open(DB_NAME, 1);
                    openRequest.addEventListener("error", () =>
                        console.error("Database failed to open")
                    );
                    openRequest.addEventListener("success", () => {
                        console.log("Database opened successfully");

                        // Store the opened database object in the db variable. This is used a lot below
                        db = openRequest.result;

                        // Run the displayData() function to display the notes already in the IDB
                        // displayData();
                    });
                    openRequest.addEventListener("upgradeneeded", (e) => {
                        // Grab a reference to the opened database
                        db = e.target.result;

                        // Create an objectStore in our database to store notes and a none auto-incrementing key
                        // An objectStore is similar to a 'table' in a relational database
                        const objectStore = db.createObjectStore(OS_NAME, {
                            keyPath: "ts",
                            autoIncrement: false,
                        });
                        // Define what data items the objectStore will contain
                        objectStore.createIndex("c_current", "c_current", { unique: false });
                        objectStore.createIndex("c_volts", "c_volts", { unique: false });
                        objectStore.createIndex("t_volts", "t_volts", { unique: false });
                        objectStore.createIndex("mark", "mark", { unique: false });
                        console.log("Database setup complete");
                    });
                }
                function addData(ts, c_current, c_volts, t_volts, mark) {
                    // prevent default - we don't want the form to submit in the conventional way
                    // e.preventDefault();
                    // console.log("adding", ts, c_current, c_volts, t_volts, mark);
                    // grab the values entered into the form fields and store them in an object ready for being inserted into the DB
                    const newItem = { ts: ts, c_current: c_current,
                                    c_volts: c_volts, t_volts: t_volts, mark: mark};

                    // open a read/write db transaction, ready for adding the data
                    const transaction = db.transaction([OS_NAME], "readwrite");

                    // call an object store that's already been added to the database
                    const objectStore = transaction.objectStore(OS_NAME);

                    // Make a request to add our newItem object to the object store
                    const addRequest = objectStore.add(newItem);

                    addRequest.addEventListener("success", () => {
                        // Clear the form, ready for adding the next entry
                        // titleInput.value = "";
                        // bodyInput.value = "";
                    });

                // Report on the success of the transaction completing, when everything is done
                    transaction.addEventListener("complete", () => {
                        console.log("Transaction completed: database modification finished.");

                        // update the display of data to show the newly added item, by running displayData() again.
                        // displayData();
                    });

                    transaction.addEventListener("error", () =>
                        console.log("Transaction not opened due to error")
                    );
                }
                function initializeEventSource() {
                    console.log("Opening eventsource connection");
                    const eventSource = new EventSource('/connect-client');
                    eventSource.onerror = onError;
                    // eventSource.addEventListener("data", onMessage);
                    // eventSource.addEventListener("mark", onMark);
                    eventSource.onmessage = onMessage;
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
                    // console.log("Update values", tok[0], tok[1], tok[2], tok[3], tok[4]);
                    if (data.getNumberOfRows() > 200) {
                        console.log("Garbage collect", data.getNumberOfRows(), 0, 100);
                        data.removeRows(0, 100);
                    }
                    //el = tok[0].substring(1);   // lop the first char off
                    // TODO handle the mark - only save data between marks?
                    data.addRow([parseInt(tok[0]),parseFloat(tok[1]),parseFloat(tok[2]),parseFloat(tok[3])]);
                    addData(tok[0], tok[1], tok[2], tok[3], tok[4]);
                }
                initDb();
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
        <div id="edit_data">
            <!-- Display the available databases and offer a/c/d/display -->
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
