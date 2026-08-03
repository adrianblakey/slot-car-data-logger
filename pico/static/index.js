// Slot Car Logger — abbreviated web UI.
// No graph, no framework: status polling + a plain numeric websocket feed.

async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.ok ? res.json().catch(() => ({})) : {};
}

function fmtBytes(n) {
  if (n == null) return '-';
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
  return (n / (1024 * 1024)).toFixed(2) + ' MB';
}

async function refreshStatus() {
  const st = await api('/api/status');
  document.getElementById('st-recording').textContent = st.recording ? 'ON' : 'OFF';
  document.getElementById('st-count').textContent = st.record_count ?? '-';
  document.getElementById('st-flash').textContent =
    st.flash_free_pct != null ? st.flash_free_pct + '%' : '-';
  if (st.profile) {
    document.getElementById('p-track').value = st.profile.track ?? '';
    document.getElementById('p-race').value = st.profile.race ?? '';
    document.getElementById('p-lane').value = st.profile.lane ?? '';
    document.getElementById('p-controller').value = st.profile.controller ?? '';
    document.getElementById('p-car').value = st.profile.car ?? '';
  }
}

async function refreshSessions() {
  const sessions = await api('/api/sessions');
  const tbody = document.querySelector('#session-table tbody');
  tbody.innerHTML = '';
  (Array.isArray(sessions) ? sessions : []).forEach((s) => {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td>' + s.name + ' (' + fmtBytes(s.size) + ')</td>' +
      '<td><a href="/api/sessions/' + s.name + '">raw</a>' +
      '<a href="/api/sessions/' + s.name + '/csv">csv</a></td>';
    tbody.appendChild(tr);
  });
}

document.getElementById('btn-start').onclick = async () => {
  await api('/api/start', { method: 'POST' });
  refreshStatus();
};
document.getElementById('btn-stop').onclick = async () => {
  await api('/api/stop', { method: 'POST' });
  refreshStatus();
  refreshSessions();
};
document.getElementById('btn-mark').onclick = () => api('/api/mark', { method: 'POST' });
document.getElementById('btn-erase').onclick = async () => {
  if (!confirm('Erase ALL session files?')) return;
  await api('/api/sessions/erase', { method: 'POST' });
  refreshSessions();
};

document.getElementById('profile-form').onsubmit = async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  await api('/api/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      track: f.track.value,
      race: f.race.value,
      lane: parseInt(f.lane.value, 10) || 1,
      controller: f.controller.value,
      car: f.car.value,
    }),
  });
};

function connectLive() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(proto + '//' + location.host + '/ws');
  ws.onmessage = (ev) => {
    const [i, vt, vs] = ev.data.trim().split(',');
    document.getElementById('live-i').textContent = i;
    document.getElementById('live-vt').textContent = vt;
    document.getElementById('live-vs').textContent = vs;
  };
  ws.onclose = () => setTimeout(connectLive, 3000);
}

refreshStatus();
refreshSessions();
connectLive();
setInterval(refreshStatus, 3000);
setInterval(refreshSessions, 10000);
