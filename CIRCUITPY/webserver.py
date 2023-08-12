
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
            if log.is_debug:
                log.logger.debug("Error:\n %s", e)
                log.logger.debug("Resetting mcu in 10 seconds")


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
                data.addColumn('number', 'Track Voltage');
                data.addColumn('number', 'Controller Voltage');
                data.addColumn('number', 'Controller Current');

                var materialOptions = {
                    title: 'Data Logger',
                    titlePosition: 'out',
                    titleTextStyle: {fontSize: 28, bold: true},
                    legend: { position: 'out' },
                    width: 1000,
                    height: 600,
                    hAxis: {
                        gridlines: {color: 'grey', minSpacing: 40, multiple: 1, interval: [1], count: 10},
                        baseLine: 0, 
                        title: 'Elapse (sec)', 
                        textStyle: {color: 'black', bold: true},
                        format: '###.###',
                        viewWindow: {max: 10, min: 0}
                    },
                    series: {
                        0: {color: 'lightblue', lineWidth: 2, targetAxisIndex: 0},
                        1: {color: 'blue', lineWidth: 2, targetAxisIndex: 0},
                        2: {color: 'red', lineWidth: 2, targetAxisIndex: 1}
                    },
                    vAxes: {
                        0: {
                            title:'Voltage (V)',
                            textStyle: {color: 'blue', bold: true},
                            viewWindow: {min: -18, max: 18}
                        },
                        1: {
                            title:'Current (A)',
                            textStyle: {color: 'red', bold: true},
                            viewWindow: {min: -20, max: 20}
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
                        objectStore.createIndex("t_volts", "t_volts", { unique: false });
                        objectStore.createIndex("c_volts", "c_volts", { unique: false });
                        objectStore.createIndex("c_current", "c_current", { unique: false });
                        console.log("Database setup complete");
                    }
                    openRequest.addEventListener("upgradeneeded", (e) => {
                        // Grab a reference to the opened database
                        console.log("Upgrade needed");
                        db = e.target.result;
                        createObjectStore();
                    });
                }
                function addData(ts, t_volts, c_volts, c_current) {
                    // Adds a row to the database
                    // console.log("adding", ts, t_volts, c_volts, c_current, mark);
                    const newItem = { ts: ts, t_volts: t_volts, c_volts: c_volts, c_current: c_current};
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
                    });

                    transaction.addEventListener("error", () =>
                        console.log("Transaction not opened due to error")
                    );
                }
                function initializeEventSource() {
                    console.log("Opening eventsource connection");
                    const eventSource = new EventSource('/connect-client');
                    eventSource.onerror = onError;
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
                        // console.log('First firstElapseTime is:', tok[0]);
                        firstElapseTime = xVal;
                    }
                    // Handle the mark - only save data between marks?
                    if (INDEXED_DB_SUPPORTED) {
                        if (tok[4] == '1') {
                            if (saveData) {
                                console.log("Mark found stop saving data");
                                materialOptions.series[0].lineWidth = 2;
                                materialOptions.series[1].lineWidth = 2;
                                materialOptions.series[2].lineWidth = 2;
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
                    // console.log('Add row to chart');
                    eTime = (xVal - firstElapseTime) / 1000000000; // scale it to n.xxxxx seconds
                    if (eTime < 0.0) {    // The clock reset so reestablish the zero
                        firstElapseTime = xVal;
                        eTime = 0.0;
                    }
                    // console.log('Normalized etime', eTime);
                    data.addRow([parseFloat(eTime),parseFloat(tok[1]),parseFloat(tok[2]),parseFloat(tok[3])]);

                    // console.log('Max, min, etime', materialOptions.hAxis.viewWindow.max, materialOptions.hAxis.viewWindow.min, eTime);
                    latestX = Math.ceil(eTime);  // Round up
                    // console.log('if eTime ceil is bigger than max, move vw', latestX, materialOptions.hAxis.viewWindow.min, materialOptions.hAxis.viewWindow.max);
                    if (latestX >= materialOptions.hAxis.viewWindow.max) {       // step the vw forward in front of the value
                        materialOptions.hAxis.viewWindow.max++;
                        materialOptions.hAxis.viewWindow.min++;
                        // console.log('Min, max, rowct', materialOptions.hAxis.viewWindow.min, materialOptions.hAxis.viewWindow.max, data.getNumberOfRows());
                        data.removeRows(0, Math.floor(rowCount / 10) - 1);           // garbage collect
                    }
                    // console.log("draw", materialOptions);
                    console.log("chart draw", performance.now());
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
                        data.addColumn('number', 'Track Voltage');
                        data.addColumn('number', 'Controller Voltage');
                        data.addColumn('number', 'Controller Current');

                        const cursor = e.target.result;

                        // If there is still another data item to iterate through, keep running this code
                        if (cursor) {
                            data.addRow([parseFloat(cursor.value.ts),
                                parseFloat(cursor.value.t_volts),
                                parseFloat(cursor.value.c_volts),
                                parseFloat(cursor.value.c_current)
                                ]);
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
                    // TODO display this in the browser
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


@server.route("/js/test.js")
def home(request: Request) -> Response:
    return FileResponse(request, "test.js", "/js")


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


