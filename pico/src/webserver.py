# Copyright @ 2026 Adrian Blakey. All rights reserved
# webserver.py — the abbreviated web UI (Microdot), reached over Wi-Fi.
#
# "Abbreviated" on purpose: no live graph (the reference's CartesianGraph
# needs a display-class budget of RAM/CPU this board doesn't have to spare
# alongside Wi-Fi+BLE) — status text, start/stop/mark, a session list with
# download (raw or CSV), erase, and a profile form. An optional /ws feed
# pushes plain numeric text lines for a live readout.
#
# main.py owns all real state; this module is wired to it via configure()
# rather than importing main (same pattern as buzzer/ble_server), so it can
# be exercised independently.

import struct
import asyncio

from microdot import Microdot, Response, send_file
from microdot.websocket import with_websocket

import flash_writer as fw
import log_record as lr
from session_profile import PROFILE
import logconfig

log = None


def _log():
    global log
    if log is None:
        log = logconfig.get_logger("webserver")
    return log


# Wire format used by main.py's publisher when it fans samples out to
# subscriber queues (flash writer, this module's /ws feed). Kept here as the
# single source of truth for the constant; main.py packs with the same
# format string.
LIVE_FMT = '<ifff'   # t_us(i32), current_A, track_V, supply_V

app = Microdot()
Response.default_content_type = 'text/html'

_status_fn  = None    # () -> dict
_start_fn   = None    # () -> None
_stop_fn    = None    # () -> None
_mark_fn    = None    # () -> None
_subscribers = None   # shared list[RingbufQueue] from main.py's publisher


def configure(status_fn, start_fn, stop_fn, mark_fn, subscribers=None) -> None:
    global _status_fn, _start_fn, _stop_fn, _mark_fn, _subscribers
    _status_fn = status_fn
    _start_fn = start_fn
    _stop_fn = stop_fn
    _mark_fn = mark_fn
    _subscribers = subscribers


# ── static / index ────────────────────────────────────────────────────────────

@app.get('/')
async def index(request):
    return send_file('static/index.html')


@app.get('/static/<path:path>')
async def static(request, path):
    if '..' in path:
        return 'Not found', 404
    return send_file('static/' + path)


# ── status + control ───────────────────────────────────────────────────────────

@app.get('/api/status')
async def api_status(request):
    st = _status_fn() if _status_fn else {}
    st['profile'] = PROFILE.as_dict()
    return Response(body=st)


@app.post('/api/start')
async def api_start(request):
    if _start_fn:
        _start_fn()
    return Response(body=_status_fn() if _status_fn else {})


@app.post('/api/stop')
async def api_stop(request):
    if _stop_fn:
        _stop_fn()
    return Response(body=_status_fn() if _status_fn else {})


@app.post('/api/mark')
async def api_mark(request):
    if _mark_fn:
        _mark_fn()
    return Response(body=_status_fn() if _status_fn else {})


# ── profile ─────────────────────────────────────────────────────────────────

@app.get('/api/profile')
async def api_profile_get(request):
    return Response(body=PROFILE.as_dict())


@app.post('/api/profile')
async def api_profile_post(request):
    body = request.json or {}
    PROFILE.update(**body)
    return Response(body=PROFILE.as_dict())


# ── sessions ────────────────────────────────────────────────────────────────

@app.get('/api/sessions')
async def api_sessions(request):
    import os
    out = []
    for name in fw.list_sessions():
        try:
            size = os.stat(fw.DATA_DIR + '/' + name)[6]
        except OSError:
            size = 0
        out.append({'name': name, 'size': size})
    return Response(body=out)


@app.post('/api/sessions/erase')
async def api_sessions_erase(request):
    n = fw.erase_all()
    _log().info("Erased %d session file(s) via web UI", n)
    return Response(body={'erased': n})


def _session_path(name):
    if '..' in name or '/' in name:
        return None
    return fw.DATA_DIR + '/' + name


@app.get('/api/sessions/<name>')
async def api_session_download(request, name):
    path = _session_path(name)
    if path is None:
        return 'Not found', 404
    try:
        return send_file(path, content_type='application/octet-stream')
    except OSError:
        return 'Not found', 404


@app.get('/api/sessions/<name>/csv')
async def api_session_csv(request, name):
    """
    Convert a binary session file to CSV on the fly, streamed one line at a
    time via an async generator (Microdot streams any response body that
    has __anext__). NOT buffered fully in memory — confirmed on hardware
    that building the whole CSV as one string works fine in isolation but
    fails with a silent 500 under the combined memory pressure of Wi-Fi +
    BLE + the ADC pipeline all live at once; streaming uses ~constant memory
    regardless of session length.
    """
    path = _session_path(name)
    if path is None:
        return 'Not found', 404
    try:
        f = open(path, 'rb')
        hdr = lr.read_header(f)
    except (OSError, ValueError) as e:
        return 'Read error: {}'.format(e), 500

    async def rows():
        try:
            for k, v in hdr['profile'].items():
                yield '# {}={}\n'.format(k, v)
            yield '# start_epoch={}\n'.format(hdr['start_epoch'])
            yield '# sample_rate_hz={}\n'.format(hdr['sample_rate_hz'])
            yield 'dt_ms,current_A,track_V,supply_V,marker\n'
            while True:
                buf = f.read(lr.RECORD_SIZE)
                if len(buf) < lr.RECORD_SIZE:
                    break
                row = lr.unpack_record(buf)
                yield '{},{},{:.2f},{:.2f},{}\n'.format(
                    row['dt_ms'],
                    '' if row['marker'] else '{:.2f}'.format(row['current_A']),
                    row['track_V'], row['supply_V'],
                    1 if row['marker'] else 0)
        finally:
            f.close()

    return Response(body=rows(), headers={'Content-Type': 'text/csv'})


# ── live numeric feed (optional, abbreviated — no graph) ────────────────────

@app.route('/ws')
@with_websocket
async def ws_live(request, ws):
    if _subscribers is None:
        return
    from primitives import RingbufQueue
    q = RingbufQueue(20)
    _subscribers.append(q)
    try:
        while True:
            packed = await q.get()
            _t, current_A, track_V, supply_V = struct.unpack(LIVE_FMT, packed)
            try:
                await ws.send('{:.2f},{:.2f},{:.2f}\n'.format(
                    current_A, track_V, supply_V))
            except OSError:
                break
    finally:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass
