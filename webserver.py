# Copyright @ 2023, Adrian Blakey. All rights reserved
# Runs the microdot webserver

from microdot_asyncio import Microdot, Response, send_file
from microdot_utemplate import render_template
from microdot_asyncio_websocket import with_websocket
from device import Device, the_device
import uasyncio as asyncio
from logging_state import Logging_State
from log_file import Log_File

import time
import logging

log = logging.getLogger("webserver")

global server
global the_ls

class LS_Value():
    # Hack to pass logging_state to the webserver
    def __init__(self):
        pass
         
    def set_state(self, logging_state: Logging_State) -> None:
        self._logging_state = logging_state
        
    def state(self) -> Logging_State:
        return self._logging_state

the_ls = LS_Value()

server = Microdot()  
Response.default_content_type = 'text/html'

# root route
@server.route('/')
async def index(request):
    # return microdot_utemplate.render_template('index.html')
    return render_template('index.html')

@server.route('/ws')
@with_websocket
async def send_data(request, ws):
    while True:
        # TODO apply some smoothing by capturing say 1 every ms and emitting the smoothed value
        if the_ls.state().playback():
            rec = the_ls.state().get_file().read_next(ts=False)
            if len(rec) == 0:
                the_ls.state().playback_off()
        else:
            rec = the_device.read()
        if len(rec) != 0:
            try:
                await ws.send(rec)
            except OSError as ex:
                log.error('WS send failed %s', ex)
        await asyncio.sleep_ms(10)
        #time.sleep_ms(10) # 10ms same as collection frequency
        
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

