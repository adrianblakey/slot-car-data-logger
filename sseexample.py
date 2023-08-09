# SPDX-FileCopyrightText: 2023 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

from time import monotonic
import microcontroller
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, SSEResponse, GET


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


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
        print("connected client response", str(connected_client.response))
        connected_client.response.close()  # Close any existing connection
    connected_client.response = response
    return response


server.start(str(wifi.radio.ipv4_address))
while True:
    pool_result = server.poll()

    if connected_client.ready:
        connected_client.send_message()