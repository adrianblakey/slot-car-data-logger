const CHART_COLORS = {
  red: "rgb(255, 99, 132)",
  orange: "rgb(255, 159, 64)",
  yellow: "rgb(255, 205, 86)",
  green: "rgb(75, 192, 192)",
  blue: "rgb(54, 162, 235)",
  purple: "rgb(153, 102, 255)",
  grey: "rgb(201, 203, 207)",
};

const NAMED_COLORS = [
  CHART_COLORS.red,
  CHART_COLORS.orange,
  CHART_COLORS.yellow,
  CHART_COLORS.green,
  CHART_COLORS.blue,
  CHART_COLORS.purple,
  CHART_COLORS.grey,
];

function namedColor(index) {
  return NAMED_COLORS[index % NAMED_COLORS.length];
}

function transparentize(value, opacity) {
  var alpha = opacity === undefined ? 0.5 : 1 - opacity;
  return colorLib(value).alpha(alpha).rgbString();
}

function rand(min, max) {
  _seed = (11 * 9301 + 49297) % 233280;
  return min + (_seed / 233280) * (max - min);
}

var dataFirst = {
  label: "Track Voltage",
  data: [],
  lineTension: 0,
  fill: false,
  borderColor: "red",
  yAxisID: "y",
};

var dataSecond = {
  label: "Controller Voltage",
  data: [],
  lineTension: 0,
  fill: false,
  borderColor: "blue",
  yAxisID: "y",
};

var dataThird = {
  label: "Controller Current",
  data: [],
  lineTension: 0,
  fill: false,
  borderColor: "green",
  yAxisID: "y1",
};

var loggerData = {
  datasets: [dataFirst, dataSecond, dataThird],
};

var chartOptions = {
  responsive: true,
  legend: {
    display: true,
    position: "top",
    labels: {
      boxWidth: 80,
      fontColor: "black",
    },
  },
  stacked: false,
  plugins: {
    title: {
      display: true,
      text: "Slot Car Data Logger",
    },
  },
  scales: {
    x: {
      type: "realtime",
      realtime: {
        ttl: 60000,
        duration: 20000,
      },
      y: {
        title: {
          display: true,
          text: "Voltage",
        },
        type: "linear",
        display: true,
        position: "left",
      },
      y1: {
        title: {
          display: true,
          text: "Current",
        },
        type: "linear",
        display: true,
        position: "right",
        // grid line settings
        grid: {
          drawOnChartArea: false, // grid lines for one axis to show up
        },
      },
    },
    interaction: {
      intersect: false,
    },
  },
};

const data = {
  datasets: [
    {
      label: "Track Voltage",
      backgroundColor: CHART_COLORS.red,
      borderColor: CHART_COLORS.red,
      lineTension: 0,
      fill: false,
      data: [],
      yAxisID: "y",
      pointRadius: 1,
    },
    {
      label: "Controller Voltage",
      backgroundColor: CHART_COLORS.blue,
      borderColor: CHART_COLORS.blue,
      lineTension: 0,
      fill: true,
      yAxisID: "y",
      data: [],
      pointRadius: 1,
    },
    {
      label: "Controller Current",
      backgroundColor: CHART_COLORS.green,
      borderColor: CHART_COLORS.green,
      lineTension: 0,
      fill: false,
      yAxisID: "y1",
      data: [],
      pointRadius: 1,
    },
  ],
};

const annotation1 = {
  type: "line",
  borderColor: "black",
  borderWidth: 5,
  click: function ({ chart, element }) {
    console.log("Line annotation clicked");
  },
  label: {
    backgroundColor: "red",
    content: "Test Label",
    display: true,
  },
  scaleID: "y",
  value: rand(-100, 100),
};
const annotation2 = {
  type: "box",
  backgroundColor: "rgba(101, 33, 171, 0.5)",
  borderColor: "rgb(101, 33, 171)",
  borderWidth: 1,
  click: function ({ chart, element }) {
    console.log("Box annotation clicked");
  },
  drawTime: "beforeDatasetsDraw",
  xMax: "April",
  xMin: "February",
  xScaleID: "x",
  yMax: rand(-100, 100),
  yMin: rand(-100, 100),
  yScaleID: "y",
};

const config = {
  type: "line",
  data: data,
  options: {
    responsive: true,
    interaction: {
      mode: "index",
      intersect: false,
    },
    stacked: false,
    plugins: {
      annotation: {
        annotations: {
          annotation1,
          annotation2,
        },
      },
      title: {
        display: true,
        text: "Slot car data logger",
      },
    },
    scales: {
      x: {
        type: "realtime",
        realtime: {
          //         duration: 20000,
          //         refresh: 1000,
          //         delay: 2000,
          //         onRefresh: onRefresh,
        },
      },
      y: {
        type: "linear",
        display: true,
        position: "left",
        title: {
          display: true,
          text: "Voltage",
        },
        suggestedMin: 0,
        suggestedMax: 15,
      },
      y1: {
        type: "linear",
        display: true,
        position: "right",
        title: {
          display: true,
          text: "Current",
        },
        suggestedMin: -10,
        suggestedMax: 18,
        // grid line settings
        grid: {
          drawOnChartArea: false, // grid lines for one axis to show up
        },
      },
    },
    interaction: {
      intersect: false,
    },
  },
};

//const theChart = new Chart(document.getElementById("theChart"), {
// type: "line",
// data: loggerData,
// options: chartOptions,
//});

const theChart = new Chart(document.getElementById("theChart"), config);

// WebSocket support
var targetUrl = `ws://${location.host}/ws`;
var websocket;
window.addEventListener("load", onLoad);

function onLoad() {
  initializeSocket();
}

function initializeSocket() {
  console.log("Opening WebSocket connection MicroPython Server...");
  websocket = new WebSocket(targetUrl);
  websocket.onopen = onOpen;
  websocket.onclose = onClose;
  websocket.onmessage = onMessage;
}
function onOpen(event) {
  console.log("Starting connection to WebSocket server..");
}
function onClose(event) {
  console.log("Closing connection to server..");
  setTimeout(initializeSocket, 2000);
}
function onMessage(event) {
  let tok = event.data.split(",");
  // tv, cv, ci
  console.log("Update values", tok[0], tok[1], tok[2]);
  const now = Date.now();
  theChart.data.datasets[0].data.push({
    x: now,
    y: parseFloat(tok[0]),
  });
  theChart.data.datasets[1].data.push({
    x: now,
    y: parseFloat(tok[1]),
  });
  theChart.data.datasets[2].data.push({
    x: now,
    y: parseFloat(tok[2]),
  });
  theChart.update("quiet");
}

function sendMessage(message) {
  websocket.send(message);
}

function updateValues(data) {
  sensorData.unshift(data);
  if (sensorData.length > 20) sensorData.pop();
  sensorValues.value = sensorData.join("\r\n");
}
