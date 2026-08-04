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
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    user-select: none;
}
#main-wrap {
    width: 100%;
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    position: relative;
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
    font-size: 8px;
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
    grid-template-columns: 340px 120px 340px;
    justify-content: center;
    gap: 20px;
    padding: 10px 16px;
    align-items: start;
}
.card {
    width: 340px;
    min-height: 520px;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 18px 20px;
    border-radius: 14px;
    position: relative;
    overflow: hidden;
}
.card-0 { background: #0d1508; border: 2px solid #4a6a1a; }
.card-1 { background: #150a12; border: 2px solid #7a2a4a; }
.char-svg {
    width: 130px;
    height: 130px;
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
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    margin-top: 10px;
    letter-spacing: 1px;
}
.card-0 .persona-name { color: #a8d84a; }
.card-1 .persona-name { color: #e8608a; }
.jar-label {
    font-size: 7px;
    color: #333;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}
.glass-count {
    font-size: 74px;
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    margin-top: 6px;
    display: inline-block;
}
.card-0 .glass-count { color: #a8d84a; }
.card-1 .glass-count { color: #e8608a; }
.glass-count.digit-swap { animation: digit-swap 0.5s ease-in-out forwards; }
.glass-count.numpop     { animation: numpop 0.5s ease-out; }
.glasses-label {
    font-size: 7px;
    color: #333;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
}
.progress-bar {
    width: 100%;
    height: 3px;
    background: #131313;
    border-radius: 2px;
    overflow: hidden;
    margin: 8px 0 4px;
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
    font-size: 8px;
    color: #3a3a3a;
    height: 14px;
    text-align: center;
}
.streak-badge {
    display: none;
    background: #1a1400;
    border: 1px solid #5a4400;
    color: #e8b830;
    font-size: 8px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 20px;
    margin-top: 4px;
    letter-spacing: 0.5px;
}
.reset-btn {
    background: transparent;
    border: 1px solid #242424;
    color: #3a3a3a;
    font-size: 8px;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    letter-spacing: 0.08em;
    margin-top: 6px;
}
.vs-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    align-self: center;
}
.vs-text { font-size: 17px; font-weight: 800; color: #282828; }
.lead-pill {
    font-size: 7px;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 20px;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border: 1px solid #2a2a2a;
    background: #1a1a1a;
    color: #3a3a3a;
}
.status-row {
    border-top: 1px solid #131313;
    text-align: center;
    padding: 8px 16px;
    font-size: 8px;
    letter-spacing: 2px;
    color: #2a2a2a;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    position: relative;
}
.status-dot {
    width: 6px;
    height: 6px;
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
.served-vertical {
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%) rotate(180deg);
    writing-mode: vertical-rl;
    display: flex;
    align-items: center;
    gap: 10px;
    pointer-events: none;
}
.sv-count {
    font-size: 26px;
    font-weight: 800;
    color: #c67b3f;
    font-variant-numeric: tabular-nums;
    letter-spacing: 2px;
}
.sv-label {
    font-size: 9px;
    letter-spacing: 4px;
    color: #444;
    text-transform: uppercase;
}
@media (max-width: 1299px) { .served-vertical { display: none; } }
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

<div class="served-vertical">
    <span class="sv-count" id="served-count">0</span>
    <span class="sv-label">IOT ENTHUSIASTS SERVED</span>
</div>

<div class="main-grid">

    <div class="card card-0" id="card-0">
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
            <path id="lemon-mouth" d="M42 66 Q50 70 58 66" stroke="#2a2a10" stroke-width="3.5" fill="none" stroke-linecap="round"/>
            <g id="lemon-blush" opacity="0">
                <ellipse cx="26" cy="59" rx="6" ry="4" fill="#F09090"/>
                <ellipse cx="74" cy="59" rx="6" ry="4" fill="#F09090"/>
            </g>
        </svg>
        </div>
        <div class="persona-name">LEMON WARRIOR</div>
        <div class="jar-label">JAR 0</div>
        <div class="glass-count" id="count-0">0</div>
        <div class="glasses-label">GLASSES</div>
        <div class="progress-bar"><div class="progress-fill" id="progress-0"></div></div>
        <div class="pour-label" id="pour-label-0">&nbsp;</div>
        <div class="streak-badge" id="streak-0"></div>
        <button class="reset-btn" onclick="resetJar(0)">RESET</button>
    </div>

    <div class="vs-col">
        <div class="vs-text">VS</div>
        <div class="lead-pill" id="lead-pill">TIED</div>
    </div>

    <div class="card card-1" id="card-1">
        <div class="char-wrap" id="char-wrap-1">
        <svg id="char-1" class="char-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="38" fill="#3a8a30"/>
            <circle cx="50" cy="50" r="33" fill="#EAF3DE"/>
            <circle cx="50" cy="50" r="29" fill="#E8406A"/>
            <ellipse cx="38" cy="38" rx="2" ry="3" fill="#1a0808"/>
            <ellipse cx="62" cy="40" rx="2" ry="3" fill="#1a0808"/>
            <ellipse cx="42" cy="62" rx="2" ry="3" fill="#1a0808"/>
            <ellipse cx="60" cy="64" rx="2" ry="3" fill="#1a0808"/>
            <ellipse cx="50" cy="32" rx="2" ry="3" fill="#1a0808"/>
            <g id="melon-eyes">
                <ellipse cx="40" cy="48" rx="6" ry="7.5" fill="#fff"/>
                <ellipse cx="60" cy="48" rx="6" ry="7.5" fill="#fff"/>
                <circle cx="40" cy="48" r="3.5" fill="#1f0c0c"/>
                <circle cx="60" cy="48" r="3.5" fill="#1f0c0c"/>
                <circle cx="41.4" cy="46.2" r="1.3" fill="#fff"/>
                <circle cx="61.4" cy="46.2" r="1.3" fill="#fff"/>
            </g>
            <path id="melon-mouth" d="M42 62 Q50 66 58 62" stroke="#1f0c0c" stroke-width="3" fill="none" stroke-linecap="round"/>
            <g id="melon-blush" opacity="0">
                <ellipse cx="28" cy="56" rx="6" ry="4" fill="#FF9090"/>
                <ellipse cx="72" cy="56" rx="6" ry="4" fill="#FF9090"/>
            </g>
        </svg>
        </div>
        <div class="persona-name">MELON CRUSHER</div>
        <div class="jar-label">JAR 1</div>
        <div class="glass-count" id="count-1">0</div>
        <div class="glasses-label">GLASSES</div>
        <div class="progress-bar"><div class="progress-fill" id="progress-1"></div></div>
        <div class="pour-label" id="pour-label-1">&nbsp;</div>
        <div class="streak-badge" id="streak-1"></div>
        <button class="reset-btn" onclick="resetJar(1)">RESET</button>
    </div>

</div>

<div class="status-row">
    <span class="status-dot" id="status-dot"></span>
    <span id="status-text">CONNECTING...</span>
    <div id="qr-wrap" style="position:absolute; right:16px; bottom:6px; text-align:center;">
        <img src="/static/qr.png" style="height:52px; width:52px; opacity:0.85; display:block;"
             onerror="this.parentElement.style.display='none'">
        <div style="font-size:6px; letter-spacing:1.5px; color:#2b2b2b; text-transform:uppercase; margin-top:3px;">SCAN TO KNOW MORE</div>
    </div>
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
        neutral: 'M42 66 Q50 70 58 66',
        excited: 'M38 63 Q50 76 62 63',
        grin:    'M30 63 Q50 84 70 63'
    },
    '1': {
        neutral: 'M42 62 Q50 66 58 62',
        excited: 'M38 58 Q50 72 62 58',
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

socket.on('connect',    () => { el('status-text').textContent = 'CONNECTED'; });
socket.on('disconnect', () => { el('status-text').textContent = 'RECONNECTING...'; });

socket.on('state', (data) => {
    const gc  = data.glass_count    || {};
    const pg  = data.partial_g      || {};
    const vol = data.glass_volume_g || 150;

    el('served-count').textContent = data.all_time_served ?? 0;

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
            const scoreColor = n === 0 ? '#a8d84a' : '#e8608a';

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
            if (newStreak >= 3 && newStreak % 2 === 1) playSound('fanfare');
        } else {
            el('count-' + n).textContent = String(newCount);
        }
        prevCount[ns] = newCount;

        const badge = el('streak-' + n);
        if (streak[ns] >= 2) {
            const fires = '🔥'.repeat(Math.min(streak[ns], 5));
            badge.textContent   = fires + ' ' + streak[ns] + '-POUR STREAK';
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    });

    // ── Lead pill ──
    const c0   = gc['0'] ?? 0;
    const c1   = gc['1'] ?? 0;
    const pill = el('lead-pill');
    const pillBase = 'padding:4px 8px;border-radius:20px;font-size:7px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;';
    if (c0 > c1) {
        pill.textContent = 'LEMON LEADS';
        pill.style.cssText = pillBase + 'background:#0d1508;color:#a8d84a;border:1px solid #4a6a1a;';
    } else if (c1 > c0) {
        pill.textContent = 'MELON LEADS';
        pill.style.cssText = pillBase + 'background:#150a12;color:#e8608a;border:1px solid #7a2a4a;';
    } else {
        pill.textContent = 'TIED';
        pill.style.cssText = pillBase + 'background:#1a1a1a;color:#3a3a3a;border:1px solid #2a2a2a;';
    }

    // ── BLE status ──
    const bleStatus = data.ble_status || {};
    const warnings  = [];
    [0, 1].forEach(n => {
        if ((bleStatus[String(n)] || 'connected') === 'disconnected')
            warnings.push('JAR ' + n + ' RECONNECTING');
    });
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
    if (w === '0')      { name = 'LEMON WARRIOR'; color = '#a8d84a'; isDraw = false; }
    else if (w === '1') { name = 'MELON CRUSHER';  color = '#e8608a'; isDraw = false; }
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
            [0, 1].forEach(i => {
                const badge = el('streak-' + i);
                badge.style.display = 'none';
                badge.textContent   = '';
            });
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

        @self._sio.on('connect')
        def _on_browser_connect():
            # WHY: push state immediately to reconnecting browser.
            # Without this, browser shows HTML default (0) for up to 500ms
            # while waiting for next _push_loop cycle — looks like score reset.
            state = self._game.get_state()
            emit('state', self._build_payload(state))

    def _build_payload(self, state: dict) -> dict:
        now = time.time()
        if now - self._all_time_served_ts >= 5.0:
            self._all_time_served    = self._storage.get_all_time_glasses()
            self._all_time_served_ts = now
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

    def _push_loop(self):
        """
        Background task: poll game state every 500ms, push to all browsers.
        Runs as a daemon thread (started by start_background_task).
        game.get_state() is Lock-protected - safe to call from any thread.
        """
        while True:
            state = self._game.get_state()
            self._sio.emit('state', self._build_payload(state))
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
