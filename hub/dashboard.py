"""
dashboard.py - Juice Battle live scoreboard
Flask + Socket.IO server. Reads game state on a timer, pushes to browser.
No game logic lives here. Display only.
"""

import time
import config
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit

# ── Crowd-facing HTML template ─────────────────────────────────────────────
# Served once on browser connect. Socket.IO client loaded from local Flask-SocketIO
# server (/socket.io/socket.io.js) - no CDN dependency for offline market use.
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Juice Battle</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #0d0d0d;
    color: #fff;
    font-family: 'Arial Black', Arial, sans-serif;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    user-select: none;
}
.title {
    font-size: 1.8vw;
    letter-spacing: 0.35em;
    text-transform: uppercase;
    opacity: 0.3;
    margin-bottom: 3vh;
}
.scoreboard {
    display: flex;
    align-items: stretch;
    gap: 6vw;
    width: 100%;
    max-width: 1400px;
    padding: 0 4vw;
}
.jar {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4vh 2vw 3vh;
    border-radius: 24px;
}
.jar-0 { background: #0d1a0d; border: 2px solid #2e7d32; }
.jar-1 { background: #0a0f1e; border: 2px solid #1565c0; }
.jar-name {
    font-size: 1.8vw;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.55;
    margin-bottom: 1vh;
}
.glass-count {
    font-size: 24vw;
    font-weight: 900;
    line-height: 0.9;
    font-variant-numeric: tabular-nums;
}
.jar-0 .glass-count { color: #66bb6a; }
.jar-1 .glass-count { color: #42a5f5; }
.glass-label {
    font-size: 1.2vw;
    letter-spacing: 0.25em;
    opacity: 0.35;
    margin-top: 1.5vh;
}
.partial-wrap { width: 100%; margin-top: 2.5vh; }
.partial-bar {
    width: 100%;
    height: 10px;
    background: #1e1e1e;
    border-radius: 5px;
    overflow: hidden;
}
.partial-fill {
    height: 100%;
    border-radius: 5px;
    transition: width 0.5s ease;
    min-width: 0%;
    max-width: 100%;
}
.jar-0 .partial-fill { background: #2e7d32; }
.jar-1 .partial-fill { background: #1565c0; }
.partial-label {
    font-size: 1vw;
    opacity: 0.35;
    text-align: center;
    margin-top: 0.6vh;
    font-family: Arial, sans-serif;
    font-weight: 400;
}
.vs {
    font-size: 4vw;
    color: #2a2a2a;
    font-style: italic;
    align-self: center;
    flex-shrink: 0;
}
.badge {
    font-size: 0.8vw;
    letter-spacing: 0.18em;
    font-weight: 700;
    padding: 0.3vh 0.8vw;
    border-radius: 4px;
    min-height: 2.5vh;
    margin-bottom: 0.8vh;
}
.badge-hidden { opacity: 0; }
.badge-anomaly { background: #c62828; color: #ffcdd2; }
.badge-bounce  { background: #e65100; color: #ffe0b2; }
@keyframes anomaly-pulse {
    0%, 100% { border-color: #c62828; }
    50%       { border-color: #ef5350; }
}
.jar-anomaly { background: #1a0000 !important;
               animation: anomaly-pulse 1.5s ease-in-out infinite; }
.jar-bounce  { border-color: #e65100 !important;
               background: #1a1000 !important; }
.status {
    font-size: 0.9vw;
    opacity: 0.18;
    margin-top: 3vh;
    letter-spacing: 0.15em;
    font-family: monospace;
}
</style>
</head>
<body>

<div class="title">Juice Battle</div>

<div class="scoreboard">
  <div class="jar jar-0">
    <div class="badge badge-hidden" id="badge-0">&nbsp;</div>
    <div class="jar-name">Jar 0</div>
    <div class="glass-count" id="count-0">0</div>
    <div class="glass-label">GLASSES</div>
    <button id="reset-0"
            onclick="resetJar(0)"
            style="margin-top:1.5vh; padding:4px 14px;
                   background:transparent; border:1px solid #444;
                   color:#888; font-size:0.7rem; border-radius:4px;
                   cursor:pointer; letter-spacing:0.08em;">
      RESET
    </button>
    <div class="partial-wrap">
      <div class="partial-bar">
        <div class="partial-fill" id="partial-0" style="width:0%"></div>
      </div>
      <div class="partial-label" id="partial-label-0">&nbsp;</div>
    </div>
  </div>

  <div class="vs">VS</div>

  <div class="jar jar-1">
    <div class="badge badge-hidden" id="badge-1">&nbsp;</div>
    <div class="jar-name">Jar 1</div>
    <div class="glass-count" id="count-1">0</div>
    <div class="glass-label">GLASSES</div>
    <button id="reset-1"
            onclick="resetJar(1)"
            style="margin-top:1.5vh; padding:4px 14px;
                   background:transparent; border:1px solid #444;
                   color:#888; font-size:0.7rem; border-radius:4px;
                   cursor:pointer; letter-spacing:0.08em;">
      RESET
    </button>
    <div class="partial-wrap">
      <div class="partial-bar">
        <div class="partial-fill" id="partial-1" style="width:0%"></div>
      </div>
      <div class="partial-label" id="partial-label-1">&nbsp;</div>
    </div>
  </div>
</div>

<div class="status" id="status">connecting...</div>

<!-- socket.io.js downloaded to hub/static/ during setup - no CDN at stall -->
<script src="/static/socket.io.js"></script>
<script>
const socket = io();

function el(id) { return document.getElementById(id); }

socket.on('connect', () => {
    el('status').textContent = 'live';
});

socket.on('disconnect', () => {
    el('status').textContent = 'reconnecting...';
});

socket.on('state', (data) => {
    // JSON serialisation converts Python int dict keys to strings.
    // {0: 5} in Python becomes {"0": 5} in JSON.
    // JS obj[0] and obj["0"] are equivalent, but we use strings explicitly.
    const gc  = data.glass_count;
    const pg  = data.partial_g;
    const vol = data.glass_volume_g || 150;

    el('count-0').textContent = gc['0'] ?? 0;
    el('count-1').textContent = gc['1'] ?? 0;

    const p0   = pg['0'] ?? 0;
    const p1   = pg['1'] ?? 0;
    const pct0 = Math.min(100, (p0 / vol) * 100).toFixed(0);
    const pct1 = Math.min(100, (p1 / vol) * 100).toFixed(0);

    el('partial-0').style.width = pct0 + '%';
    el('partial-1').style.width = pct1 + '%';
    el('partial-label-0').textContent = p0 > 1 ? '+' + p0.toFixed(0) + 'g' : String.fromCharCode(160);
    el('partial-label-1').textContent = p1 > 1 ? '+' + p1.toFixed(0) + 'g' : String.fromCharCode(160);

    [0, 1].forEach(function(n) {
        var status = (data.node_status && data.node_status[String(n)]) || 'ok';
        var jar   = document.querySelector('.jar-' + n);
        var badge = el('badge-' + n);
        jar.classList.remove('jar-anomaly', 'jar-bounce');
        badge.className = 'badge';
        if (status === 'anomaly') {
            jar.classList.add('jar-anomaly');
            badge.classList.add('badge-anomaly');
            badge.textContent = 'JAR ABSENT';
        } else if (status === 'bounce') {
            jar.classList.add('jar-bounce');
            badge.classList.add('badge-bounce');
            badge.textContent = 'DISTURBANCE';
        } else {
            badge.classList.add('badge-hidden');
            badge.textContent = ' ';
        }
    });
});

function resetJar(n) {
  fetch('/reset/' + n, {method: 'POST'})
    .then(r => r.json())
    .then(d => { if (!d.ok) console.error('reset failed', d); });
}
</script>

</body>
</html>"""


class Dashboard:
    """
    Crowd-facing scoreboard server.
    Reads game.get_state() every 500ms on a background thread.
    Pushes state to all connected browsers via Socket.IO.
    No game logic lives here - display only.
    """

    def __init__(self, game):
        # game instance injected by main.py - Dashboard never imports game directly
        self._game = game

        self._app = Flask(__name__)
        # threading mode: real OS threads, no monkey-patching.
        # eventlet/gevent would conflict with transport.py's real threads.
        self._sio = SocketIO(self._app, async_mode='threading', cors_allowed_origins='*')

        self._app.add_url_rule('/', 'index', self._serve_index)
        self._app.add_url_rule('/reset/<int:node_id>', 'reset_node',
                               self._reset_node, methods=['POST'])

        @self._sio.on('connect')
        def _on_browser_connect():
            # WHY: push state immediately to reconnecting browser.
            # Without this, browser shows HTML default (0) for up to 500ms
            # while waiting for next _push_loop cycle — looks like score reset.
            state = self._game.get_state()
            emit('state', {
                'glass_count':    state['glass_count'],
                'partial_g':      state['partial_g'],
                'running':        state['running'],
                'glass_volume_g': config.GLASS_VOLUME_G,
                'node_status':    state['node_status'],
            })

    def _reset_node(self, node_id: int):
        if node_id not in (0, 1):
            return jsonify({'ok': False, 'error': 'invalid node'}), 400
        self._game.reset_node(node_id)
        return jsonify({'ok': True, 'node_id': node_id})

    def _serve_index(self):
        """Serve the scoreboard HTML page."""
        return render_template_string(HTML_TEMPLATE)

    def _push_loop(self):
        """
        Background task: poll game state every 500ms, push to all browsers.
        Runs as a daemon thread (started by start_background_task).
        game.get_state() is Lock-protected - safe to call from any thread.
        """
        while True:
            state = self._game.get_state()
            payload = {
                'glass_count':    state['glass_count'],
                'partial_g':      state['partial_g'],
                'running':        state['running'],
                'glass_volume_g': config.GLASS_VOLUME_G,
                'node_status':    state['node_status'],
            }
            self._sio.emit('state', payload)
            time.sleep(0.5)

    def start(self):
        """
        Start the background push loop, then run the Flask-SocketIO server.
        Blocks until the process exits (Ctrl+C).
        Call last in main.py - transport and game must be started first.
        """
        self._sio.start_background_task(self._push_loop)
        print(f"[DASHBOARD] Scoreboard live at http://0.0.0.0:{config.DASHBOARD_PORT}")
        # allow_unsafe_werkzeug=True: required in newer Flask-SocketIO (>=5.0)
        # for threading mode with Werkzeug's dev server. Safe for kiosk use.
        self._sio.run(
            self._app,
            host='0.0.0.0',
            port=config.DASHBOARD_PORT,
            allow_unsafe_werkzeug=True,
        )
