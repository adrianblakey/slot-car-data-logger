
google.charts.load('current', {'packages': ['line']});
google.charts.setOnLoadCallback(init);

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

    const data = new google.visualization.DataTable();
    data.addColumn('number', 'Elapse');
    data.addColumn('number', 'Track Voltage');
    data.addColumn('number', 'Controller Voltage');
    data.addColumn('number', 'Controller Current');

    const materialOptions = {
        title: 'Data Logger',
        titlePosition: 'out',
        titleTextStyle: {fontSize: 28, bold: true},
        legend: {position: 'out'},
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
                title: 'Voltage (V)',
                textStyle: {color: 'blue', bold: true},
                viewWindow: {min: -18, max: 18}
            },
            1: {
                title: 'Current (A)',
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

    const chart = new google.charts.Line(document.getElementById('linechart_material'));

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
            const div = document.getElementById('databases');
            const h2 = document.createElement('h2');
            h2.textContent = 'Databases in the Browser';
            div.appendChild(h2);
            const ul = document.createElement('ul');
            div.appendChild(ul);
            for (let i = 0; i < databases.length; i++) {
                const li = document.createElement('li');
                const delButton = document.createElement('button');
                delButton.innerText = 'delete';
                delButton.onclick = function () { // remove list item here
                    deleteADatabase(this.parentElement.id);
                    this.parentElement.remove();
                };
                const disButton = document.createElement('button');
                disButton.innerText = 'graph';
                disButton.onclick = function () { // graph the database
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
            console.log("Database", db_name, "opened successfully");

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
            objectStore.createIndex("t_volts", "t_volts", {unique: false});
            objectStore.createIndex("c_volts", "c_volts", {unique: false});
            objectStore.createIndex("c_current", "c_current", {unique: false});
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
        const newItem = {ts: ts, t_volts: t_volts, c_volts: c_volts, c_current: c_current};
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

    let saveData = false;         // cache data in database or not
    let firstElapseTime = 0

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
        let tok = event.data.split(',');
        console.log("Update values", tok[0], tok[1], tok[2], tok[3], tok[4]);
        let xVal = parseInt(tok[0]);                  // elapse time as an int
        let rowCount = data.getNumberOfRows();
        if (rowCount === 0) {  // before we add anything, save the first e time
            // console.log('First firstElapseTime is:', tok[0]);
            firstElapseTime = xVal;
        }
        // Handle the mark - only save data between marks?
        if (INDEXED_DB_SUPPORTED) {
            if (tok[4] === '1') {
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
        let eTime = (xVal - firstElapseTime) / 1000000000; // scale it to n.xxxxx seconds
        if (eTime < 0.0) {    // The clock reset so reestablish the zero
            firstElapseTime = xVal;
            eTime = 0.0;
        }
        // console.log('Normalized etime', eTime);
        data.addRow([eTime, parseFloat(tok[1]), parseFloat(tok[2]), parseFloat(tok[3])]);

        // console.log('Max, min, etime', materialOptions.hAxis.viewWindow.max, materialOptions.hAxis.viewWindow.min, eTime);
        let latestX = Math.ceil(eTime);  // Round up
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
            const data = new google.visualization.DataTable();
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
            console.log("Database", dbName, "opened successfully");

            // Store the opened database object in the db variable. This is used a lot below
            graphDb = openRequest.result;
            // Display the list of databases in the form
            displayData();
        });
    }

    const browserName = getBrowserName();
    if (browserName !== 'Firefox') {
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
