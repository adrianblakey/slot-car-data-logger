from microdot_asyncio import Microdot, Response, send_file
from microdot_utemplate import render_template
from microdot_asyncio_websocket import with_websocket
from device import Device, the_device
import time

global server

server = Microdot()  
Response.default_content_type = 'text/html'


# root route
@server.route('/')
async def index(request):
#    return microdot_utemplate.render_template('index.html')
    return render_template('index.html')

@server.route('/ws')
@with_websocket
async def send_data(request, ws):
    while True:
        # data = await ws.receive()
        time.sleep(.01)
        await ws.send(the_device.read_all())


# Static CSS/JSS
@server.route("/static/<path:path>")
def static(request, path):
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    return send_file("static/" + path)


# shutdown
@server.get('/shutdown')
def shutdown(request):
    request.app.shutdown()
    return 'The server is shutting down...'
   