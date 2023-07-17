# Copyright @ 2023 Adrian Blakey, All rights reserved.

"""

Slot car data logger firmware.

Channels:

  GP18      - External LED, low = ON
  GP22      - Push button
  GP26/ADC0 - Current drawn by the motor through the hand controller
  GP27/ADC1 - Output voltage to track and motor from the hand controller
  GP28/ADC2 - Track incoming supply voltag

TODO
Button press
Logging
Write logs to local filesystem - web interface to pull them
Flash the led

"""
import os
from time import monotonic, monotonic_ns, time, sleep

import socketpool
import wifi
import mdns
import board
import analogio
import microcontroller
import digitalio
from adafruit_debouncer import Debouncer

from adafruit_httpserver import Server, Request, Response, FileResponse, MIMETypes, GET, JSONResponse, SSEResponse

debug = True
LANE_COLORS = ['bla', 'pur', 'yel', 'blu', 'ora', 'gre', 'whi', 'red']
ID = "Slot Car Data Logger V1.0"
GIT = "https://github.com/adrianblakey/slot-car-data-logger"

led = digitalio.DigitalInOut(board.GP18)
led.direction = digitalio.Direction.OUTPUT
led.value = True

board_led = digitalio.DigitalInOut(board.LED)
board_led.direction = digitalio.Direction.OUTPUT
board_led.value = False

def flash_led(on_time: float) -> None:
    led.value = False
    sleep(on_time)
    led.value = True


def led_on() -> None:
    led.value = False


def led_off() -> None:
    led.value = True


def scan_wifi_for(ssid: str) -> bool:
    """Scans for a specific ssid"""
    rc = False
    for network in wifi.radio.start_scanning_networks():
        if debug:
            print("DEBUG - %s\tRSSI: %d\tChannel: %d" % (
                str(network.ssid, "utf-8"), network.rssi, network.channel))
        if network.ssid == ssid:
            if debug:
                print("DEBUG - Found matching WiFi network:\t%s\tRSSI: %d\tChannel: %d" % (
                    str(network.ssid, "utf-8"), network.rssi, network.channel))
            rc = True
            break
    wifi.radio.stop_scanning_networks()
    return rc


def look_for_host(hostname: str) -> str:
    """Search for a specific hostname on the network"""
    ip = None
    if debug:
        print("DEBUG - Looking for hostname:", hostname)
    temp_pool = socketpool.SocketPool(wifi.radio)
    try:
        [(family, socket_type, socket_protocol, flags, (ip, port))] = temp_pool.getaddrinfo(host=hostname,
                                                                                            port=80)  # port is required
        if debug:
            print("DEBUG - Found address:", ip)
    except OSError as e:
        if debug:
            print("DEBUG - Hostname", hostname, "not found", str(e), type(e))
        rc = False
    return ip


def uniqueify_hostname(hostname: str) -> str:
    """Looks for the hostname on the network. If found tries suffixes until it finds
    one free that it can use"""
    if debug:
        print('DEBUG - uniqueify_hostname()', hostname)
    # TODO recurses forever if all colors used up!
    # Three chars to cover the 10 char hostname bug
    ip = look_for_host(hostname)
    if ip:  # found a match
        if ip == wifi.radio.ipv4_address:  # If the IP address matches my hostname then reuse it
            return hostname
        tokens = hostname.split("-")
        if len(tokens) > 1:
            color = tokens[1]
            if debug:
                print("DEBUG - Color suffix", color)
            for i, lane_color in enumerate(LANE_COLORS):  # Find the next color
                if debug:
                    print("DEBUG - lane color", lane_color)
                if color == lane_color:  # Match my current color - which is taken
                    if i == len(LANE_COLORS) - 1:  # Last one match - so it resets
                        i = -1
                    hostname = tokens[0] + "-" + LANE_COLORS[i + 1]
                    break
        else:
            # No suffix - pick the first one
            hostname = hostname + "-" + LANE_COLORS[0]
        hostname = uniqueify_hostname(hostname)
    else:  # hostname not found - use it
        pass
    return hostname


def connect_to_wifi():
    the_time = str(time())
    wifi.radio.hostname = str(the_time)  # Set a garbage hostname to run search for other hosts
    if debug:
        print("DEBUG - Temp Hostname for scanning:", wifi.radio.hostname)
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")  # We'll use a conventional SSID, say slot-car-logger
    if not scan_wifi_for(ssid):
        led_on()
        if debug:
            print("DEBUG - Unable to find default network ssid:", ssid)
        raise RuntimeError('No such ssid ' + ssid)
    else:
        if debug:
            print("DEBUG - Success: network", ssid, "found, connecting with default credentials.")

    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")  # We'll use a conventional password too, say sl0tc1r
    try:
        wifi.radio.connect(str(ssid), str(password))
    except ConnectionError:
        led_on()
        if debug:
            print("DEBUG - Unable to connect with default credentials")
        raise RuntimeError('Bad WiFi password')

    hostname = uniqueify_hostname("logger-bla")  # This name covers the 10 digit time string bug
    wifi.radio.stop_station()  # Discard temp connection

    if debug:
        print("DEBUG - Wifi connection:", wifi.radio.connected)
        print("DEBUG - Setting hostname to", hostname, "before reconnecting")

    wifi.radio.hostname = str(hostname)
    try:
        wifi.radio.connect(str(ssid), str(password))
    except ConnectionError as e:
        if debug:
            print("DEBUG - Unable to connect with default credentials", str(e))
        # TODO flash the red led
        # TODO wait/retry from the start after waiting for the network to be set up, note code will reload on its own


def advertise_service():
    try:
        if debug:
            print("DEBUG - MDNS advertisement")
        mdns_server = mdns.Server(wifi.radio)
        mdns_server.hostname = wifi.radio.hostname
        mdns_server.instance_name = 'Slot car data logger'
    #    mdns_server.advertise_service(service_type="_httpslots", protocol="_tcp", port=80)
    except RuntimeError as e:
        if debug:
            print("DEBUG - MDNS setting failed:", str(e))


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
        return self._response and self._next_message < monotonic() + 1

    @property
    def collected(self):
        return self._collected

    @collected.setter
    def collected(self, value: int):
        self._collected = value

    def send_message(self):
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
        self._next_message = monotonic() + 1
        board_led.value = not board_led.value


flash_led(0.5)
connect_to_wifi()
pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=debug, root_path='/static')
advertise_service()
server.start(str(wifi.radio.ipv4_address))

connected_client = ConnectedClient()


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
        <script type="text/javascript" src="js/test.js"></script>
        <script type="text/javascript">
            google.charts.load('current', {'packages':['line']});
            google.charts.setOnLoadCallback(init);
            test();
            let db;
            let INDEXED_DB_SUPPORTED = false;
            let graphDb;
            const DB_NAME = 'logger_db_';
            let db_name;
            const OS_NAME = 'logger_os';

            const getBrowserName = () => {
                let browserInfo = navigator.userAgent;
                let browser;
                if (browserInfo.includes('Opera') || browserInfo.includes('Opr')) {
                    browser = 'Opera';
                } else if (browserInfo.includes('Edg')) {
                    browser = 'Edge';
                } else if (browserInfo.includes('Chrome')) {
                    browser = 'Chrome';
                } else if (browserInfo.includes('Safari')) {
                    browser = 'Safari';
                } else if (browserInfo.includes('Firefox')) {
                    browser = 'Firefox'
                } else {
                    browser = 'unknown'
                }
                return browser;
            }


            function init() {

                var data = new google.visualization.DataTable();
                data.addColumn('number', 'Elapse');
                data.addColumn('number', 'Controller Current');
                data.addColumn('number', 'Controller Voltage');
                data.addColumn('number', 'Track Voltage');

                var materialOptions = {
                    title: 'Data Logger',
                    titlePosition: 'out',
                    titleTextStyle: {fontSize: 28, bold: true},
                    legend: { position: 'out' },
                    width: 1000,
                    height: 600,
                    hAxis: {
                        gridlines: {color: 'grey', minSpacing: 40, multiple: 1, interval: [1], count: 10},
                        minorGridlines: {color: 'violet', interval: [1]},
                        baseLine: 0, 
                        title: 'Elapse (sec)', 
                        textStyle: {color: 'black', bold: true},
                        format: '###.###',
                        viewWindow: {max: 10, min: 0}
                    },
                    series: {
                        0: {color: 'red', lineWidth: 2, targetAxisIndex: 0},
                        1: {color: 'blue', lineWidth: 2, targetAxisIndex: 1},
                        2: {color: 'lightblue', lineWidth: 2, targetAxisIndex: 1}
                    },
                    vAxes: {
                        0: {
                            title:'Current (A)',
                            textStyle: {color: 'red', bold: true},
                            viewWindow: {min: -20, max: 20}
                        },
                        1: {
                            title:'Voltage (V)',
                            textStyle: {color: 'blue', bold: true},
                            viewWindow: {min: -15, max: 15}
                        }
                    },
                    animation: {
                        startup: true,
                        duration: 20,
                        easing: 'linear'
                    }
                };

                var chart = new google.charts.Line(document.getElementById('linechart_material'));

                function deleteADatabase(dbName) {
                    console.log("Deleting database:", dbName);
                    const DBDeleteRequest = window.indexedDB.deleteDatabase(dbName);

                    DBDeleteRequest.onerror = (event) => {
                        console.error("Error deleting database.");
                    };

                    DBDeleteRequest.onsuccess = (event) => {
                        console.log("Database deleted successfully");
                    };
                }

                function initDb() {
                    console.log("initDB");
                    const promise = indexedDB.databases();
                    promise.then((databases) => {
                        var div = document.getElementById('databases');
                        var h2 = document.createElement('h2');
                        h2.textContent = 'Databases in the Browser';
                        div.appendChild(h2);
                        var ul = document.createElement('ul');
                        div.appendChild(ul);
                        for (var i = 0; i < databases.length; i++) {
                            var li = document.createElement('li');
                            var delButton = document.createElement('button');
                            delButton.innerText = 'delete';
                            delButton.onclick = function() { // remove list item here
                                deleteADatabase(this.parentElement.id);
                                this.parentElement.remove();
                            };
                            var disButton = document.createElement('button');
                            disButton.innerText = 'graph';
                            disButton.onclick = function() { // graph the database
                                // TODO graph it
                            };
                            li.appendChild(document.createTextNode(databases[i].name));
                            li.setAttribute("id", databases[i].name);
                            li.appendChild(delButton);
                            li.appendChild(disButton);
                            ul.appendChild(li);
                            console.log(databases[i].name, databases[i].version);
                            // deleteADatabase(databases[i].name);
                        }
                    });

                    let now = new Date();
                    // New db every session
                    db_name = DB_NAME + now.getFullYear() + now.getMonth() + now.getDate() + now.getHours() + now.getMinutes() + now.getSeconds();
                    const openRequest = window.indexedDB.open(db_name, 1);
                    openRequest.addEventListener("error", () =>
                        console.error("Database", db_name, "failed to open")
                    );
                    openRequest.addEventListener("success", () => {
                        console.log("Database", db_name ,"opened successfully");

                        // Store the opened database object in the db variable. This is used a lot below
                        db = openRequest.result;
                        // Display the list of databases in the form
                        // displayData();
                    });
                    function createObjectStore() {
                        console.log("Create object store", OS_NAME);
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
                        console.log("Database setup complete");
                    }
                    openRequest.addEventListener("upgradeneeded", (e) => {
                        // Grab a reference to the opened database
                        console.log("Upgrade needed");
                        db = e.target.result;
                        createObjectStore();
                    });
                }
                function addData(ts, c_current, c_volts, t_volts) {
                    // Adds a row to the database
                    // prevent default - we don't want the form to submit in the conventional way
                    // e.preventDefault();
                    // console.log("adding", ts, c_current, c_volts, t_volts, mark);
                    // grab the values entered into the form fields and store them in an object ready for being inserted into the DB
                    const newItem = { ts: ts, c_current: c_current,
                                    c_volts: c_volts, t_volts: t_volts};

                    // open a read/write db transaction, ready for adding the data
                    const transaction = db.transaction([OS_NAME], "readwrite");

                    // call an object store that's already been added to the database
                    const objectStore = transaction.objectStore(OS_NAME);

                    // Make a request to add our newItem object to the object store
                    const addRequest = objectStore.add(newItem);

                    addRequest.addEventListener("success", () => {
                        console.log("Data added successfully");
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

                var saveData = false;         // cache data in database or not
                firstElapseTime = 0
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
                    tok = event.data.split(',');
                    console.log("Update values", tok[0], tok[1], tok[2], tok[3], tok[4]);
                    xVal = parseInt(tok[0]);                  // elapse time as an int
                    rowCount = data.getNumberOfRows();
                    if (rowCount == 0) {  // before we add anything, save the first e time
                        console.log('First firstElapseTime is:', tok[0]);
                        firstElapseTime = xVal;
                    }
                    // Handle the mark - only save data between marks?
                    if (INDEXED_DB_SUPPORTED) {
                        if (tok[4] == '1') {
                            if (saveData) {
                                console.log("mark found stop saving data");
                                materialOptions.series[0].lineWidth = 1;
                                materialOptions.series[1].lineWidth = 1;
                                materialOptions.series[2].lineWidth = 1;
                                hAxis.title = 'Elapse (sec)';
                                hAxis.textStyle.color = 'black';
                                saveData = false;    
                            } else {
                                console.log("mark found start saving data");
                                materialOptions.series[0].lineWidth = 10;
                                materialOptions.series[1].lineWidth = 10;
                                materialOptions.series[2].lineWidth = 10;
                                hAxis.title = 'Elapse (sec) - saving data in: ' + db_name;
                                hAxis.textStyle.color = 'red';
                                saveData = true;
                            }
                        }
                        if (saveData) {
                            console.log('Saving data to database');
                            addData(tok[0], tok[1], tok[2], tok[3]);
                        }
                    }
                    console.log('Add row to chart');
                    eTime = (xVal - firstElapseTime) / 1000000000; // scale it to n.xxxxx seconds
                    if (eTime < 0.0) {    // The clock reset so reestablish the zero
                        firstElapseTime = xVal;
                        eTime = 0.0;
                    }
                    console.log('Normalized etime', eTime);
                    data.addRow([parseFloat(eTime),parseFloat(tok[1]),parseFloat(tok[2]),parseFloat(tok[3])]);

                    // console.log('Max, min, etime', materialOptions.hAxis.viewWindow.max, materialOptions.hAxis.viewWindow.min, eTime);
                    latestX = Math.ceil(eTime);  // Round up
                    console.log('if eTime ceil is bigger than max, move vw', latestX, materialOptions.hAxis.viewWindow.min, materialOptions.hAxis.viewWindow.max);
                    if (latestX >= materialOptions.hAxis.viewWindow.max) {       // step the vw forward in front of the value
                        materialOptions.hAxis.viewWindow.max++;
                        materialOptions.hAxis.viewWindow.min++;
                        console.log('Min, max, rowct', materialOptions.hAxis.viewWindow.min, materialOptions.hAxis.viewWindow.max, data.getNumberOfRows());
                        data.removeRows(0, Math.floor(rowCount / 10) - 1);           // garbage collect
                    }
                    // console.log("draw", materialOptions);
                    chart.draw(data, google.charts.Line.convertOptions(materialOptions));
                }
                function displayData() {
                // Open our object store and then get a cursor - which iterates through all the
                // different data items in the store
                    const objectStore = db.transaction("notes_os").objectStore("notes_os");
                    objectStore.openCursor().addEventListener("success", (e) => {
                    // Get a reference to the cursor
                        var data = new google.visualization.DataTable();
                        data.addColumn('number', 'Elapse');
                        data.addColumn('number', 'Controller Current');
                        data.addColumn('number', 'Controller Voltage');
                        data.addColumn('number', 'Track Voltage');
                        const cursor = e.target.result;

                        // If there is still another data item to iterate through, keep running this code
                        if (cursor) {

                            data.addRow([parseFloat(cursor.value.ts),
                                parseFloat(cursor.value.c_current),
                                parseFloat(cursor.value.c_volts),
                                parseFloat(cursor.value.t_volts)]);
                            // Iterate to the next item in the cursor
                            cursor.continue();
                        } 
                        console.log("All data added to chart");
                    });
                }
                function graphData(dbName) {
                    // Open the database readonly
                    const openRequest = window.indexedDB.open(dbName, 1);
                    openRequest.addEventListener("error", () =>
                        console.error("Database", dbName, "failed to open")
                    );
                    openRequest.addEventListener("success", () => {
                        console.log("Database", dbName ,"opened successfully");

                        // Store the opened database object in the db variable. This is used a lot below
                        graphDb = openRequest.result;
                        // Display the list of databases in the form
                        displayData();
                    });
                }
                const browserName = getBrowserName();
                if (browserName != 'Firefox') {
                    console.log("IndexedDB is supported.");
                    INDEXED_DB_SUPPORTED = true;
                    initDb();
                } else {
                    console.log("IndexedDB is not supported.");
                }
                
                initializeEventSource();
                chart.draw(data, google.charts.Line.convertOptions(materialOptions));

            } // end init

        </script>
        <title>Server-Sent Events Clients</title>
    </head>
    <body>
        <div id="chart_wrap">
            <div id="linechart_material" style="width: auto; height: 600px"></div>
        </div>
        <div id="databases_wrap">
            <div id="databases" style="width: auto">
            <!-- TODO Display the available databases and offer a/c/d/display -->
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

MIMETypes.configure(
    default_to="text/plain",
    # Unregistering unnecessary MIME types can save memory
    keep_for=[".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico"],
    # If you need to, you can add additional MIME types
)


@server.route("/js/test.js")
def home(request: Request):
    return FileResponse(request, "test.js", "/js")


@server.route("/id", GET)
def client(request: Request):
    return Response(request, MY_ID, content_type="text/html")


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


try:
    pin = digitalio.DigitalInOut(board.GP22)
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP
    button = Debouncer(pin)
    while True:
        pool_result = server.poll()
        button.update()
        if button.fell:
            if debug:
                print('DEBUG - button Just pressed')
            connected_client.collected = monotonic_ns()
        elif button.rose:
            if debug:
                print('DEBUG - button Just released')
        else:
            pass
        if connected_client.ready:
            connected_client.send_message()
except Exception as e:
    print("Error:\n", str(e))
    print("Resetting mcu in 10 seconds")
    led_on()
    time.sleep(10)
    microcontroller.reset()






