"""
dashboard.py - Juice Battle live scoreboard
Flask + Socket.IO server. Reads game state on a timer, pushes to browser.
No game logic lives here. Display only.
"""

import time
import config
from flask import Flask, render_template_string, jsonify, make_response
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
.badge-bounce        { background: #e65100; color: #ffe0b2; }
.badge-disconnected  { background: #F59E0B; color: #1a1200; }
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
.vs-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    gap: 2vh;
}
.game-over-btn {
    padding: 8px 20px;
    background: #e65100;
    border: none;
    color: #fff;
    font-size: 0.75rem;
    font-weight: 700;
    border-radius: 6px;
    cursor: pointer;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.game-over-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
}
.winner-banner {
    width: 100%;
    max-width: 1400px;
    padding: 2vh 4vw;
    margin-bottom: 2vh;
    text-align: center;
    font-size: 4vw;
    font-weight: 900;
    letter-spacing: 0.12em;
    border-radius: 12px;
    border: 2px solid transparent;
}
</style>
</head>
<body>

<div class="title">Juice Battle</div>

<div id="winner-banner" class="winner-banner" style="display:none"></div>

<div class="scoreboard">
  <div class="jar jar-0">
    <div class="badge badge-hidden" id="badge-0">&nbsp;</div>
    <div class="badge badge-disconnected" id="ble-badge-0" style="display:none">RECONNECTING...</div>
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

  <div class="vs-col">
    <div class="vs">VS</div>
    <button id="game-over-btn" class="game-over-btn" onclick="gameOver()">GAME OVER</button>
  </div>

  <div class="jar jar-1">
    <div class="badge badge-hidden" id="badge-1">&nbsp;</div>
    <div class="badge badge-disconnected" id="ble-badge-1" style="display:none">RECONNECTING...</div>
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

    if (data.ble_status) {
        [0, 1].forEach(function(n) {
            setBleStatus(n, data.ble_status[String(n)] || 'connected');
        });
    }

    var gameOver = data.game_over;
    var winner   = data.winner;
    var banner   = el('winner-banner');
    var goBtn    = el('game-over-btn');
    if (gameOver) {
        goBtn.disabled = true;
        banner.style.display = 'block';
        if (winner === 0 || winner === '0') {
            banner.textContent = 'JAR 0 WINS!';
            banner.style.color      = '#66bb6a';
            banner.style.background = '#0d1a0d';
            banner.style.borderColor = '#2e7d32';
        } else if (winner === 1 || winner === '1') {
            banner.textContent = 'JAR 1 WINS!';
            banner.style.color      = '#42a5f5';
            banner.style.background = '#0a0f1e';
            banner.style.borderColor = '#1565c0';
        } else {
            banner.textContent = "IT'S A DRAW!";
            banner.style.color      = '#ffffff';
            banner.style.background = '#1a1a1a';
            banner.style.borderColor = '#555555';
        }
    } else {
        goBtn.disabled = false;
        banner.style.display = 'none';
    }
});

socket.on('node_status_update', (data) => {
    setBleStatus(data.node_id, data.status);
});

function setBleStatus(n, status) {
    document.getElementById('ble-badge-' + n).style.display = (status === 'disconnected') ? 'block' : 'none';
}

function resetJar(n) {
  fetch('/reset/' + n, {method: 'POST'})
    .then(r => r.json())
    .then(d => { if (!d.ok) console.error('reset failed', d); });
}

function gameOver() {
  fetch('/game_over', {method: 'POST'})
    .then(r => r.json())
    .then(d => { if (!d.ok) console.error('game_over failed', d); });
}
</script>

</body>
</html>"""


HTML_V2 = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Juice Battle — Live</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: #000;
    color: #fff;
    font-family: 'Arial Black', Arial, sans-serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    user-select: none;
}
#main-wrap {
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
}
.brandband {
    background: #fff;
    border-bottom: 3px solid #c67b3f;
    padding: 12px 20px;
    text-align: center;
    position: relative;
    flex-shrink: 0;
}
.brandband-controls {
    position: absolute;
    top: 14px;
    right: 16px;
    display: flex;
    gap: 5px;
}
.subline-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 8px 16px 4px;
    flex-shrink: 0;
}
.subline-title {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 5px;
    color: #3f3f3f;
    text-transform: uppercase;
}
.subline-sep { color: #1e1e1e; }
.subline-count {
    font-size: 19px;
    font-weight: 800;
    color: #c67b3f;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}
.subline-label {
    font-size: 7px;
    letter-spacing: 1.6px;
    color: #333;
    text-transform: uppercase;
}
.sound-btn {
    background: transparent;
    border: 1px solid #ccc;
    color: #666;
    font-size: 14px;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    line-height: 1;
}
.game-over-btn {
    background: #b84800;
    border: none;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
}
.game-over-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.main-grid {
    display: grid;
    grid-template-columns: 1fr 380px 1fr;
    gap: 20px;
    max-width: 1800px;
    margin: 0 auto;
    padding: 8px 60px;
    align-items: start;
    flex: 1;
}
.card {
    display: flex;
    flex-direction: column;
    min-height: 520px;
    padding: 20px 18px 16px;
    border-radius: 14px;
    position: relative;
    overflow: hidden;
}
.node-label { font-size: 11px; color: #444; text-transform: uppercase; letter-spacing: 2px; flex-shrink: 0; margin-bottom: 12px; }
.band-row { display: flex; align-items: center; gap: 24px; flex: 1; }
.card-1 .band-row { flex-direction: row-reverse; }
.jar-box { flex-shrink: 0; }
.stack {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
}
.share-pct { font-size: 14px; color: #4a4a4a; letter-spacing: 1px; text-transform: uppercase; }
.bottom { flex-shrink: 0; margin-top: 14px; display: flex; flex-direction: column; align-items: center; gap: 5px; width: 100%; }
.jar-svg { width: 150px; height: 250px; flex-shrink: 0; }
.jar-liquid { transition: height 0.6s ease, y 0.6s ease; }
.feed-panel {
    background: #080808; border: 1px solid #1a1a1a; border-radius: 12px;
    padding: 14px 14px; margin-top: 12px; width: 100%;
    flex: 1; min-height: 200px; display: flex; flex-direction: column;
}
.feed-header { font-size: 11px; letter-spacing: 2px; color: #444; text-transform: uppercase; margin-bottom: 8px; flex-shrink: 0; }
#feed-rows { flex: 1; }
.feed-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid #111; }
.feed-row:last-child { border-bottom: none; }
.feed-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.feed-text { font-size: 14px; color: #888; font-family: monospace, 'Courier New'; flex: 1; line-height: 1.3; }
.feed-time { font-size: 11px; color: #444; white-space: nowrap; }
.ticker-served-num {
    color: #e08c45;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: 0;
    vertical-align: middle;
    margin-right: 4px;
}
.ticker-bar {
    background: #0e0e12; border-top: 2px solid #2a2a2a;
    display: flex; align-items: center; gap: 0;
    overflow: hidden; flex-shrink: 0;
}
.ticker-mid { flex: 1; overflow: hidden; padding: 10px 0; }
.ticker-track { display: flex; width: max-content; animation: ticker-scroll 40s linear infinite; }
.ticker-item { white-space: nowrap; padding: 0 28px; font-size: 15px; font-weight: 500; letter-spacing: 1.4px;
               color: #9a9a9a; text-transform: uppercase; font-family: monospace, 'Courier New'; }
.ticker-sep { color: #3a3a3a; padding: 0 4px; }
.ticker-right {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 20px; flex-shrink: 0;
    border-left: 1px solid #181818;
    font-size: 13px; font-weight: 600; color: #b8b8b8; text-transform: uppercase; letter-spacing: 1px;
    min-width: 240px;
}
@keyframes ticker-scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.card-0 { background: #0d1508; border: 2px solid #4a6a1a; }
.card-1 { background: #150a12; border: 2px solid #7a2a4a; }
.char-svg {
    width: 150px;
    height: 150px;
    animation: bob 3s ease-in-out infinite;
    flex-shrink: 0;
}
.char-svg.excited     { animation: bob 1.4s ease-in-out infinite; }
.char-svg.celebrating { animation: celebrate 0.7s ease-in-out; }
#lemon-eyes, #melon-eyes {
    transform-box: fill-box;
    transform-origin: center;
}
.eyes-wide      { transform: scale(1.15); }
.watching-right { animation: watch-right 1.6s ease-in-out infinite !important; }
.watching-left  { animation: watch-left  1.6s ease-in-out infinite !important; }
.glance-right   { animation: glance-right 1.6s ease-in-out !important; }
.glance-left    { animation: glance-left  1.6s ease-in-out !important; }
.persona-name {
    font-size: 38px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
}
.card-0 .persona-name { color: #b8e83a; }
.card-1 .persona-name { color: #ff5f8f; }
.glass-count {
    font-size: 130px;
    font-weight: 800;
    line-height: 0.85;
    font-variant-numeric: tabular-nums;
    display: inline-block;
}
.card-0 .glass-count { color: #b8e83a; }
.card-1 .glass-count { color: #ff5f8f; }
.glass-count.digit-swap { animation: digit-swap 0.5s ease-in-out forwards; }
.glass-count.numpop     { animation: numpop 0.5s ease-out; }
.glasses-label {
    font-size: 13px;
    color: #444;
    text-transform: uppercase;
    letter-spacing: 2px;
}
.progress-bar {
    width: 100%;
    height: 4px;
    background: #131313;
    border-radius: 2px;
    overflow: hidden;
    margin: 4px 0;
}
.progress-fill {
    height: 100%;
    border-radius: 2px;
    width: 0%;
    transition: width 0.5s ease;
}
.card-0 .progress-fill { background: #7ab52a; }
.card-1 .progress-fill { background: #c84070; }
.pour-label {
    font-size: 10px;
    color: #3a3a3a;
    height: 16px;
    text-align: center;
}
.streak-badge {
    display: none;
    background: #1a1400;
    border: 1px solid #5a4400;
    color: #e8b830;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
}
.reset-btn {
    background: transparent;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    color: #666;
    font-size: 12px;
    text-transform: uppercase;
    padding: 12px 24px;
    cursor: pointer;
    letter-spacing: 2px;
    font-family: 'Arial Black', Arial, sans-serif;
}
.reset-btn:hover { border-color: #444; color: #999; }
.vs-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    align-self: stretch;
    padding-top: 50px;
}
.vs-text { font-size: 24px; font-weight: 800; color: #282828; }
.lead-pill {
    font-size: 10px;
    font-weight: 700;
    padding: 5px 10px;
    border-radius: 20px;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 1px;
    border: 1px solid #2a2a2a;
    background: #1a1a1a;
    color: #3a3a3a;
}
.status-dot {
    width: 7px;
    height: 7px;
    background: #2a8a2a;
    border-radius: 50%;
    display: inline-block;
    animation: glowpulse 1.6s ease-in-out infinite;
    flex-shrink: 0;
}
.status-dot.disconnected { background: #e8b830; }
.node-warning { color: #e8b830; }
@keyframes bob {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-5px); }
}
@keyframes celebrate {
    0%   { transform: scale(1) rotate(0deg); }
    25%  { transform: scale(1.16) rotate(-9deg); }
    50%  { transform: scale(1.16) rotate(9deg); }
    75%  { transform: scale(1.08) rotate(-6deg); }
    100% { transform: scale(1) rotate(0deg); }
}
@keyframes watch-right {
    0%, 30%  { transform: translateX(0); }
    40%, 60% { transform: translateX(8px); }
    70%, 100%{ transform: translateX(0); }
}
@keyframes watch-left {
    0%, 30%  { transform: translateX(0); }
    40%, 60% { transform: translateX(-8px); }
    70%, 100%{ transform: translateX(0); }
}
@keyframes glance-right {
    0%, 20%  { transform: translateX(0); }
    30%, 50% { transform: translateX(8px); }
    60%, 100%{ transform: translateX(0); }
}
@keyframes glance-left {
    0%, 20%  { transform: translateX(0); }
    30%, 50% { transform: translateX(-8px); }
    60%, 100%{ transform: translateX(0); }
}
@keyframes numpop {
    0%   { transform: scale(1); }
    40%  { transform: scale(1.22); }
    100% { transform: scale(1); }
}
@keyframes digit-swap {
    0%   { transform: translateY(0);     opacity: 1; }
    40%  { transform: translateY(-30px); opacity: 0; }
    41%  { transform: translateY(30px);  opacity: 0; }
    100% { transform: translateY(0);     opacity: 1; }
}
@keyframes floatup {
    0%   { opacity: 0; transform: translateX(-50%) translateY(0); }
    15%  { opacity: 1; transform: translateX(-50%) translateY(-8px); }
    85%  { opacity: 1; transform: translateX(-50%) translateY(-34px); }
    100% { opacity: 0; transform: translateX(-50%) translateY(-42px); }
}
@keyframes confetti-fall {
    0%   { transform: translateY(0) rotate(0deg); opacity: 1; }
    100% { transform: translateY(400px) rotate(720deg); opacity: 0; }
}
@keyframes glowpulse {
    0%, 100% { opacity: 0.35; }
    50%      { opacity: 1; }
}
@keyframes look-cycle-left {
    0%, 20%   { transform: translate(8px, 0); }
    25%, 45%  { transform: translate(0, 0); }
    50%, 70%  { transform: translate(0, 5px); }
    75%, 100% { transform: translate(0, 0); }
}
@keyframes look-cycle-right {
    0%, 20%   { transform: translate(-8px, 0); }
    25%, 45%  { transform: translate(0, 0); }
    50%, 70%  { transform: translate(0, 5px); }
    75%, 100% { transform: translate(0, 0); }
}
@keyframes area-zoom {
    0%   { transform: scale(1); }
    30%  { transform: scale(1.18); }
    100% { transform: scale(1); }
}
.char-wrap { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.char-wrap.area-zoom { animation: area-zoom 0.6s ease-out forwards; }
.look-cycle-left  { animation: look-cycle-left  4.8s ease-in-out infinite !important; }
.look-cycle-right { animation: look-cycle-right 4.8s ease-in-out infinite !important; }
#winner-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.96);
    z-index: 100;
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
#overlay-logo { margin-bottom: 28px; }
#overlay-char {
    width: 160px;
    height: 160px;
    animation: celebrate 0.7s ease-in-out infinite;
    flex-shrink: 0;
}
#overlay-name {
    font-size: 52px;
    font-weight: 800;
    letter-spacing: 8px;
    text-transform: uppercase;
    text-align: center;
    margin-top: 20px;
}
#overlay-sub {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 8px;
    color: #c67b3f;
    margin-top: 10px;
    text-transform: uppercase;
}
#overlay-score {
    font-size: 13px;
    color: #555;
    letter-spacing: 2px;
    margin-top: 12px;
    text-transform: uppercase;
}
#overlay-rule {
    border: none;
    border-top: 1px solid #c67b3f;
    width: 200px;
    margin: 24px auto;
}
#overlay-brand {
    font-size: 10px;
    letter-spacing: 4px;
    color: #c67b3f;
    text-transform: uppercase;
}
    50%      { text-shadow: 0 0 40px rgba(198,123,63,0.55); }
}
</style>
</head>
<body>

<div id="winner-overlay">
    <div id="overlay-logo">
        <img src="/static/dharanova_logo.png" style="height:70px; width:auto;">
    </div>
    <svg id="overlay-char" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"></svg>
    <img id="overlay-draw-logo" src="/static/dharanova_logo.png" style="height:120px; width:auto; display:none; margin-bottom:10px;">
    <div id="overlay-name"></div>
    <div id="overlay-sub">CHAMPION</div>
    <div id="overlay-score"></div>
    <hr id="overlay-rule">
    <div id="overlay-brand">DHARANOVA · GROUNDED INNOVATION</div>
</div>

<div id="main-wrap">

<div class="brandband">
    <img src="/static/dharanova_logo.png" style="height:44px; width:auto; display:block; margin:0 auto;">
    <div class="brandband-controls">
        <button id="sound-btn" class="sound-btn" onclick="toggleSound()">🔊</button>
        <button id="game-over-btn" class="game-over-btn" onclick="triggerGameOver()">GAME OVER</button>
    </div>
</div>

<div class="subline-row">
    <span class="subline-title">JUICE BATTLE</span>
</div>

<div class="main-grid">

    <div class="card card-0" id="card-0">
        <div class="node-label">NODE A &middot; JAR 0</div>
        <div class="band-row">
            <div class="jar-box">
                <svg class="jar-svg" viewBox="0 0 90 150" xmlns="http://www.w3.org/2000/svg">
                    <rect x="26" y="3" width="38" height="13" rx="4" fill="#c8c8c8"/>
                    <rect x="6" y="16" width="78" height="130" rx="14" fill="none" stroke="#7ab52a" stroke-width="3"/>
                    <rect id="jar-liquid-0" x="10" y="20" width="70" height="122" rx="11" fill="#b8e83a" opacity="0.92" class="jar-liquid"/>
                    <line id="jar-surface-0" x1="10" y1="20" x2="80" y2="20" stroke="#d8f86a" stroke-width="2.5"/>
                </svg>
            </div>
            <div class="stack">
                <div class="char-wrap" id="char-wrap-0">
                <svg id="char-0" class="char-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                    <ellipse cx="50" cy="55" rx="33" ry="37" fill="#E8D830"/>
                    <ellipse cx="50" cy="55" rx="33" ry="37" fill="none" stroke="#C2B01E" stroke-width="2"/>
                    <path d="M50 18 Q55 9 61 13" stroke="#5a8a20" stroke-width="4" fill="none" stroke-linecap="round"/>
                    <g id="lemon-eyes">
                        <ellipse cx="38" cy="47" rx="5" ry="7" fill="#2a2a10"/>
                        <ellipse cx="62" cy="47" rx="5" ry="7" fill="#2a2a10"/>
                        <circle cx="39.5" cy="44.5" r="1.8" fill="#fff"/>
                        <circle cx="63.5" cy="44.5" r="1.8" fill="#fff"/>
                    </g>
                    <path id="lemon-mouth" d="M42 66 Q50 72 58 66" stroke="#2a2a10" stroke-width="3.5" fill="none" stroke-linecap="round"/>
                    <g id="lemon-blush" opacity="0">
                        <ellipse cx="26" cy="59" rx="6" ry="4" fill="#F09090"/>
                        <ellipse cx="74" cy="59" rx="6" ry="4" fill="#F09090"/>
                    </g>
                </svg>
                </div>
                <div class="persona-name">LEMON WARRIOR</div>
                <div class="glass-count" id="count-0">0</div>
                <div class="glasses-label">GLASSES</div>
                <div class="share-pct" id="share-0">&nbsp;</div>
                <div class="streak-badge" id="streak-0"></div>
            </div>
        </div>
        <div class="bottom">
            <div class="progress-bar"><div class="progress-fill" id="progress-0"></div></div>
            <div class="pour-label" id="pour-label-0">&nbsp;</div>
            <button class="reset-btn" onclick="resetJar(0)">RESET</button>
        </div>
    </div>

    <div class="vs-col">
        <div class="vs-text">VS</div>
        <div class="lead-pill" id="lead-pill">TIED</div>
        <div class="feed-panel">
            <div class="feed-header">LIVE POUR FEED</div>
            <div id="feed-rows"><div class="feed-row"><span class="feed-text" style="color:#333">Waiting for first pour…</span></div></div>
        </div>
    </div>

    <div class="card card-1" id="card-1">
        <div class="node-label">NODE B &middot; JAR 1</div>
        <div class="band-row">
            <div class="jar-box">
                <svg class="jar-svg" viewBox="0 0 90 150" xmlns="http://www.w3.org/2000/svg">
                    <rect x="26" y="3" width="38" height="13" rx="4" fill="#c8c8c8"/>
                    <rect x="6" y="16" width="78" height="130" rx="14" fill="none" stroke="#c84070" stroke-width="3"/>
                    <rect id="jar-liquid-1" x="10" y="20" width="70" height="122" rx="11" fill="#ff5f8f" opacity="0.92" class="jar-liquid"/>
                    <line id="jar-surface-1" x1="10" y1="20" x2="80" y2="20" stroke="#ff9fb8" stroke-width="2.5"/>
                </svg>
            </div>
            <div class="stack">
                <div class="char-wrap" id="char-wrap-1">
                <svg id="char-1" class="char-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="50" cy="50" r="38" fill="#3a8a30"/>
                    <circle cx="50" cy="50" r="33" fill="#EAF3DE"/>
                    <circle cx="50" cy="50" r="29" fill="#E8406A"/>
                    <g id="melon-eyes">
                        <ellipse cx="40" cy="48" rx="6" ry="7.5" fill="#fff"/>
                        <ellipse cx="60" cy="48" rx="6" ry="7.5" fill="#fff"/>
                        <circle cx="40" cy="48" r="3.5" fill="#1f0c0c"/>
                        <circle cx="60" cy="48" r="3.5" fill="#1f0c0c"/>
                        <circle cx="41.4" cy="46.2" r="1.3" fill="#fff"/>
                        <circle cx="61.4" cy="46.2" r="1.3" fill="#fff"/>
                    </g>
                    <path id="melon-mouth" d="M42 64 Q50 70 58 64" stroke="#1f0c0c" stroke-width="3" fill="none" stroke-linecap="round"/>
                    <g id="melon-blush" opacity="0">
                        <ellipse cx="28" cy="56" rx="6" ry="4" fill="#FF9090"/>
                        <ellipse cx="72" cy="56" rx="6" ry="4" fill="#FF9090"/>
                    </g>
                </svg>
                </div>
                <div class="persona-name">MELON CRUSHER</div>
                <div class="glass-count" id="count-1">0</div>
                <div class="glasses-label">GLASSES</div>
                <div class="share-pct" id="share-1">&nbsp;</div>
                <div class="streak-badge" id="streak-1"></div>
            </div>
        </div>
        <div class="bottom">
            <div class="progress-bar"><div class="progress-fill" id="progress-1"></div></div>
            <div class="pour-label" id="pour-label-1">&nbsp;</div>
            <button class="reset-btn" onclick="resetJar(1)">RESET</button>
        </div>
    </div>

</div>

</div>

<div class="ticker-bar">
    <div class="ticker-mid">
        <div class="ticker-track" id="ticker-track">
            <span class="ticker-item ticker-served"><span class="ticker-served-num" id="t-served">0</span> IOT ENTHUSIASTS SERVED</span>
            <span class="ticker-sep">&nbsp;&nbsp;&nbsp;&middot;&nbsp;&nbsp;&nbsp;</span>
            <span class="ticker-item">BUILT BY DHARANOVA — GROUNDED INNOVATION</span>
            <span class="ticker-sep">&nbsp;&nbsp;&nbsp;&middot;&nbsp;&nbsp;&nbsp;</span>
            <span class="ticker-item ticker-served"><span class="ticker-served-num" id="t-served2">0</span> IOT ENTHUSIASTS SERVED</span>
            <span class="ticker-sep">&nbsp;&nbsp;&nbsp;&middot;&nbsp;&nbsp;&nbsp;</span>
            <span class="ticker-item">BUILT BY DHARANOVA — GROUNDED INNOVATION</span>
            <span class="ticker-sep">&nbsp;&nbsp;&nbsp;&middot;&nbsp;&nbsp;&nbsp;</span>
        </div>
    </div>
    <div class="ticker-right">
        <span class="status-dot" id="status-dot"></span>
        <span id="status-text">CONNECTING...</span>
    </div>
</div>

<script src="/static/socket.io.js"></script>
<script>
const socket = io();

const sounds = {
    glass:   new Audio('/static/sounds/glass.mp3'),
    pour:    new Audio('/static/sounds/pour.mp3'),
    fanfare: new Audio('/static/sounds/fanfare.mp3'),
    cheer:   new Audio('/static/sounds/cheer.mp3')
};
sounds.pour.loop = true;
Object.values(sounds).forEach(s => { s.preload = 'auto'; s.load(); });

let soundEnabled    = true;
let audioUnlocked   = false;
let initialized     = false;
let gameOverHandled = false;
let pourFadeTimer   = null;      // setInterval id; guard against overlapping fades

const pouringNodes = new Set();  // nodes with partial_g currently increasing
const prevCount    = {'0': 0, '1': 0};
const prevPartial  = {'0': 0, '1': 0};
const idleCount    = {'0': 0, '1': 0};
const streak       = {'0': 0, '1': 0};
const IDLE_AFTER   = 3;
const JAR_CAPACITY_G = 5000; // estimate — should move to config.py later

const feedEvents     = [];        // [{text, color, ts}] newest-first, max 5
let   minPourSec     = null;      // fastest pour duration seen this session
const pourStartTs    = {'0': 0, '1': 0};
const prevPourActive = {'0': false, '1': false};
let   lastBleStatus  = {};        // detect connect/disconnect transitions

// Unlock Chromium kiosk autoplay on first interaction
document.addEventListener('click', function() {
    if (!audioUnlocked) {
        sounds.glass.play().catch(() => {});
        sounds.glass.pause();
        sounds.glass.currentTime = 0;
        audioUnlocked = true;
    }
}, { once: true });

function stopAllSounds() {
    if (pourFadeTimer !== null) { clearInterval(pourFadeTimer); pourFadeTimer = null; }
    Object.values(sounds).forEach(s => { s.pause(); s.currentTime = 0; s.volume = 1; });
    pouringNodes.clear();
}

function playSound(name) {
    if (!soundEnabled) return;
    try {
        const snd = sounds[name];
        snd.pause();
        snd.currentTime = 0;
        snd.play().catch(e => console.log('audio:', e));
    } catch(e) { console.log('sound error:', e); }
}

function startPour() {
    if (!soundEnabled || !sounds.pour.paused) return;
    if (pourFadeTimer !== null) {
        clearInterval(pourFadeTimer);
        pourFadeTimer = null;
        sounds.pour.volume = 1;
    }
    try {
        sounds.pour.currentTime = 0;
        sounds.pour.play().catch(e => console.log('audio:', e));
    } catch(e) { console.log('sound error:', e); }
}

function fadeOutPour() {
    const s = sounds.pour;
    if (s.paused) return;
    if (pourFadeTimer !== null) {
        clearInterval(pourFadeTimer);
        pourFadeTimer = null;
        s.volume = 1;
    }
    const steps = 10, interval = 15;
    let i = 0;
    pourFadeTimer = setInterval(() => {
        i++;
        s.volume = 1 - i / steps;
        if (i >= steps) {
            clearInterval(pourFadeTimer);
            pourFadeTimer = null;
            s.pause();
            s.currentTime = 0;
            s.volume = 1;
        }
    }, interval);
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    el('sound-btn').textContent = soundEnabled ? '🔊' : '🔇';
    if (!soundEnabled) stopAllSounds();
}

// ── Character state machine ────────────────────────────────────────────────
const CHAR = {
    '0': { name: 'lemon', watchCls: 'watching-right' },
    '1': { name: 'melon', watchCls: 'watching-left'  }
};
const CHAR_MOUTH = {
    '0': {
        neutral: 'M42 66 Q50 72 58 66',
        excited: 'M38 62 Q50 78 62 62',
        grin:    'M30 63 Q50 84 70 63'
    },
    '1': {
        neutral: 'M42 64 Q50 70 58 64',
        excited: 'M38 60 Q50 76 62 60',
        grin:    'M38 62 Q50 70 62 62'
    }
};
const celebrating = {'0': false, '1': false};

function setCharState(jarN, state) {
    const ns    = String(jarN);
    const ch    = CHAR[ns];
    const svg   = el('char-' + ns);
    const eyes  = el(ch.name + '-eyes');
    const mouth = el(ch.name + '-mouth');
    const blush = el(ch.name + '-blush');

    svg.classList.remove('excited', 'celebrating');
    if (eyes) eyes.classList.remove(
        'eyes-wide', 'watching-right', 'watching-left', 'glance-right', 'glance-left',
        'look-cycle-left', 'look-cycle-right'
    );

    switch (state) {
        case 'idle':
            celebrating[ns] = false;
            if (mouth) mouth.setAttribute('d', CHAR_MOUTH[ns].neutral);
            if (blush) blush.setAttribute('opacity', '0');
            if (eyes) eyes.classList.add(ns === '0' ? 'look-cycle-left' : 'look-cycle-right');
            break;
        case 'excited':
            svg.classList.add('excited');
            if (eyes) eyes.classList.add('eyes-wide');
            if (mouth) mouth.setAttribute('d', CHAR_MOUTH[ns].excited);
            break;
        case 'watching':
            if (mouth) mouth.setAttribute('d', CHAR_MOUTH[ns].neutral);
            if (eyes) eyes.classList.add(ch.watchCls);
            break;
        case 'celebrating':
            celebrating[ns] = true;
            void svg.offsetWidth;
            svg.classList.add('celebrating');
            setTimeout(() => svg.classList.remove('celebrating'), 700);
            if (blush) blush.setAttribute('opacity', '0.5');
            if (mouth) mouth.setAttribute('d', CHAR_MOUTH[ns].grin);
            setTimeout(() => {
                celebrating[ns] = false;
                svg.classList.remove('excited');
                if (eyes) eyes.classList.remove(
                    'eyes-wide', 'watching-right', 'watching-left',
                    'look-cycle-left', 'look-cycle-right'
                );
                if (eyes) eyes.classList.add(ns === '0' ? 'look-cycle-left' : 'look-cycle-right');
                if (blush) blush.setAttribute('opacity', '0');
                if (mouth) mouth.setAttribute('d', CHAR_MOUTH[ns].neutral);
            }, 2000);
            break;
    }
}

// ── Utilities ──────────────────────────────────────────────────────────────
function el(id) { return document.getElementById(id); }

function showFloatLabel(cardId, text, color) {
    const card = el(cardId);
    const lbl  = document.createElement('div');
    lbl.textContent = text;
    lbl.style.cssText =
        'position:absolute;top:45%;left:50%;font-size:11px;font-weight:800;' +
        'letter-spacing:2px;pointer-events:none;color:' + color + ';' +
        'animation:floatup 1.8s ease-out forwards;z-index:10;white-space:nowrap;';
    card.appendChild(lbl);
    setTimeout(() => lbl.remove(), 1800);
}

function spawnConfetti(cardEl) {
    const colors = ['#E8D830','#7ab52a','#E8406A','#c67b3f','#fff'];
    for (let i = 0; i < 18; i++) {
        const bit = document.createElement('div');
        const c   = colors[Math.floor(Math.random() * colors.length)];
        bit.style.cssText =
            'position:absolute;width:6px;height:12px;background:' + c +
            ';left:' + (Math.random() * 100) + '%;top:-10px;opacity:1;' +
            'border-radius:1px;pointer-events:none;z-index:5;';
        bit.style.animation =
            'confetti-fall ' + (1.2 + Math.random() * 0.8) + 's ease-in forwards';
        bit.style.animationDelay = (Math.random() * 0.3) + 's';
        cardEl.appendChild(bit);
        setTimeout(() => bit.remove(), 2500);
    }
}

// ── Feed panel ─────────────────────────────────────────────────────────────
function addFeedEvent(text, color) {
    feedEvents.unshift({ text, color, ts: Date.now() });
    if (feedEvents.length > 5) feedEvents.pop();
    renderFeed();
}

function relTime(ts) {
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 5)  return 'now';
    if (s < 60) return s + 's';
    return Math.floor(s / 60) + 'm';
}

function renderFeed() {
    const rows = el('feed-rows');
    if (!rows) return;
    rows.innerHTML = feedEvents.map(e =>
        '<div class="feed-row">' +
        '<div class="feed-dot" style="background:' + e.color + '"></div>' +
        '<div class="feed-text">' + e.text + '</div>' +
        '<div class="feed-time">' + relTime(e.ts) + '</div>' +
        '</div>'
    ).join('');
}

setInterval(renderFeed, 5000);

// ── Jar fill ───────────────────────────────────────────────────────────────
function updateJarFill(n, count, vol) {
    const used         = count * vol;
    const fillFraction = Math.max(0, Math.min(1, 1 - used / JAR_CAPACITY_G));
    const h    = (122 * fillFraction).toFixed(1);
    const y    = (142 - 122 * fillFraction).toFixed(1);
    const liq  = el('jar-liquid-' + n);
    const surf = el('jar-surface-' + n);
    if (liq)  { liq.setAttribute('height', h); liq.setAttribute('y', y); }
    if (surf) { surf.setAttribute('y1', y); surf.setAttribute('y2', y); }
}

// ── Ticker stats ───────────────────────────────────────────────────────────
function updateTicker(c0, c1, totalServed) {
    ['', '2'].forEach(sfx => {
        const sn = el('t-served' + sfx);
        if (sn) sn.textContent = String(totalServed);
    });
}

socket.on('connect',    () => { el('status-text').textContent = 'CONNECTED'; });
socket.on('disconnect', () => { el('status-text').textContent = 'RECONNECTING...'; });

socket.on('state', (data) => {
    const gc  = data.glass_count    || {};
    const pg  = data.partial_g      || {};
    const vol = data.glass_volume_g || 150;


    // Seed prevCount from first push — avoids spurious score events on load
    if (!initialized) {
        prevCount['0']   = gc['0'] ?? 0;
        prevCount['1']   = gc['1'] ?? 0;
        prevPartial['0'] = pg['0'] ?? 0;
        prevPartial['1'] = pg['1'] ?? 0;
        el('count-0').textContent = String(prevCount['0']);
        el('count-1').textContent = String(prevCount['1']);
        initialized = true;
    }

    // ── Pour activity → character states ──
    const p0Inc = (pg['0'] ?? 0) > prevPartial['0'];
    const p1Inc = (pg['1'] ?? 0) > prevPartial['1'];

    // Track pour start time for fastest-pour stat
    if (p0Inc && !prevPourActive['0']) pourStartTs['0'] = Date.now();
    if (p1Inc && !prevPourActive['1']) pourStartTs['1'] = Date.now();
    prevPourActive['0'] = p0Inc;
    prevPourActive['1'] = p1Inc;

    // Per-node pour tracking: start shared loop when first node begins, fade when last stops
    if (p0Inc && !pouringNodes.has('0')) {
        const wasEmpty = pouringNodes.size === 0;
        pouringNodes.add('0');
        if (wasEmpty) startPour();
    }
    if (p1Inc && !pouringNodes.has('1')) {
        const wasEmpty = pouringNodes.size === 0;
        pouringNodes.add('1');
        if (wasEmpty) startPour();
    }

    if (p0Inc || p1Inc) {
        idleCount['0'] = 0; idleCount['1'] = 0;
        if (!celebrating['0']) setCharState(0, 'excited');
        if (!celebrating['1']) setCharState(1, 'excited');
    } else {
        idleCount['0']++;
        idleCount['1']++;
        if (idleCount['0'] >= IDLE_AFTER) {
            if (!celebrating['0']) setCharState(0, 'idle');
            if (pouringNodes.has('0')) { pouringNodes.delete('0'); if (pouringNodes.size === 0) fadeOutPour(); }
        }
        if (idleCount['1'] >= IDLE_AFTER) {
            if (!celebrating['1']) setCharState(1, 'idle');
            if (pouringNodes.has('1')) { pouringNodes.delete('1'); if (pouringNodes.size === 0) fadeOutPour(); }
        }
    }
    prevPartial['0'] = pg['0'] ?? 0;
    prevPartial['1'] = pg['1'] ?? 0;

    // ── Per-node ──
    [0, 1].forEach(n => {
        const ns       = String(n);
        const newCount = gc[ns] ?? 0;
        const oldCount = prevCount[ns];

        const pgVal = pg[ns] ?? 0;
        const pct   = Math.min(100, (pgVal / vol) * 100).toFixed(1);
        el('progress-' + n).style.width = pct + '%';
        el('pour-label-' + n).innerHTML =
            pgVal > 1
                ? 'Last <b style="color:#5f5f5f">+' + pgVal.toFixed(0) + 'g</b>'
                : '&nbsp;';

        if (newCount > oldCount) {
            const loser      = 1 - n;
            const loserNs    = String(loser);
            const scoreColor = n === 0 ? '#b8e83a' : '#ff5f8f';
            const personaName = n === 0 ? 'LEMON WARRIOR' : 'MELON CRUSHER';

            // Record pour duration for ticker fastest-pour stat
            if (pourStartTs[ns] > 0) {
                const durSec = (Date.now() - pourStartTs[ns]) / 1000;
                if (minPourSec === null || durSec < minPourSec) minPourSec = durSec;
                pourStartTs[ns] = 0;
            }

            playSound('glass');

            // Winner: celebrate + area zoom (both one-shot)
            setCharState(n, 'celebrating');
            const wrapEl = el('char-wrap-' + n);
            if (wrapEl) {
                wrapEl.classList.remove('area-zoom');
                void wrapEl.offsetWidth;
                wrapEl.classList.add('area-zoom');
                setTimeout(() => wrapEl.classList.remove('area-zoom'), 600);
            }

            // Loser: one glance then idle
            setCharState(loser, 'idle');
            const loserEyes = el(CHAR[loserNs].name + '-eyes');
            if (loserEyes) {
                loserEyes.classList.remove('look-cycle-left', 'look-cycle-right');
                const glanceCls = (loser === 0) ? 'glance-right' : 'glance-left';
                void loserEyes.offsetWidth;
                loserEyes.classList.add(glanceCls);
                setTimeout(() => {
                    loserEyes.classList.remove(glanceCls);
                    loserEyes.classList.add(loser === 0 ? 'look-cycle-left' : 'look-cycle-right');
                }, 1600);
            }

            // Animated digit swap (one-shot)
            const countEl = el('count-' + n);
            countEl.classList.remove('digit-swap', 'numpop');
            void countEl.offsetWidth;
            countEl.classList.add('digit-swap');
            setTimeout(() => { countEl.textContent = String(newCount); }, 200);
            setTimeout(() => {
                countEl.classList.remove('digit-swap');
                void countEl.offsetWidth;
                countEl.classList.add('numpop');
                setTimeout(() => countEl.classList.remove('numpop'), 500);
            }, 500);

            spawnConfetti(el('card-' + n));
            showFloatLabel('card-' + n, '+1 GLASS', scoreColor);

            streak[ns]      = (streak[ns] || 0) + 1;
            streak[loserNs] = 0;
            const newStreak = streak[ns];
            if (newStreak >= 3 && newStreak % 2 === 1) {
                playSound('fanfare');
                addFeedEvent(personaName + ' is on a ' + newStreak + '-pour streak', '#e8b830');
            }
            addFeedEvent(personaName + ' poured glass #' + newCount, scoreColor);
        } else {
            el('count-' + n).textContent = String(newCount);
        }
        prevCount[ns] = newCount;

        updateJarFill(n, newCount, vol);

        const badge = el('streak-' + n);
        if (streak[ns] >= 2) {
            const fires = '🔥'.repeat(Math.min(streak[ns], 5));
            badge.textContent   = fires + ' ' + streak[ns] + '-POUR STREAK';
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    });

    // ── Share percentages + ticker ──
    const c0 = gc['0'] ?? 0;
    const c1 = gc['1'] ?? 0;
    {
        const total = c0 + c1;
        const p0 = total > 0 ? Math.round(c0 / total * 100) : 50;
        const p1 = 100 - p0;
        const s0 = el('share-0'); if (s0) s0.textContent = total > 0 ? p0 + '% OF ALL POURS' : ' ';
        const s1 = el('share-1'); if (s1) s1.textContent = total > 0 ? p1 + '% OF ALL POURS' : ' ';
        updateTicker(c0, c1, data.all_time_served ?? 0);
    }

    // ── Lead pill ──
    const pill = el('lead-pill');
    const pillBase = 'padding:5px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;';
    if (c0 > c1) {
        pill.textContent = 'LEMON LEADS';
        pill.style.cssText = pillBase + 'background:#0d1508;color:#b8e83a;border:1px solid #4a6a1a;';
    } else if (c1 > c0) {
        pill.textContent = 'MELON LEADS';
        pill.style.cssText = pillBase + 'background:#150a12;color:#ff5f8f;border:1px solid #7a2a4a;';
    } else {
        pill.textContent = 'TIED';
        pill.style.cssText = pillBase + 'background:#1a1a1a;color:#3a3a3a;border:1px solid #2a2a2a;';
    }

    // ── BLE status ──
    const bleStatus = data.ble_status || {};
    const warnings  = [];
    [0, 1].forEach(n => {
        const ns  = String(n);
        const cur = bleStatus[ns] || 'connected';
        const prv = lastBleStatus[ns] || 'connected';
        if (cur !== prv) {
            if (cur === 'disconnected') addFeedEvent('JAR ' + n + ' disconnected', '#e8b830');
            else                        addFeedEvent('JAR ' + n + ' reconnected',  '#7ab52a');
        }
        if (cur === 'disconnected') warnings.push('JAR ' + n + ' RECONNECTING');
    });
    lastBleStatus = Object.assign({}, bleStatus);
    if (warnings.length === 0) {
        el('status-dot').className    = 'status-dot';
        el('status-text').textContent = 'BOTH NODES CONNECTED';
    } else {
        el('status-dot').className  = 'status-dot disconnected';
        el('status-text').innerHTML = warnings
            .map(w => '<span class="node-warning">' + w + '</span>')
            .join(' &middot; ');
    }

    // ── Game over ──
    if (data.game_over && !gameOverHandled) {
        gameOverHandled = true;
        handleGameOver(data.winner);
    }
    if (!data.game_over) {
        gameOverHandled              = false;
        el('game-over-btn').disabled = false;
    }
});

function handleGameOver(winner) {
    playSound('fanfare');
    setTimeout(() => {
        playSound('cheer');
        // Cap cheer at 4s regardless of file length
        setTimeout(() => { sounds.cheer.pause(); sounds.cheer.currentTime = 0; }, 4000);
    }, 1500);
    el('game-over-btn').disabled = true;

    const w = String(winner);
    let name, color, isDraw;
    if (w === '0')      { name = 'LEMON WARRIOR'; color = '#b8e83a'; isDraw = false; }
    else if (w === '1') { name = 'MELON CRUSHER';  color = '#ff5f8f'; isDraw = false; }
    else                { name = "IT'S A DRAW";     color = '#c67b3f'; isDraw = true; }

    el('overlay-name').textContent = name;
    el('overlay-name').style.color = color;
    el('overlay-sub').style.display = isDraw ? 'none' : '';

    // Draw: show large logo in character slot; Win: clone winner SVG
    const destSvg    = el('overlay-char');
    const drawLogoEl = el('overlay-draw-logo');
    if (isDraw) {
        destSvg.style.display    = 'none';
        drawLogoEl.style.display = '';
        destSvg.innerHTML        = '';
    } else {
        destSvg.style.display    = '';
        drawLogoEl.style.display = 'none';
        const srcSvg = el('char-' + w);
        destSvg.innerHTML = srcSvg ? srcSvg.innerHTML : '';
    }

    // Score line
    const c0 = prevCount['0'], c1 = prevCount['1'];
    const [winG, loseG] = isDraw ? [c0, c1] : (w === '0' ? [c0, c1] : [c1, c0]);
    el('overlay-score').textContent =
        winG + ' GLASS' + (winG !== 1 ? 'ES' : '') +
        ' VS ' +
        loseG + ' GLASS' + (loseG !== 1 ? 'ES' : '');

    const overlay = el('winner-overlay');
    overlay.style.opacity    = '0';
    overlay.style.transition = '';
    overlay.style.display    = 'flex';
    void overlay.offsetWidth;
    overlay.style.transition = 'opacity 0.5s ease';
    overlay.style.opacity    = '1';

    setTimeout(() => {
        overlay.style.transition = 'opacity 0.8s ease';
        overlay.style.opacity    = '0';
        setTimeout(() => { overlay.style.display = 'none'; }, 800);
    }, 5000);
}

function resetJar(n) {
    fetch('/reset/' + n, { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            if (!d.ok) { console.error('reset failed', d); return; }
            streak['0'] = 0;  streak['1'] = 0;
            prevCount[String(n)] = 0;
            minPourSec = null;
            [0, 1].forEach(i => {
                const badge = el('streak-' + i);
                badge.style.display = 'none';
                badge.textContent   = '';
            });
            updateJarFill(n, 0, 150);
        });
}

function triggerGameOver() {
    fetch('/game_over', { method: 'POST' })
        .then(r => r.json())
        .then(d => { if (!d.ok) console.error('game_over failed', d); });
}
</script>
</body>
</html>"""

HTML_V3 = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Juice Battle — Live</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
    background: #000;
    color: #fff;
    font-family: 'Arial Black', Arial, sans-serif;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    user-select: none;
}
#bg-canvas {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
}
#main-wrap {
    position: relative; z-index: 2; width: 100%;
    flex: 1; display: flex; flex-direction: column; overflow: hidden;
}
/* TOP BAR */
.brandband {
    background: #fff; border-bottom: 3px solid #c67b3f;
    padding: 10px 20px; text-align: center;
    position: relative; flex-shrink: 0;
}
.brandband-controls { position: absolute; top: 12px; right: 16px; display: flex; gap: 5px; }
.sound-btn { background: transparent; border: 1px solid #ccc; color: #666; font-size: 14px; padding: 4px 8px; border-radius: 4px; cursor: pointer; line-height: 1; }
.game-over-btn { background: #b84800; border: none; color: #fff; font-size: 11px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; padding: 6px 14px; border-radius: 4px; cursor: pointer; }
.game-over-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.subline-row { display: flex; align-items: center; justify-content: center; padding: 6px 16px 3px; flex-shrink: 0; }
.subline-title { font-size: 11px; font-weight: 800; letter-spacing: 5px; color: #3f3f3f; text-transform: uppercase; }
/* 3-COL GRID */
.main-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; padding: 7px 18px 0; flex-shrink: 0; }
/* PLAYER CARDS */
.card { border-radius: 14px; padding: 14px 12px 10px; display: flex; flex-direction: column; position: relative; overflow: hidden; backdrop-filter: blur(2px); min-height: 0; }
.card-0 { background: rgba(13,21,8,0.88); border: 2px solid #4a6a1a; }
.card-1 { background: rgba(21,10,18,0.88); border: 2px solid #7a2a4a; }
@keyframes glow-lemon { 0%,100%{box-shadow:none} 40%{box-shadow:0 0 60px rgba(184,232,58,0.7),0 0 30px rgba(184,232,58,0.4) inset;border-color:#b8e83a;} }
@keyframes glow-melon { 0%,100%{box-shadow:none} 40%{box-shadow:0 0 60px rgba(255,95,143,0.7),0 0 30px rgba(255,95,143,0.4) inset;border-color:#ff5f8f;} }
.card-0.pouring { animation: glow-lemon 0.7s ease-out; }
.card-1.pouring { animation: glow-melon 0.7s ease-out; }
.node-label { font-size: 10px; color: #444; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 7px; flex-shrink: 0; }
.band-row { display: flex; align-items: center; gap: 10px; justify-content: center; flex: 1; }
.card-1 .band-row { flex-direction: row-reverse; }
.jar-box { flex-shrink: 0; }
.jar-svg { width: 80px; height: 135px; flex-shrink: 0; }
.jar-liquid { transition: height 0.6s ease, y 0.6s ease; }
.stack { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; }
.char-svg { width: 95px; height: 95px; animation: bob 3s ease-in-out infinite; flex-shrink: 0; }
.char-svg.excited     { animation: bob 1.4s ease-in-out infinite; }
.char-svg.celebrating { animation: celebrate 0.7s ease-in-out; }
#lemon-eyes, #melon-eyes { transform-box: fill-box; transform-origin: center; }
.eyes-wide      { transform: scale(1.15); }
.watching-right { animation: watch-right 1.6s ease-in-out infinite !important; }
.watching-left  { animation: watch-left  1.6s ease-in-out infinite !important; }
.glance-right   { animation: glance-right 1.6s ease-in-out !important; }
.glance-left    { animation: glance-left  1.6s ease-in-out !important; }
.persona-name { font-size: 19px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
.card-0 .persona-name { color: #b8e83a; }
.card-1 .persona-name { color: #ff5f8f; }
.glass-count { font-size: 75px; font-weight: 800; line-height: 0.85; font-variant-numeric: tabular-nums; display: inline-block; }
.card-0 .glass-count { color: #b8e83a; }
.card-1 .glass-count { color: #ff5f8f; }
.glass-count.digit-swap { animation: digit-swap 0.5s ease-in-out forwards; }
.glass-count.numpop     { animation: numpop 0.5s ease-out; }
.glasses-label { font-size: 10px; color: #444; text-transform: uppercase; letter-spacing: 2px; }
.share-pct { font-size: 11px; color: #4a4a4a; letter-spacing: 1px; text-transform: uppercase; }
.streak-badge { display: none; background: #1a1400; border: 1px solid #5a4400; color: #e8b830; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 20px; letter-spacing: 0.5px; }
.round-wins{font-size:0.7rem;letter-spacing:0.12em;color:#555;margin-top:4px;text-transform:uppercase;font-weight:600;}
.bottom { flex-shrink: 0; margin-top: 8px; display: flex; flex-direction: column; align-items: center; gap: 4px; width: 100%; }
.progress-bar { width: 100%; height: 4px; background: #131313; border-radius: 2px; overflow: hidden; margin: 2px 0; }
.progress-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
.card-0 .progress-fill { background: #7ab52a; }
.card-1 .progress-fill { background: #c84070; }
.pour-label { font-size: 10px; color: #3a3a3a; height: 14px; text-align: center; }
.reset-btn { background: transparent; border: 1px solid #2a2a2a; border-radius: 10px; color: #666; font-size: 11px; text-transform: uppercase; padding: 8px 20px; cursor: pointer; letter-spacing: 2px; font-family: 'Arial Black', Arial, sans-serif; }
.reset-btn:hover { border-color: #444; color: #999; }
/* CENTRE COLUMN */
.card-centre { background: rgba(8,8,8,0.82); border: 1px solid #1a1a1a; border-radius: 14px; padding: 10px; display: flex; flex-direction: column; gap: 6px; backdrop-filter: blur(2px); position: relative; }
.vs-col-top { text-align: center; }
.vs-text { font-size: 18px; font-weight: 800; color: #282828; }
.lead-pill { font-size: 10px; font-weight: 700; padding: 4px 10px; border-radius: 20px; text-align: center; text-transform: uppercase; letter-spacing: 1px; border: 1px solid #2a2a2a; background: #1a1a1a; color: #3a3a3a; align-self: center; margin-top: 4px; }
.feed-panel { background: #050505; border: 1px solid #111; border-radius: 8px; padding: 9px 10px; flex: 1; min-height: 0; overflow: hidden; }
.feed-header { display: flex; justify-content: space-between; align-items: center; font-size: 10px; letter-spacing: 2px; color: #444; text-transform: uppercase; margin-bottom: 6px; flex-shrink: 0; }
.live-badge { display: flex; align-items: center; gap: 4px; font-size: 9px; color: #3a3a3a; }
.live-dot-green { width: 6px; height: 6px; border-radius: 50%; background: #2a8a2a; animation: glowpulse 1.6s ease-in-out infinite; }
#feed-rows { flex: 1; }
.feed-row { display: flex; align-items: center; gap: 7px; padding: 4px 0; border-bottom: 1px solid #0d0d0d; }
.feed-row:last-child { border-bottom: none; }
.feed-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.feed-text { font-size: 12px; color: #888; font-family: monospace; flex: 1; line-height: 1.3; }
.feed-time { font-size: 11px; color: #444; white-space: nowrap; }
/* WELCOME BAND */
.welcome-band { margin: 7px 18px 0; padding: 9px 22px; background: linear-gradient(90deg,rgba(198,123,63,0.12),rgba(198,123,63,0.06),rgba(198,123,63,0.12)); border: 1px solid rgba(198,123,63,0.22); border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 14px; flex-shrink: 0; }
.welcome-icon { font-size: 15px; }
.welcome-text { font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #c67b3f; text-align: center; }
.welcome-sub { font-size: 9px; letter-spacing: 1.5px; color: #5a3a1a; text-align: center; margin-top: 2px; font-family: Arial,sans-serif; font-weight: 400; }
/* MARKETING ZONE */
.marketing-zone { margin: 7px 18px 0; border-radius: 12px; overflow: hidden; position: relative; flex: 1; min-height: 0; }
.mslide { position: absolute; inset: 0; padding: 14px 22px; display: flex; align-items: center; gap: 24px; opacity: 0; transition: opacity 1.4s ease; border-radius: 12px; }
.mslide.active { opacity: 1; }
.ms-water { background: linear-gradient(120deg,rgba(0,20,45,0.96),rgba(0,8,22,0.98),rgba(0,25,12,0.95)); border: 1px solid #0a2a40; }
.ms-india { background: linear-gradient(120deg,rgba(28,10,0,0.96),rgba(10,4,0,0.98),rgba(0,18,4,0.95)); border: 1px solid #2a1500; }
.ms-left { flex: 0 0 260px; display: flex; flex-direction: column; }
.ms-centre { flex: 1; display: flex; justify-content: center; align-items: center; }
.ms-right { flex: 0 0 240px; display: flex; flex-direction: column; gap: 7px; }
.ms-eyebrow { font-size: 9px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 6px; font-family: Arial,sans-serif; font-weight: 400; }
.ms-water .ms-eyebrow { color: #1a5070; }
.ms-india .ms-eyebrow { color: #5a3010; }
.ms-headline { font-size: 24px; font-weight: 800; line-height: 1.15; letter-spacing: 1px; text-transform: uppercase; }
.ms-water .ms-headline { color: #4db8ff; }
.ms-india .ms-headline { color: #ff9933; }
.ms-body { font-size: 11px; line-height: 1.6; margin-top: 6px; font-family: Arial,sans-serif; font-weight: 400; }
.ms-water .ms-body { color: #1a4a60; }
.ms-india .ms-body { color: #4a2a10; }
.ms-live-stat { margin-top: 9px; display: flex; align-items: baseline; gap: 6px; }
.ms-live-num { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; }
.ms-water .ms-live-num { color: #4db8ff; }
.ms-india .ms-live-num { color: #ff9933; }
.ms-live-lbl { font-size: 9px; letter-spacing: 1.5px; text-transform: uppercase; font-family: Arial,sans-serif; }
.ms-water .ms-live-lbl { color: #1a4a60; }
.ms-india .ms-live-lbl { color: #4a2a10; }
.ms-bar { height: 3px; border-radius: 2px; margin-top: 7px; background: #010f1a; overflow: hidden; }
.ms-bar-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg,#0066aa,#4db8ff); animation: barf 6s ease-in-out infinite alternate; }
@keyframes barf { from{width:10%} to{width:92%} }
.ms-stat { border-radius: 6px; padding: 8px 11px; }
.ms-water .ms-stat { background: rgba(0,28,58,0.8); border: 1px solid #0a3050; }
.ms-india .ms-stat { background: rgba(28,10,0,0.8); border: 1px solid #3a1a00; }
.ms-stat-val { font-size: 19px; font-weight: 800; line-height: 1; }
.ms-water .ms-stat-val { color: #4db8ff; }
.ms-india .ms-stat-val { color: #ff9933; }
.ms-stat-lbl { font-size: 9px; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 2px; font-family: Arial,sans-serif; }
.ms-water .ms-stat-lbl { color: #1a4a60; }
.ms-india .ms-stat-lbl { color: #4a2a10; }
.ms-badge { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; margin-top: auto; padding-top: 8px; border-top: 1px solid; font-family: Arial,sans-serif; }
.ms-water .ms-badge { color: #0a3050; border-color: #0a2030; }
.ms-water .ms-badge strong { color: #ff6b35; }
.ms-india .ms-badge { color: #3a1a00; border-color: #2a1000; }
.ms-india .ms-badge strong { color: #ff6b35; }
.india-stripe { width: 4px; height: 42px; border-radius: 2px; flex-shrink: 0; background: linear-gradient(to bottom,#ff9933 33%,#fff 33% 66%,#138808 66%); margin-right: 4px; margin-top: 2px; }
.slide-dots { position: absolute; bottom: 10px; right: 14px; display: flex; gap: 5px; }
.sdot { width: 6px; height: 6px; border-radius: 50%; background: #1a1a1a; transition: background 0.4s; }
.sdot.on { background: #ff6b35; }
/* TICKER */
.ticker-bar { background: #0a0a0e; border-top: 2px solid #ff6b35; display: flex; align-items: center; overflow: hidden; flex-shrink: 0; margin-top: 7px; }
.ticker-mid { flex: 1; overflow: hidden; padding: 9px 0; }
.ticker-track { display: flex; width: max-content; animation: ticker-scroll 40s linear infinite; }
.ticker-item { white-space: nowrap; padding: 0 18px; font-size: 15px; font-weight: 900; font-family: 'Arial Black',Arial,sans-serif; letter-spacing: 2px; color: #e8e8e8; text-transform: uppercase; }
.ticker-served-num { color: #ff9933; font-size: 20px; font-weight: 900; vertical-align: middle; margin-right: 4px; }
.ticker-sep { color: #ff6b35; padding: 0 5px; font-weight: 900; font-size: 16px; }
.ticker-grn { color: #b8e83a; font-weight: 900; }
.ticker-right { padding: 9px 18px; flex-shrink: 0; border-left: 1px solid #2a2a2a; font-size: 12px; font-weight: 800; color: #ccc; text-transform: uppercase; letter-spacing: 1px; min-width: 240px; display: flex; align-items: center; gap: 8px; font-family: 'Arial Black',Arial,sans-serif; }
@keyframes ticker-scroll { from{transform:translateX(0)} to{transform:translateX(-50%)} }
/* ANIMATIONS */
@keyframes bob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }
@keyframes celebrate { 0%{transform:scale(1) rotate(0deg)} 25%{transform:scale(1.16) rotate(-9deg)} 50%{transform:scale(1.16) rotate(9deg)} 75%{transform:scale(1.08) rotate(-6deg)} 100%{transform:scale(1) rotate(0deg)} }
@keyframes watch-right { 0%,30%{transform:translateX(0)} 40%,60%{transform:translateX(8px)} 70%,100%{transform:translateX(0)} }
@keyframes watch-left  { 0%,30%{transform:translateX(0)} 40%,60%{transform:translateX(-8px)} 70%,100%{transform:translateX(0)} }
@keyframes glance-right { 0%,20%{transform:translateX(0)} 30%,50%{transform:translateX(8px)} 60%,100%{transform:translateX(0)} }
@keyframes glance-left  { 0%,20%{transform:translateX(0)} 30%,50%{transform:translateX(-8px)} 60%,100%{transform:translateX(0)} }
@keyframes numpop { 0%{transform:scale(1)} 40%{transform:scale(1.22)} 100%{transform:scale(1)} }
@keyframes digit-swap { 0%{transform:translateY(0);opacity:1} 40%{transform:translateY(-30px);opacity:0} 41%{transform:translateY(30px);opacity:0} 100%{transform:translateY(0);opacity:1} }
@keyframes floatup { 0%{opacity:0;transform:translateX(-50%) translateY(0)} 15%{opacity:1;transform:translateX(-50%) translateY(-8px)} 85%{opacity:1;transform:translateX(-50%) translateY(-34px)} 100%{opacity:0;transform:translateX(-50%) translateY(-42px)} }
@keyframes confetti-fall { 0%{transform:translateY(0) rotate(0deg);opacity:1} 100%{transform:translateY(400px) rotate(720deg);opacity:0} }
@keyframes glowpulse { 0%,100%{opacity:0.35} 50%{opacity:1} }
@keyframes look-cycle-left  { 0%,20%{transform:translate(8px,0)} 25%,45%{transform:translate(0,0)} 50%,70%{transform:translate(0,5px)} 75%,100%{transform:translate(0,0)} }
@keyframes look-cycle-right { 0%,20%{transform:translate(-8px,0)} 25%,45%{transform:translate(0,0)} 50%,70%{transform:translate(0,5px)} 75%,100%{transform:translate(0,0)} }
@keyframes area-zoom { 0%{transform:scale(1)} 30%{transform:scale(1.18)} 100%{transform:scale(1)} }
.char-wrap { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.char-wrap.area-zoom { animation: area-zoom 0.6s ease-out forwards; }
.look-cycle-left  { animation: look-cycle-left  4.8s ease-in-out infinite !important; }
.look-cycle-right { animation: look-cycle-right 4.8s ease-in-out infinite !important; }
.ripple-ring { position: fixed; border-radius: 50%; pointer-events: none; z-index: 1; animation: ripple-expand 1.8s ease-out forwards; }
@keyframes ripple-expand { 0%{width:0;height:0;opacity:0.7;transform:translate(-50%,-50%)} 100%{width:700px;height:700px;opacity:0;transform:translate(-50%,-50%)} }
.status-dot { width: 8px; height: 8px; background: #2a8a2a; border-radius: 50%; display: inline-block; animation: glowpulse 1.6s ease-in-out infinite; flex-shrink: 0; }
.status-dot.disconnected { background: #e8b830; }
.node-warning { color: #e8b830; }
#winner-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.96); z-index: 100; display: none; flex-direction: column; align-items: center; justify-content: center; }
#overlay-logo { margin-bottom: 28px; }
#overlay-char { width: 160px; height: 160px; animation: celebrate 0.7s ease-in-out infinite; flex-shrink: 0; }
#overlay-name { font-size: 52px; font-weight: 800; letter-spacing: 8px; text-transform: uppercase; text-align: center; margin-top: 20px; }
#overlay-sub  { font-size: 16px; font-weight: 700; letter-spacing: 8px; color: #c67b3f; margin-top: 10px; text-transform: uppercase; }
#overlay-score { font-size: 13px; color: #555; letter-spacing: 2px; margin-top: 12px; text-transform: uppercase; }
#overlay-rule { border: none; border-top: 1px solid #c67b3f; width: 200px; margin: 24px auto; }
#overlay-brand { font-size: 10px; letter-spacing: 4px; color: #c67b3f; text-transform: uppercase; }
@keyframes drainBar { from{width:100%} to{width:0%} }
#round-over-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.93); border-radius: 14px; z-index: 10; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 9px; padding: 14px 12px; }
#ro-heading { font-size: 13px; font-weight: 700; letter-spacing: 4px; color: #c67b3f; text-transform: uppercase; text-align: center; }
.ro-score-row { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 0 6px; font-size: 14px; font-weight: 700; }
.ro-name0 { color: #b8e83a; }
.ro-name1 { color: #ff5f8f; }
.ro-val { color: #fff; font-size: 22px; font-weight: 800; }
#ro-winner { font-size: 14px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; text-align: center; color: #e8b830; margin-top: 2px; }
#ro-bar-wrap { width: 100%; height: 8px; background: #1a1a1a; border-radius: 4px; overflow: hidden; margin-top: 6px; }
#ro-bar { height: 100%; border-radius: 4px; background: #c67b3f; width: 100%; }
#round-begin-banner { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.93); border-radius: 14px; z-index: 11; display: none; flex-direction: column; align-items: center; justify-content: center; gap: 4px; }
#rb-number { font-size: 28px; font-weight: 800; letter-spacing: 6px; color: #c67b3f; text-transform: uppercase; text-align: center; }
#rb-begins { font-size: 13px; font-weight: 700; letter-spacing: 5px; color: #5a3a1a; text-transform: uppercase; }
</style>
</head>
<body>

<canvas id="bg-canvas"></canvas>

<div id="winner-overlay">
    <div id="overlay-logo"><img src="/static/dharanova_logo.png" style="height:70px;width:auto;"></div>
    <svg id="overlay-char" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"></svg>
    <img id="overlay-draw-logo" src="/static/dharanova_logo.png" style="height:120px;width:auto;display:none;margin-bottom:10px;">
    <div id="overlay-name"></div>
    <div id="overlay-sub">CHAMPION</div>
    <div id="overlay-score"></div>
    <hr id="overlay-rule">
    <div id="overlay-brand">DHARANOVA &middot; GROUNDED INNOVATION</div>
</div>

<div id="main-wrap">

<div class="brandband">
    <img src="/static/dharanova_logo.png" style="height:40px;width:auto;display:block;margin:0 auto;">
    <div class="brandband-controls">
        <button id="sound-btn" class="sound-btn" onclick="toggleSound()">&#128266;</button>
        <button id="game-over-btn" class="game-over-btn" onclick="triggerGameOver()">GAME OVER</button>
    </div>
</div>

<div class="subline-row"><span class="subline-title">J U I C E &nbsp;&nbsp; B A T T L E</span></div>

<div class="main-grid">

  <div class="card card-0" id="card-0">
    <div class="node-label">NODE A &middot; JAR 0</div>
    <div class="band-row">
      <div class="jar-box">
        <svg class="jar-svg" viewBox="0 0 90 150" xmlns="http://www.w3.org/2000/svg">
          <rect x="26" y="3" width="38" height="13" rx="4" fill="#c8c8c8"/>
          <rect x="6" y="16" width="78" height="130" rx="14" fill="none" stroke="#7ab52a" stroke-width="3"/>
          <rect id="jar-liquid-0" x="10" y="20" width="70" height="122" rx="11" fill="#b8e83a" opacity="0.92" class="jar-liquid"/>
          <line id="jar-surface-0" x1="10" y1="20" x2="80" y2="20" stroke="#d8f86a" stroke-width="2.5"/>
        </svg>
      </div>
      <div class="stack">
        <div class="char-wrap" id="char-wrap-0">
        <svg id="char-0" class="char-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <ellipse cx="50" cy="55" rx="33" ry="37" fill="#E8D830"/>
          <ellipse cx="50" cy="55" rx="33" ry="37" fill="none" stroke="#C2B01E" stroke-width="2"/>
          <path d="M50 18 Q55 9 61 13" stroke="#5a8a20" stroke-width="4" fill="none" stroke-linecap="round"/>
          <g id="lemon-eyes">
            <ellipse cx="38" cy="47" rx="5" ry="7" fill="#2a2a10"/>
            <ellipse cx="62" cy="47" rx="5" ry="7" fill="#2a2a10"/>
            <circle cx="39.5" cy="44.5" r="1.8" fill="#fff"/>
            <circle cx="63.5" cy="44.5" r="1.8" fill="#fff"/>
          </g>
          <path id="lemon-mouth" d="M42 66 Q50 72 58 66" stroke="#2a2a10" stroke-width="3.5" fill="none" stroke-linecap="round"/>
          <g id="lemon-blush" opacity="0"><ellipse cx="26" cy="59" rx="6" ry="4" fill="#F09090"/><ellipse cx="74" cy="59" rx="6" ry="4" fill="#F09090"/></g>
        </svg>
        </div>
        <div class="persona-name">LEMON WARRIOR</div>
        <div class="glass-count" id="count-0">0</div>
        <div class="glasses-label">GLASSES</div>
        <div class="share-pct" id="share-0">&nbsp;</div>
        <div class="streak-badge" id="streak-0"></div>
        <div class="round-wins" id="wins-0">ROUND WINS: 0</div>
      </div>
    </div>
    <div class="bottom">
      <div class="progress-bar"><div class="progress-fill" id="progress-0"></div></div>
      <div class="pour-label" id="pour-label-0">&nbsp;</div>
      <button class="reset-btn" onclick="resetJar(0)">RESET</button>
    </div>
  </div>

  <div class="card-centre" id="centre-panel">
    <div id="round-over-overlay">
      <div id="ro-heading"></div>
      <div class="ro-score-row"><span class="ro-name0">🍋 Lemon Warrior</span><span id="ro-score0" class="ro-val">0</span></div>
      <div class="ro-score-row"><span class="ro-name1">🍈 Melon Crusher</span><span id="ro-score1" class="ro-val">0</span></div>
      <div id="ro-winner"></div>
      <div id="ro-bar-wrap"><div id="ro-bar"></div></div>
    </div>
    <div id="round-begin-banner">
      <div id="rb-number"></div>
      <div id="rb-begins">BEGINS</div>
    </div>
    <div class="vs-col-top">
      <div class="vs-text">VS</div>
      <div class="lead-pill" id="lead-pill">TIED</div>
    </div>
    <div class="feed-panel">
      <div class="feed-header">
        LIVE POUR FEED
        <div class="live-badge"><span class="live-dot-green"></span> LIVE</div>
      </div>
      <div id="feed-rows"><div class="feed-row"><span class="feed-text" style="color:#333">Waiting for first pour&hellip;</span></div></div>
    </div>
  </div>

  <div class="card card-1" id="card-1">
    <div class="node-label">NODE B &middot; JAR 1</div>
    <div class="band-row">
      <div class="jar-box">
        <svg class="jar-svg" viewBox="0 0 90 150" xmlns="http://www.w3.org/2000/svg">
          <rect x="26" y="3" width="38" height="13" rx="4" fill="#c8c8c8"/>
          <rect x="6" y="16" width="78" height="130" rx="14" fill="none" stroke="#c84070" stroke-width="3"/>
          <rect id="jar-liquid-1" x="10" y="20" width="70" height="122" rx="11" fill="#ff5f8f" opacity="0.92" class="jar-liquid"/>
          <line id="jar-surface-1" x1="10" y1="20" x2="80" y2="20" stroke="#ff9fb8" stroke-width="2.5"/>
        </svg>
      </div>
      <div class="stack">
        <div class="char-wrap" id="char-wrap-1">
        <svg id="char-1" class="char-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <circle cx="50" cy="50" r="38" fill="#3a8a30"/>
          <circle cx="50" cy="50" r="33" fill="#EAF3DE"/>
          <circle cx="50" cy="50" r="29" fill="#E8406A"/>
          <g id="melon-eyes">
            <ellipse cx="40" cy="48" rx="6" ry="7.5" fill="#fff"/>
            <ellipse cx="60" cy="48" rx="6" ry="7.5" fill="#fff"/>
            <circle cx="40" cy="48" r="3.5" fill="#1f0c0c"/>
            <circle cx="60" cy="48" r="3.5" fill="#1f0c0c"/>
            <circle cx="41.4" cy="46.2" r="1.3" fill="#fff"/>
            <circle cx="61.4" cy="46.2" r="1.3" fill="#fff"/>
          </g>
          <path id="melon-mouth" d="M42 64 Q50 70 58 64" stroke="#1f0c0c" stroke-width="3" fill="none" stroke-linecap="round"/>
          <g id="melon-blush" opacity="0"><ellipse cx="28" cy="56" rx="6" ry="4" fill="#FF9090"/><ellipse cx="72" cy="56" rx="6" ry="4" fill="#FF9090"/></g>
        </svg>
        </div>
        <div class="persona-name">MELON CRUSHER</div>
        <div class="glass-count" id="count-1">0</div>
        <div class="glasses-label">GLASSES</div>
        <div class="share-pct" id="share-1">&nbsp;</div>
        <div class="streak-badge" id="streak-1"></div>
        <div class="round-wins" id="wins-1">ROUND WINS: 0</div>
      </div>
    </div>
    <div class="bottom">
      <div class="progress-bar"><div class="progress-fill" id="progress-1"></div></div>
      <div class="pour-label" id="pour-label-1">&nbsp;</div>
      <button class="reset-btn" onclick="resetJar(1)">RESET</button>
    </div>
  </div>

</div><!-- /main-grid -->

<div class="welcome-band">
  <span class="welcome-icon">&#127807;</span>
  <div>
    <div class="welcome-text">Dharanova Welcomes All IoT Enthusiasts to This Summit</div>
    <div class="welcome-sub">Where grounded innovation meets real-world sensing &mdash; thank you for being here</div>
  </div>
  <span class="welcome-icon">&#127807;</span>
</div>

<div class="marketing-zone">

  <div class="mslide ms-water active" id="ms1">
    <div class="ms-left">
      <div class="ms-eyebrow">&#128167; Precision IoT &middot; Water Conservation</div>
      <div class="ms-headline">Every Drop<br>Accounted<br>For</div>
      <div class="ms-body">IoT sensing makes water waste visible &mdash;<br>and stoppable. What gets measured gets managed.</div>
      <div class="ms-live-stat">
        <span class="ms-live-num" id="ms-litres">0.0L</span>
        <span class="ms-live-lbl">served &amp; precisely<br>measured this session</span>
      </div>
      <div class="ms-bar"><div class="ms-bar-fill"></div></div>
      <div class="ms-badge">Built by <strong>DHARANOVA</strong> &mdash; Grounded Innovation</div>
    </div>
    <div class="ms-centre">
      <svg width="130" height="130" viewBox="0 0 160 160">
        <defs>
          <radialGradient id="wgg" cx="40%" cy="35%"><stop offset="0%" stop-color="#1a6a9a"/><stop offset="100%" stop-color="#051a30"/></radialGradient>
          <clipPath id="wcc"><circle cx="80" cy="80" r="70"/></clipPath>
        </defs>
        <circle cx="80" cy="80" r="72" fill="rgba(0,30,60,0.3)" stroke="#0a3050" stroke-width="1.5"/>
        <circle cx="80" cy="80" r="70" fill="url(#wgg)"/>
        <g clip-path="url(#wcc)">
          <path d="M0,100 Q40,80 80,100 Q120,120 160,100 L160,160 L0,160 Z" fill="rgba(30,120,200,0.55)"><animateTransform attributeName="transform" type="translate" values="0,0;-20,8;0,0" dur="3s" repeatCount="indefinite"/></path>
          <path d="M0,112 Q40,92 80,112 Q120,132 160,112 L160,160 L0,160 Z" fill="rgba(20,80,160,0.4)"><animateTransform attributeName="transform" type="translate" values="0,0;20,5;0,0" dur="4s" repeatCount="indefinite"/></path>
        </g>
        <circle cx="80" cy="80" r="70" fill="none" stroke="#4db8ff" stroke-width="1" opacity="0.3"/>
      </svg>
    </div>
    <div class="ms-right">
      <div class="ms-stat"><div class="ms-stat-val">2.5B</div><div class="ms-stat-lbl">People globally lack safe water</div></div>
      <div class="ms-stat"><div class="ms-stat-val">40%</div><div class="ms-stat-lbl">Water lost without measurement</div></div>
      <div class="ms-stat"><div class="ms-stat-val" id="ms-glasses">0</div><div class="ms-stat-lbl">Glasses measured at this stall today</div></div>
    </div>
    <div class="slide-dots"><div class="sdot on" id="sd1"></div><div class="sdot" id="sd2"></div></div>
  </div>

  <div class="mslide ms-india" id="ms2">
    <div class="ms-left">
      <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:6px;">
        <div class="india-stripe"></div>
        <div>
          <div class="ms-eyebrow">India &middot; IoT &middot; Innovation</div>
          <div class="ms-headline">Sensing<br>India's<br>Future</div>
        </div>
      </div>
      <div class="ms-body">From smart agriculture to industrial monitoring &mdash;<br>Dharanova IoT sensors solve real problems<br>across the nation, grounded in Indian soil.</div>
      <div class="ms-live-stat">
        <span class="ms-live-num" style="font-size:20px;">Bharat</span>
        <span class="ms-live-lbl">powered by<br>IoT innovation</span>
      </div>
      <div class="ms-badge">Built in India by <strong>DHARANOVA</strong></div>
    </div>
    <div class="ms-centre">
      <svg width="150" height="165" viewBox="-5 -5 215 255" xmlns="http://www.w3.org/2000/svg">
        <path d="M 199.5,63.1 L 200.0,66.4 L 197.6,68.0 L 198.2,73.3 L 193.3,71.7 L 184.4,77.8 L 184.6,82.8 L 180.9,90.1 L 180.5,94.3 L 177.5,101.5 L 172.1,99.5 L 171.8,108.5 L 170.3,111.5 L 171.0,115.2 L 167.7,117.3 L 164.0,103.5 L 162.2,103.5 L 161.0,109.1 L 157.3,104.5 L 159.4,99.6 L 162.5,99.1 L 165.6,91.7 L 161.7,90.2 L 155.3,90.3 L 148.8,89.1 L 148.2,83.1 L 144.9,82.6 L 139.5,78.9 L 137.1,84.8 L 142.0,89.4 L 137.8,92.7 L 136.2,95.8 L 140.5,98.2 L 139.3,103.4 L 141.7,110.0 L 142.7,117.2 L 141.8,120.3 L 137.1,120.2 L 128.7,122.0 L 129.0,128.6 L 125.4,133.8 L 115.5,139.6 L 107.9,149.9 L 102.7,155.4 L 95.9,161.1 L 95.9,165.1 L 92.5,167.3 L 86.3,170.4 L 83.1,170.8 L 81.1,177.5 L 82.5,188.8 L 82.9,196.1 L 80.0,204.3 L 79.9,219.1 L 76.4,219.6 L 73.3,226.2 L 75.4,229.1 L 69.1,231.6 L 66.8,237.5 L 64.1,240.0 L 57.6,231.9 L 54.4,219.7 L 51.8,210.9 L 49.4,206.7 L 45.8,198.4 L 44.1,187.5 L 42.9,182.0 L 36.7,170.0 L 33.8,153.1 L 31.8,142.0 L 31.8,131.4 L 30.5,123.3 L 20.5,128.5 L 15.7,127.4 L 6.8,116.9 L 10.1,113.7 L 8.0,110.3 L 0.0,102.9 L 4.6,97.1 L 19.6,97.1 L 18.3,89.6 L 14.4,85.2 L 13.6,78.5 L 9.2,74.6 L 16.7,65.4 L 24.7,66.1 L 31.8,56.9 L 36.1,48.1 L 42.7,39.4 L 42.6,33.1 L 48.5,28.1 L 42.9,23.8 L 40.6,17.9 L 38.1,10.3 L 41.5,6.5 L 51.9,8.6 L 59.5,7.3 L 66.1,0.0 L 73.5,10.2 L 72.8,17.3 L 75.5,21.8 L 75.3,26.2 L 70.4,25.1 L 72.3,34.7 L 79.0,40.2 L 88.5,46.3 L 84.2,50.2 L 81.5,58.4 L 88.1,61.7 L 94.6,66.0 L 103.5,70.9 L 112.9,72.0 L 116.9,76.4 L 122.1,77.3 L 130.4,79.3 L 136.1,79.2 L 136.9,75.7 L 136.0,70.2 L 136.5,66.4 L 140.7,64.6 L 141.2,71.4 L 141.4,73.2 L 147.6,76.5 L 151.9,75.1 L 157.7,75.7 L 163.3,75.5 L 163.8,70.1 L 161.0,67.3 L 166.5,66.2 L 172.7,59.7 L 180.6,54.2 L 186.4,56.3 L 191.2,52.7 L 194.4,58.1 L 192.1,61.7 L 199.5,63.1 Z"
          fill="rgba(40,18,0,0.85)" stroke="#ff9933" stroke-width="1.2" stroke-linejoin="round"/>
        <ellipse cx="105" cy="248" rx="8" ry="11" fill="rgba(40,18,0,0.7)" stroke="#ff9933" stroke-width="1"/>
        <circle cx="94" cy="73" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="2.0s" repeatCount="indefinite"/></circle>
        <text x="100" y="72" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Delhi</text>
        <circle cx="50" cy="148" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="2.4s" repeatCount="indefinite"/></circle>
        <text x="4" y="147" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Mumbai</text>
        <circle cx="138" cy="118" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="1.8s" repeatCount="indefinite"/></circle>
        <text x="144" y="117" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Kolkata</text>
        <circle cx="95" cy="162" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="2.2s" repeatCount="indefinite"/></circle>
        <text x="100" y="161" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Hyd</text>
        <circle cx="88" cy="192" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="2.6s" repeatCount="indefinite"/></circle>
        <text x="55" y="192" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Blr</text>
        <circle cx="110" cy="192" r="5" fill="#ff9933"><animate attributeName="r" values="4;8;4" dur="2.8s" repeatCount="indefinite"/></circle>
        <text x="116" y="192" fill="#ffcc66" font-size="10" font-family="monospace" font-weight="bold">Chennai</text>
        <line x1="94" y1="73" x2="50" y2="148" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
        <line x1="94" y1="73" x2="138" y2="118" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
        <line x1="50" y1="148" x2="95" y2="162" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
        <line x1="138" y1="118" x2="95" y2="162" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
        <line x1="95" y1="162" x2="88" y2="192" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
        <line x1="95" y1="162" x2="110" y2="192" stroke="#ff9933" stroke-width="0.7" opacity="0.25"/>
      </svg>
    </div>
    <div class="ms-right">
      <div class="ms-stat"><div class="ms-stat-val">IoT</div><div class="ms-stat-lbl">Smart agriculture &amp; water management</div></div>
      <div class="ms-stat"><div class="ms-stat-val">Edge</div><div class="ms-stat-lbl">Real-time sensing at point of action</div></div>
      <div class="ms-stat"><div class="ms-stat-val">Open</div><div class="ms-stat-lbl">Open hardware &mdash; accessible to all</div></div>
    </div>
    <div class="slide-dots"><div class="sdot" id="sd3"></div><div class="sdot on" id="sd4"></div></div>
  </div>

</div><!-- /marketing-zone -->
</div><!-- /main-wrap -->

<div class="ticker-bar">
  <div class="ticker-mid">
    <div class="ticker-track" id="ticker-track">
      <span class="ticker-item"><span class="ticker-served-num" id="t-served">0</span> IOT ENTHUSIASTS SERVED</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">BUILT BY DHARANOVA &mdash; GROUNDED INNOVATION</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">EVERY POUR MEASURED &nbsp;&middot;&nbsp; EVERY DROP COUNTS</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item ticker-grn">INDIA'S IoT PIONEERS</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">WELCOME TO THE DHARANOVA IoT SUMMIT</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item"><span class="ticker-served-num" id="t-served2">0</span> IOT ENTHUSIASTS SERVED</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">BUILT BY DHARANOVA &mdash; GROUNDED INNOVATION</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">EVERY POUR MEASURED &nbsp;&middot;&nbsp; EVERY DROP COUNTS</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item ticker-grn">INDIA'S IoT PIONEERS</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
      <span class="ticker-item">WELCOME TO THE DHARANOVA IoT SUMMIT</span>
      <span class="ticker-sep">&nbsp;&middot;&nbsp;</span>
    </div>
  </div>
  <div class="ticker-right">
    <span class="status-dot" id="status-dot"></span>
    <span id="status-text">CONNECTING...</span>
  </div>
</div>

<script src="/static/socket.io.js"></script>
<script>
// ATMOSPHERIC BACKGROUND
const bgCanvas=document.getElementById('bg-canvas'),bgCtx=bgCanvas.getContext('2d');
function bgResize(){bgCanvas.width=window.innerWidth;bgCanvas.height=window.innerHeight;}
bgResize();window.addEventListener('resize',bgResize);
const bgP=[];
for(let i=0;i<130;i++){const w=Math.random()>0.4;bgP.push({x:Math.random()*window.innerWidth,y:Math.random()*window.innerHeight,r:Math.random()*2.8+0.8,vx:(Math.random()-0.5)*0.28,vy:(Math.random()-0.5)*0.28,alpha:Math.random()*0.55+0.18,w,phase:Math.random()*Math.PI*2,ps:Math.random()*0.015+0.005});}
let bgPh=0;
function bgDraw(){bgCtx.clearRect(0,0,bgCanvas.width,bgCanvas.height);bgPh+=0.004;const cx=bgCanvas.width/2,cy=bgCanvas.height/2;const g=bgCtx.createRadialGradient(cx,cy,0,cx,cy,bgCanvas.height*0.55);const a=0.07+0.038*Math.sin(bgPh);g.addColorStop(0,`rgba(0,110,65,${a*1.5})`);g.addColorStop(0.3,`rgba(0,65,130,${a})`);g.addColorStop(0.7,`rgba(0,22,65,${a*0.4})`);g.addColorStop(1,'rgba(0,0,0,0)');bgCtx.fillStyle=g;bgCtx.fillRect(0,0,bgCanvas.width,bgCanvas.height);for(const p of bgP){p.phase+=p.ps;const pa=p.alpha*(0.5+0.5*Math.sin(p.phase));bgCtx.beginPath();bgCtx.arc(p.x,p.y,p.r,0,Math.PI*2);bgCtx.fillStyle=p.w?`rgba(45,150,230,${pa})`:`rgba(230,115,30,${pa})`;bgCtx.fill();p.x+=p.vx;p.y+=p.vy;if(p.x<-5)p.x=bgCanvas.width+5;if(p.x>bgCanvas.width+5)p.x=-5;if(p.y<-5)p.y=bgCanvas.height+5;if(p.y>bgCanvas.height+5)p.y=-5;}requestAnimationFrame(bgDraw);}
bgDraw();
// POUR RIPPLE
function triggerRipple(n){const ring=document.createElement('div');ring.className='ripple-ring';const x=n===0?window.innerWidth*0.22:window.innerWidth*0.78;const y=window.innerHeight*0.35;ring.style.left=x+'px';ring.style.top=y+'px';ring.style.border='3px solid '+(n===0?'rgba(184,232,58,0.55)':'rgba(255,95,143,0.55)');document.body.appendChild(ring);setTimeout(()=>ring.remove(),1900);}
// CAUSE PANEL ROTATION
(function(){var cur=1;setInterval(function(){var s1=el('ms1'),s2=el('ms2'),d1=el('sd1'),d2=el('sd2'),d3=el('sd3'),d4=el('sd4');if(cur===1){s1.classList.remove('active');s2.classList.add('active');d1.classList.remove('on');d2.classList.add('on');d3.classList.remove('on');d4.classList.add('on');cur=2;}else{s2.classList.remove('active');s1.classList.add('active');d2.classList.remove('on');d1.classList.add('on');d4.classList.remove('on');d3.classList.add('on');cur=1;}},7000);})();
// MARKETING STATS
function updateMarketingStats(allTime,total){var l=el('ms-litres');if(l)l.textContent=((total*150)/1000).toFixed(2)+'L';var g=el('ms-glasses');if(g)g.textContent=allTime;}
// SOCKET + GAME LOGIC
const socket=io();
const sounds={glass:new Audio('/static/sounds/glass.mp3'),pour:new Audio('/static/sounds/pour.mp3'),fanfare:new Audio('/static/sounds/fanfare.mp3'),cheer:new Audio('/static/sounds/cheer.mp3')};
sounds.pour.loop=true;Object.values(sounds).forEach(s=>{s.preload='auto';s.load();});
let soundEnabled=true,audioUnlocked=false,initialized=false,gameOverHandled=false,pourFadeTimer=null;
const pouringNodes=new Set(),prevCount={'0':0,'1':0},prevPartial={'0':0,'1':0},idleCount={'0':0,'1':0},streak={'0':0,'1':0};
const IDLE_AFTER=3,JAR_CAPACITY_G=5000,feedEvents=[],pourStartTs={'0':0,'1':0},prevPourActive={'0':false,'1':false};
let minPourSec=null,lastBleStatus={};
document.addEventListener('click',function(){if(!audioUnlocked){sounds.glass.play().catch(()=>{});sounds.glass.pause();sounds.glass.currentTime=0;audioUnlocked=true;}},{once:true});
function stopAllSounds(){if(pourFadeTimer!==null){clearInterval(pourFadeTimer);pourFadeTimer=null;}Object.values(sounds).forEach(s=>{s.pause();s.currentTime=0;s.volume=1;});pouringNodes.clear();}
function playSound(name){if(!soundEnabled)return;try{const s=sounds[name];s.pause();s.currentTime=0;s.play().catch(e=>console.log('audio:',e));}catch(e){console.log('sound error:',e);}}
function startPour(){if(!soundEnabled||!sounds.pour.paused)return;if(pourFadeTimer!==null){clearInterval(pourFadeTimer);pourFadeTimer=null;sounds.pour.volume=1;}try{sounds.pour.currentTime=0;sounds.pour.play().catch(e=>console.log('audio:',e));}catch(e){console.log('sound error:',e);}}
function fadeOutPour(){const s=sounds.pour;if(s.paused)return;if(pourFadeTimer!==null){clearInterval(pourFadeTimer);pourFadeTimer=null;s.volume=1;}const steps=10,interval=15;let i=0;pourFadeTimer=setInterval(()=>{i++;s.volume=1-i/steps;if(i>=steps){clearInterval(pourFadeTimer);pourFadeTimer=null;s.pause();s.currentTime=0;s.volume=1;}},interval);}
function toggleSound(){soundEnabled=!soundEnabled;el('sound-btn').textContent=soundEnabled?'&#128266;':'&#128263;';if(!soundEnabled)stopAllSounds();}
const CHAR={'0':{name:'lemon',watchCls:'watching-right'},'1':{name:'melon',watchCls:'watching-left'}};
const CHAR_MOUTH={'0':{neutral:'M42 66 Q50 72 58 66',excited:'M38 62 Q50 78 62 62',grin:'M30 63 Q50 84 70 63'},'1':{neutral:'M42 64 Q50 70 58 64',excited:'M38 60 Q50 76 62 60',grin:'M38 62 Q50 70 62 62'}};
const celebrating={'0':false,'1':false};
function setCharState(jarN,state){const ns=String(jarN),ch=CHAR[ns],svg=el('char-'+ns),eyes=el(ch.name+'-eyes'),mouth=el(ch.name+'-mouth'),blush=el(ch.name+'-blush');svg.classList.remove('excited','celebrating');if(eyes)eyes.classList.remove('eyes-wide','watching-right','watching-left','glance-right','glance-left','look-cycle-left','look-cycle-right');switch(state){case 'idle':celebrating[ns]=false;if(mouth)mouth.setAttribute('d',CHAR_MOUTH[ns].neutral);if(blush)blush.setAttribute('opacity','0');if(eyes)eyes.classList.add(ns==='0'?'look-cycle-left':'look-cycle-right');break;case 'excited':svg.classList.add('excited');if(eyes)eyes.classList.add('eyes-wide');if(mouth)mouth.setAttribute('d',CHAR_MOUTH[ns].excited);break;case 'watching':if(mouth)mouth.setAttribute('d',CHAR_MOUTH[ns].neutral);if(eyes)eyes.classList.add(ch.watchCls);break;case 'celebrating':celebrating[ns]=true;void svg.offsetWidth;svg.classList.add('celebrating');setTimeout(()=>svg.classList.remove('celebrating'),700);if(blush)blush.setAttribute('opacity','0.5');if(mouth)mouth.setAttribute('d',CHAR_MOUTH[ns].grin);setTimeout(()=>{celebrating[ns]=false;svg.classList.remove('excited');if(eyes)eyes.classList.remove('eyes-wide','watching-right','watching-left','look-cycle-left','look-cycle-right');if(eyes)eyes.classList.add(ns==='0'?'look-cycle-left':'look-cycle-right');if(blush)blush.setAttribute('opacity','0');if(mouth)mouth.setAttribute('d',CHAR_MOUTH[ns].neutral);},2000);break;}}
function el(id){return document.getElementById(id);}
function showFloatLabel(cardId,text,color){const card=el(cardId),lbl=document.createElement('div');lbl.textContent=text;lbl.style.cssText='position:absolute;top:45%;left:50%;font-size:11px;font-weight:800;letter-spacing:2px;pointer-events:none;color:'+color+';animation:floatup 1.8s ease-out forwards;z-index:10;white-space:nowrap;';card.appendChild(lbl);setTimeout(()=>lbl.remove(),1800);}
function spawnConfetti(cardEl){const colors=['#E8D830','#7ab52a','#E8406A','#c67b3f','#fff'];for(let i=0;i<18;i++){const bit=document.createElement('div'),c=colors[Math.floor(Math.random()*colors.length)];bit.style.cssText='position:absolute;width:6px;height:12px;background:'+c+';left:'+(Math.random()*100)+'%;top:-10px;opacity:1;border-radius:1px;pointer-events:none;z-index:5;';bit.style.animation='confetti-fall '+(1.2+Math.random()*0.8)+'s ease-in forwards';bit.style.animationDelay=(Math.random()*0.3)+'s';cardEl.appendChild(bit);setTimeout(()=>bit.remove(),2500);}}
function addFeedEvent(text,color){feedEvents.unshift({text,color,ts:Date.now()});if(feedEvents.length>5)feedEvents.pop();renderFeed();}
function relTime(ts){const s=Math.floor((Date.now()-ts)/1000);if(s<5)return 'now';if(s<60)return s+'s';return Math.floor(s/60)+'m';}
function renderFeed(){const rows=el('feed-rows');if(!rows)return;rows.innerHTML=feedEvents.map(e=>'<div class="feed-row"><div class="feed-dot" style="background:'+e.color+'"></div><div class="feed-text">'+e.text+'</div><div class="feed-time">'+relTime(e.ts)+'</div></div>').join('');}
setInterval(renderFeed,5000);
function updateJarFill(n,count,vol){const used=count*vol,ff=Math.max(0,Math.min(1,1-used/JAR_CAPACITY_G)),h=(122*ff).toFixed(1),y=(142-122*ff).toFixed(1),liq=el('jar-liquid-'+n),surf=el('jar-surface-'+n);if(liq){liq.setAttribute('height',h);liq.setAttribute('y',y);}if(surf){surf.setAttribute('y1',y);surf.setAttribute('y2',y);}}
function updateTicker(c0,c1,totalServed){['','2'].forEach(sfx=>{const sn=el('t-served'+sfx);if(sn)sn.textContent=String(totalServed);});}
let wasDisconnected=false;
socket.on('disconnect',()=>{el('status-text').textContent='RECONNECTING...';wasDisconnected=true;});
socket.on('connect',()=>{el('status-text').textContent='CONNECTED';if(wasDisconnected){wasDisconnected=false;window.location.reload();}});
socket.io.on('reconnect',()=>{window.location.reload();});
socket.on('state',(data)=>{
  const gc=data.glass_count||{},pg=data.partial_g||{},vol=data.glass_volume_g||150;
  if(!initialized){prevCount['0']=gc['0']??0;prevCount['1']=gc['1']??0;prevPartial['0']=pg['0']??0;prevPartial['1']=pg['1']??0;el('count-0').textContent=String(prevCount['0']);el('count-1').textContent=String(prevCount['1']);initialized=true;}
  const p0Inc=(pg['0']??0)>prevPartial['0'],p1Inc=(pg['1']??0)>prevPartial['1'];
  if(p0Inc&&!prevPourActive['0'])pourStartTs['0']=Date.now();if(p1Inc&&!prevPourActive['1'])pourStartTs['1']=Date.now();
  prevPourActive['0']=p0Inc;prevPourActive['1']=p1Inc;
  if(p0Inc&&!pouringNodes.has('0')){const w=pouringNodes.size===0;pouringNodes.add('0');if(w)startPour();}
  if(p1Inc&&!pouringNodes.has('1')){const w=pouringNodes.size===0;pouringNodes.add('1');if(w)startPour();}
  if(p0Inc||p1Inc){idleCount['0']=0;idleCount['1']=0;if(!celebrating['0'])setCharState(0,'excited');if(!celebrating['1'])setCharState(1,'excited');}
  else{idleCount['0']++;idleCount['1']++;if(idleCount['0']>=IDLE_AFTER){if(!celebrating['0'])setCharState(0,'idle');if(pouringNodes.has('0')){pouringNodes.delete('0');if(pouringNodes.size===0)fadeOutPour();}}if(idleCount['1']>=IDLE_AFTER){if(!celebrating['1'])setCharState(1,'idle');if(pouringNodes.has('1')){pouringNodes.delete('1');if(pouringNodes.size===0)fadeOutPour();}}}
  prevPartial['0']=pg['0']??0;prevPartial['1']=pg['1']??0;
  [0,1].forEach(n=>{
    const ns=String(n),newCount=gc[ns]??0,oldCount=prevCount[ns],pgVal=pg[ns]??0,pct=Math.min(100,(pgVal/vol)*100).toFixed(1);
    el('progress-'+n).style.width=pct+'%';
    el('pour-label-'+n).innerHTML=pgVal>1?'Last <b style="color:#5f5f5f">+'+pgVal.toFixed(0)+'g</b>':'&nbsp;';
    if(newCount>oldCount){
      const loser=1-n,loserNs=String(loser),scoreColor=n===0?'#b8e83a':'#ff5f8f',personaName=n===0?'LEMON WARRIOR':'MELON CRUSHER';
      if(pourStartTs[ns]>0){const d=(Date.now()-pourStartTs[ns])/1000;if(minPourSec===null||d<minPourSec)minPourSec=d;pourStartTs[ns]=0;}
      playSound('glass');
      triggerRipple(n);
      const cardEl=el('card-'+n);cardEl.classList.remove('pouring');void cardEl.offsetWidth;cardEl.classList.add('pouring');setTimeout(()=>cardEl.classList.remove('pouring'),800);
      setCharState(n,'celebrating');
      const wrapEl=el('char-wrap-'+n);if(wrapEl){wrapEl.classList.remove('area-zoom');void wrapEl.offsetWidth;wrapEl.classList.add('area-zoom');setTimeout(()=>wrapEl.classList.remove('area-zoom'),600);}
      setCharState(loser,'idle');
      const loserEyes=el(CHAR[loserNs].name+'-eyes');if(loserEyes){loserEyes.classList.remove('look-cycle-left','look-cycle-right');const gc2=loser===0?'glance-right':'glance-left';void loserEyes.offsetWidth;loserEyes.classList.add(gc2);setTimeout(()=>{loserEyes.classList.remove(gc2);loserEyes.classList.add(loser===0?'look-cycle-left':'look-cycle-right');},1600);}
      const countEl=el('count-'+n);countEl.classList.remove('digit-swap','numpop');void countEl.offsetWidth;countEl.classList.add('digit-swap');setTimeout(()=>{countEl.textContent=String(newCount);},200);setTimeout(()=>{countEl.classList.remove('digit-swap');void countEl.offsetWidth;countEl.classList.add('numpop');setTimeout(()=>countEl.classList.remove('numpop'),500);},500);
      spawnConfetti(el('card-'+n));showFloatLabel('card-'+n,'+1 GLASS',scoreColor);
      streak[ns]=(streak[ns]||0)+1;streak[loserNs]=0;
      if(streak[ns]>=3&&streak[ns]%2===1){playSound('fanfare');addFeedEvent(personaName+' is on a '+streak[ns]+'-pour streak','#e8b830');}
      addFeedEvent(personaName+' poured glass #'+newCount,scoreColor);
    }else{el('count-'+n).textContent=String(newCount);}
    prevCount[ns]=newCount;updateJarFill(n,newCount,vol);
    const badge=el('streak-'+n);if(streak[ns]>=2){const fires='🔥'.repeat(Math.min(streak[ns],5));badge.textContent=fires+' '+streak[ns]+'-POUR STREAK';badge.style.display='inline-block';}else{badge.style.display='none';}
  });
  const c0=gc['0']??0,c1=gc['1']??0,total=c0+c1,p0=total>0?Math.round(c0/total*100):50,p1=100-p0;
  const s0=el('share-0');if(s0)s0.textContent=total>0?p0+'% OF ALL POURS':' ';
  const s1=el('share-1');if(s1)s1.textContent=total>0?p1+'% OF ALL POURS':' ';
  updateTicker(c0,c1,data.session_glasses??0);
  updateMarketingStats(data.all_time_served??0,total);
  const pill=el('lead-pill'),pb='padding:4px 10px;border-radius:20px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;';
  if(c0>c1){pill.textContent='LEMON LEADS';pill.style.cssText=pb+'background:#0d1508;color:#b8e83a;border:1px solid #4a6a1a;';}
  else if(c1>c0){pill.textContent='MELON LEADS';pill.style.cssText=pb+'background:#150a12;color:#ff5f8f;border:1px solid #7a2a4a;';}
  else{pill.textContent='TIED';pill.style.cssText=pb+'background:#1a1a1a;color:#3a3a3a;border:1px solid #2a2a2a;';}
  const bleStatus=data.ble_status||{},warnings=[];
  [0,1].forEach(n=>{const ns=String(n),cur=bleStatus[ns]||'connected',prv=lastBleStatus[ns]||'connected';if(cur!==prv){if(cur==='disconnected')addFeedEvent('JAR '+n+' disconnected','#e8b830');else addFeedEvent('JAR '+n+' reconnected','#7ab52a');}if(cur==='disconnected')warnings.push('JAR '+n+' RECONNECTING');});
  lastBleStatus=Object.assign({},bleStatus);
  if(warnings.length===0){el('status-dot').className='status-dot';el('status-text').textContent='BOTH NODES CONNECTED';}
  else{el('status-dot').className='status-dot disconnected';el('status-text').innerHTML=warnings.map(w=>'<span class="node-warning">'+w+'</span>').join(' &middot; ');}
  if(data.game_over&&!gameOverHandled){gameOverHandled=true;handleGameOver(data.winner);}
  if(!data.game_over){gameOverHandled=false;el('game-over-btn').disabled=false;}
  // Round wins per jar — updates small text below score digit
  const rw=data.round_wins||{};
  const w0el=el('wins-0'),w1el=el('wins-1');
  if(w0el)w0el.textContent='ROUND WINS: '+(rw.lemon||0);
  if(w1el)w1el.textContent='ROUND WINS: '+(rw.melon||0);
});
function handleGameOver(winner){playSound('fanfare');setTimeout(()=>{playSound('cheer');setTimeout(()=>{sounds.cheer.pause();sounds.cheer.currentTime=0;},4000);},1500);el('game-over-btn').disabled=true;const w=String(winner);let name,color,isDraw;if(w==='0'){name='LEMON WARRIOR';color='#b8e83a';isDraw=false;}else if(w==='1'){name='MELON CRUSHER';color='#ff5f8f';isDraw=false;}else{name="IT'S A DRAW";color='#c67b3f';isDraw=true;}el('overlay-name').textContent=name;el('overlay-name').style.color=color;el('overlay-sub').style.display=isDraw?'none':'';const destSvg=el('overlay-char'),drawLogoEl=el('overlay-draw-logo');if(isDraw){destSvg.style.display='none';drawLogoEl.style.display='';destSvg.innerHTML='';}else{destSvg.style.display='';drawLogoEl.style.display='none';const srcSvg=el('char-'+w);destSvg.innerHTML=srcSvg?srcSvg.innerHTML:'';}const c0=prevCount['0'],c1=prevCount['1'],wg=isDraw?c0:(w==='0'?c0:c1),lg=isDraw?c1:(w==='0'?c1:c0);el('overlay-score').textContent=wg+' GLASS'+(wg!==1?'ES':'')+' VS '+lg+' GLASS'+(lg!==1?'ES':'');const overlay=el('winner-overlay');overlay.style.opacity='0';overlay.style.transition='';overlay.style.display='flex';void overlay.offsetWidth;overlay.style.transition='opacity 0.5s ease';overlay.style.opacity='1';setTimeout(()=>{overlay.style.transition='opacity 0.8s ease';overlay.style.opacity='0';setTimeout(()=>{overlay.style.display='none';},800);},5000);}
function resetJar(n){fetch('/reset/'+n,{method:'POST'}).then(r=>r.json()).then(d=>{if(!d.ok){console.error('reset failed',d);return;}streak['0']=0;streak['1']=0;prevCount[String(n)]=0;minPourSec=null;[0,1].forEach(i=>{const b=el('streak-'+i);b.style.display='none';b.textContent='';});updateJarFill(n,0,150);});}
function triggerGameOver(){fetch('/game_over',{method:'POST'}).then(r=>r.json()).then(d=>{if(!d.ok)console.error('game_over failed',d);});}
socket.on('round_over',function(data){
  var names=['🍋 Lemon Warrior','🍈 Melon Crusher'];
  var winnerText=data.winner===-1?"IT'S A TIE! 🤝":names[data.winner]+' WINS! 🏆';
  document.getElementById('ro-heading').textContent='ROUND '+data.round+' COMPLETE';
  document.getElementById('ro-score0').textContent=data.score0;
  document.getElementById('ro-score1').textContent=data.score1;
  document.getElementById('ro-winner').textContent=winnerText;
  var bar=document.getElementById('ro-bar');
  bar.style.animation='none';
  bar.offsetHeight;
  bar.style.animation='drainBar 10s linear forwards';
  document.getElementById('round-over-overlay').style.display='flex';
});
socket.on('round_begin',function(data){
  document.getElementById('round-over-overlay').style.display='none';
  document.getElementById('rb-number').textContent='ROUND '+data.round;
  document.getElementById('round-begin-banner').style.display='flex';
  setTimeout(function(){document.getElementById('round-begin-banner').style.display='none';},2000);
});
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

    def __init__(self, game, storage=None):
        # game instance injected by main.py - Dashboard never imports game directly
        self._game = game

        if storage is None:
            from storage import Storage as _Storage
            storage = _Storage(config.DB_PATH)
        self._storage = storage
        self._all_time_served    = 0
        self._all_time_served_ts = 0.0
        self._session_glasses    = 0
        self._session_glasses_ts = 0.0
        self._round_wins         = {'lemon': 0, 'melon': 0, 'tie': 0}
        self._round_wins_ts      = 0.0

        self._app = Flask(__name__)
        # threading mode: real OS threads, no monkey-patching.
        # eventlet/gevent would conflict with transport.py's real threads.
        self._sio = SocketIO(self._app, async_mode='threading', cors_allowed_origins='*')

        self._app.add_url_rule('/', 'index', self._serve_index)
        self._app.add_url_rule('/reset/<int:node_id>', 'reset_node',
                               self._reset_node, methods=['POST'])
        self._app.add_url_rule('/game_over', 'game_over',
                               self._game_over, methods=['POST'])
        self._app.add_url_rule('/adjust/<int:node_id>/<delta>', 'adjust',
                               self._adjust_count, methods=['POST'])
        self._app.add_url_rule('/v2', 'index_v2', self._serve_v2)
        self._app.add_url_rule('/v3', 'index_v3', self._serve_v3)
        self._app.add_url_rule('/reset_rounds', 'reset_rounds',
                               self._reset_rounds, methods=['POST'])

        @self._sio.on('connect')
        def _on_browser_connect():
            # WHY: push state immediately to reconnecting browser.
            # Without this, browser shows HTML default (0) for up to 500ms
            # while waiting for next _push_loop cycle — looks like score reset.
            state = self._game.get_state()
            emit('state', self._build_payload(state))

    def _build_payload(self, state: dict) -> dict:
        now = time.time()
        # All-time counter: refresh every 5s (DB read, not per-event)
        if now - self._all_time_served_ts >= 5.0:
            self._all_time_served    = self._storage.get_all_time_glasses()
            self._all_time_served_ts = now
        # Session glasses: refresh every 2s (increments every pour)
        if now - self._session_glasses_ts >= 2.0:
            self._session_glasses    = self._game.get_session_glasses()
            self._session_glasses_ts = now
        # Round wins: refresh every 5s (only changes at round end)
        if now - self._round_wins_ts >= 5.0:
            self._round_wins    = self._game.get_round_wins()
            self._round_wins_ts = now
        return {
            'glass_count':     state['glass_count'],
            'partial_g':       state['partial_g'],
            'running':         state['running'],
            'glass_volume_g':  config.GLASS_VOLUME_G,
            'node_status':     state['node_status'],
            'ble_status':      state['ble_status'],
            'game_over':       state['game_over'],
            'winner':          state['winner'],
            'all_time_served': self._all_time_served,
            'session_glasses': self._session_glasses,
            'round_wins':      self._round_wins,
        }

    def _reset_node(self, node_id: int):
        if node_id not in (0, 1):
            return jsonify({'ok': False, 'error': 'invalid node'}), 400
        self._game.reset_node(node_id)
        return jsonify({'ok': True, 'node_id': node_id})

    def _game_over(self):
        result = self._game.game_over()
        self._sio.emit('state', self._build_payload(self._game.get_state()))
        if result['winner'] is not None:
            return jsonify({'ok': True, 'winner': result['winner']})
        return jsonify({'ok': True, 'draw': True})

    def _adjust_count(self, node_id: int, delta: str):
        if node_id not in (0, 1):
            return jsonify({'ok': False, 'error': 'invalid node'}), 400
        try:
            delta_int = int(delta)
        except ValueError:
            return jsonify({'ok': False, 'error': 'invalid delta'}), 400
        new_count = self._game.adjust_glass_count(node_id, delta_int)
        return jsonify({'ok': True, 'node': node_id, 'new_count': new_count})

    def _serve_index(self):
        """Serve the scoreboard HTML page."""
        return render_template_string(HTML_TEMPLATE)

    def _serve_v2(self):
        """Serve the crowd-facing v2 dashboard."""
        return render_template_string(HTML_V2)

    def _reset_rounds(self):
        self._storage.set_round_number(1)
        self._game.round_number = 1
        self._game.glasses_this_round = 0
        self._game._round_in_progress = True
        return jsonify({'status': 'ok', 'round_number': 1})

    def _serve_v3(self):
        """Serve the crowd-facing v3 dashboard with atmospheric background and cause panel."""
        response = make_response(render_template_string(HTML_V3))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    def _push_loop(self):
        """
        Background task: poll game state every 500ms, push to all browsers.
        Runs as a daemon thread (started by start_background_task).
        game.get_state() is Lock-protected - safe to call from any thread.
        """
        _prev_round_in_progress = True
        while True:
            state = self._game.get_state()
            self._sio.emit('state', self._build_payload(state))
            rin = state.get('round_in_progress', True)
            if not rin and _prev_round_in_progress:
                self._sio.emit('round_over', {
                    'round':  state.get('round_number', 1),
                    'winner': state.get('round_last_winner', -1),
                    'score0': state.get('round_last_score0', 0),
                    'score1': state.get('round_last_score1', 0),
                })
            elif rin and not _prev_round_in_progress:
                self._sio.emit('round_begin', {'round': state.get('round_number', 1)})
            _prev_round_in_progress = rin
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
