"""
dashboard.py - Juice Battle live scoreboard
Flask + Socket.IO server. Reads game state on a timer, pushes to browser.
No game logic lives here. Display only.
"""

import time
import config
from flask import Flask, render_template, render_template_string, jsonify, make_response, request, redirect
from flask_socketio import SocketIO, emit

# ── Crowd-facing HTML template ─────────────────────────────────────────────
# Served once on browser connect. Socket.IO client loaded from local Flask-SocketIO
# server (/socket.io/socket.io.js) - no CDN dependency for offline market use.

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
@keyframes logoPulse {
  0%,100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255,255,255,0); }
  50% { transform: scale(1.02); box-shadow: 0 0 32px 8px rgba(255,255,255,0.06); }
}
@keyframes earth-rotate{from{transform:translateX(0)}to{transform:translateX(-250px)}}
@keyframes city-blink{0%,100%{opacity:0.85}50%{opacity:0.15}}
@keyframes india-pulse{0%,100%{r:5;opacity:0.9}50%{r:14;opacity:0.25}}
@keyframes pulse-ring{0%{r:5;opacity:0.8;stroke-width:2}100%{r:42;opacity:0;stroke-width:0.5}}
@keyframes data-travel{from{stroke-dashoffset:70}to{stroke-dashoffset:0}}
@keyframes sat-orbit-a{from{transform:rotate(0deg) translateX(0) rotate(0deg)}to{transform:rotate(360deg) translateX(0) rotate(-360deg)}}
@keyframes sat-orbit-b{from{transform:rotate(120deg)}to{transform:rotate(480deg)}}
@keyframes sat-orbit-c{from{transform:rotate(240deg)}to{transform:rotate(600deg)}}
@keyframes water-ripple{0%{r:4;opacity:0.8;stroke-width:2.5}100%{r:60;opacity:0;stroke-width:0.3}}
@keyframes particle-float{0%{transform:translateY(0);opacity:0.7}100%{transform:translateY(-180px);opacity:0}}
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
    const vol = data.glass_volume_g || {{ glass_volume_g }};


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
            updateJarFill(n, 0, {{ glass_volume_g }});
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

_OPS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Juice Battle Ops</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#080808;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:16px;max-width:420px;margin:0 auto}
h1{font-size:13px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#fff;text-align:center;padding:12px 0 4px}
.sub{text-align:center;font-size:11px;color:#444;margin-bottom:20px}
.section-label{font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#444;margin:16px 0 8px 2px}
.card{background:#111;border:0.5px solid #222;border-radius:12px;padding:12px;margin-bottom:4px}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:0.5px solid #1a1a1a}
.stat-row:last-child{border-bottom:none}
.stat-label{font-size:12px;color:#555}
.stat-val{font-size:12px;font-weight:600;color:#888}
.stat-val.green{color:#7ab52a}
.stat-val.amber{color:#e8901a}
.jar-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:0.5px solid #1a1a1a}
.jar-row:last-child{border-bottom:none}
.jar-name{font-size:12px;color:#888;font-weight:500;flex:1}
.jar-count{font-size:22px;font-weight:700;min-width:40px;text-align:center}
.adj-btns{display:flex;gap:8px}
.adj-btn{width:36px;height:36px;border-radius:8px;border:0.5px solid #333;background:#1a1a1a;color:#fff;font-size:20px;font-weight:400;cursor:pointer;display:flex;align-items:center;justify-content:center;user-select:none;transition:transform 0.1s}
.adj-btn:active{transform:scale(0.92)}
.adj-btn.plus{border-color:#2a4a1a;background:#141f0a;color:#7ab52a}
.adj-btn.minus{border-color:#4a1a1a;background:#1f0a0a;color:#e84040}
.btn-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.btn-grid.single{grid-template-columns:1fr}
.op-btn{padding:12px 8px;border-radius:10px;border:0.5px solid #2a2a2a;background:#111;color:#666;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;cursor:pointer;text-align:center;user-select:none;transition:transform 0.1s,opacity 0.1s}
.op-btn:active{transform:scale(0.96);opacity:0.8}
.op-btn.amber{border-color:#4a3010;background:#120e06;color:#e8901a}
.op-btn.red{border-color:#4a1010;background:#120606;color:#e84040}
.op-btn.green{border-color:#1a4010;background:#060f04;color:#7ab52a}
.op-btn.blue{border-color:#102a4a;background:#060c12;color:#3a8ae8}
.op-btn.gray{border-color:#2a2a2a;background:#111;color:#666}
.round-input-row{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.round-input-row input{flex:1;background:#1a1a1a;border:0.5px solid #333;border-radius:8px;color:#fff;font-size:16px;padding:10px 12px;text-align:center}
.round-input-row input:focus{outline:none;border-color:#555}
.vol-row{display:flex;align-items:center;gap:10px;padding:6px 0}
.vol-row label{font-size:11px;color:#555;min-width:60px}
.vol-row input[type=range]{flex:1;accent-color:#e8901a}
.vol-val{font-size:12px;color:#e8901a;min-width:32px;text-align:right;font-weight:600}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#1a1a1a;border:0.5px solid #333;border-radius:8px;padding:8px 16px;font-size:12px;color:#fff;opacity:0;transition:opacity 0.2s;pointer-events:none;white-space:nowrap}
.toast.show{opacity:1}
.confirm-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:99}
.confirm-overlay.show{display:flex}
.confirm-box{background:#111;border:0.5px solid #333;border-radius:16px;padding:24px;max-width:280px;width:90%;text-align:center}
.confirm-box h2{font-size:14px;font-weight:700;color:#e84040;margin-bottom:8px}
.confirm-box p{font-size:12px;color:#666;margin-bottom:20px;line-height:1.5}
.confirm-btns{display:grid;grid-template-columns:1fr 1fr;gap:8px}
</style>
</head>
<body>
<h1>Juice Battle Ops</h1>
<p class="sub">Operator panel</p>

<div class="section-label">Live status</div>
<div class="card">
  <div class="stat-row"><span class="stat-label">Session</span><span class="stat-val" id="st-slug">&mdash;</span></div>
  <div class="stat-row"><span class="stat-label">Round</span><span class="stat-val" id="st-round">&mdash;</span></div>
  <div class="stat-row"><span class="stat-label">Session glasses</span><span class="stat-val" id="st-sg">&mdash;</span></div>
  <div class="stat-row"><span class="stat-label">All-time</span><span class="stat-val" id="st-at">&mdash;</span></div>
  <div class="stat-row"><span class="stat-label">BLE</span><span class="stat-val green" id="st-ble">&mdash;</span></div>
</div>

<div class="section-label">Adjust glass count</div>
<div class="card">
  <div class="jar-row">
    <span class="jar-name">Lemon Warrior</span>
    <span class="jar-count" id="cnt-0">&mdash;</span>
    <div class="adj-btns">
      <div class="adj-btn minus" onclick="adjust(0,-1)">&minus;</div>
      <div class="adj-btn plus"  onclick="adjust(0,+1)">+</div>
    </div>
  </div>
  <div class="jar-row">
    <span class="jar-name">Melon Crusher</span>
    <span class="jar-count" id="cnt-1">&mdash;</span>
    <div class="adj-btns">
      <div class="adj-btn minus" onclick="adjust(1,-1)">&minus;</div>
      <div class="adj-btn plus"  onclick="adjust(1,+1)">+</div>
    </div>
  </div>
</div>

<div class="section-label">Round controls</div>
<div class="card">
  <div class="round-input-row">
    <input type="number" id="round-target" min="1" max="99" value="1" placeholder="Round #">
    <div class="op-btn amber" style="white-space:nowrap;padding:12px 14px" onclick="setRound()">Set round</div>
  </div>
  <div class="btn-grid">
    <div class="op-btn amber" onclick="post('/reset_rounds')">Reset to round 1</div>
    <div class="op-btn green" onclick="forceRoundEnd()">Force round end</div>
  </div>
</div>

<div class="section-label">Node controls</div>
<div class="card">
  <div class="btn-grid">
    <div class="op-btn blue" onclick="post('/reset/0')">Reset Lemon</div>
    <div class="op-btn blue" onclick="post('/reset/1')">Reset Melon</div>
  </div>
</div>

<div class="section-label">Audio</div>
<div class="card">
  <div class="vol-row">
    <label>Music vol</label>
    <input type="range" min="0" max="100" value="20" id="vol-slider"
           oninput="document.getElementById('vol-out').textContent=this.value+'%'"
           onchange="setVolume(this.value)">
    <span class="vol-val" id="vol-out">20%</span>
  </div>
  <div class="btn-grid" style="margin-top:8px">
    <div class="op-btn gray" onclick="post('/audio/pause')">Pause music</div>
    <div class="op-btn gray" onclick="post('/audio/resume')">Resume music</div>
  </div>
  <div class="btn-grid single" style="margin-top:8px">
    <div class="op-btn amber" onclick="audioNext()">Next track</div>
  </div>
  <div id="track-name" style="text-align:center;font-size:10px;color:#444;margin-top:8px">&mdash;</div>
</div>

<div class="section-label">Danger zone</div>
<div class="card">
  <div class="btn-grid">
    <div class="op-btn red" onclick="confirmAction('new-session')">New session</div>
    <div class="op-btn red" onclick="confirmAction('game-over')">Game over</div>
  </div>
</div>

<div class="toast" id="toast"></div>

<div class="confirm-overlay" id="confirm-overlay">
  <div class="confirm-box">
    <h2 id="confirm-title">Are you sure?</h2>
    <p id="confirm-msg">This cannot be undone.</p>
    <div class="confirm-btns">
      <div class="op-btn gray" onclick="closeConfirm()">Cancel</div>
      <div class="op-btn red" id="confirm-yes" onclick="doConfirm()">Confirm</div>
    </div>
  </div>
</div>

<script>
let _confirmAction = null;
const CONFIRM_COPY = {
  'new-session': {
    title: 'Start new session?',
    msg: 'Resets IoT counter, round wins, and round number. Cannot be undone.'
  },
  'game-over': {
    title: 'Trigger game over?',
    msg: 'Ends the current game and shows the winner overlay on the display.'
  }
};

function toast(msg, dur=2000){
  const t=document.getElementById('toast');
  t.textContent=msg;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),dur);
}

function post(url, body=null){
  const opts={method:'POST',headers:{'Content-Type':'application/json'}};
  if(body)opts.body=JSON.stringify(body);
  return fetch(url,opts).then(r=>r.json()).then(d=>{
    toast(d.ok===false?(d.error||'Error'):'Done');
    return d;
  }).catch(()=>toast('Network error'));
}

function adjust(node, delta){
  fetch('/adjust/'+node+'/'+delta,{method:'POST'})
    .then(r=>r.json()).then(d=>{
      if(d.ok!==false){
        document.getElementById('cnt-'+node).textContent=d.new_count??'?';
        toast((delta>0?'+1':'-1')+' on '+(node===0?'Lemon':'Melon'));
      }
    });
}

function setVolume(pct){
  post('/audio/volume',{level: parseFloat(pct)/100});
}

function audioNext(){
  fetch('/audio/next',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.ok){
      document.getElementById('track-name').textContent=d.track||'';
      toast('Now: '+d.track);
    }
  });
}

function setRound(){
  const n=parseInt(document.getElementById('round-target').value)||1;
  post('/set_round',{round:n});
}

function forceRoundEnd(){
  post('/force_round_end');
}

function confirmAction(action){
  _confirmAction=action;
  const c=CONFIRM_COPY[action]||{title:'Are you sure?',msg:''};
  document.getElementById('confirm-title').textContent=c.title;
  document.getElementById('confirm-msg').textContent=c.msg;
  document.getElementById('confirm-overlay').classList.add('show');
}

function closeConfirm(){
  document.getElementById('confirm-overlay').classList.remove('show');
  _confirmAction=null;
}

function doConfirm(){
  closeConfirm();
  if(_confirmAction==='new-session'){
    post('/new_session');
  } else if(_confirmAction==='game-over'){
    post('/game_over');
  }
}

function refreshStatus(){
  fetch('/state').then(r=>r.json()).then(d=>{
    const gc=d.glass_count||{};
    document.getElementById('cnt-0').textContent=gc['0']??0;
    document.getElementById('cnt-1').textContent=gc['1']??0;
    document.getElementById('st-round').textContent='Round '+(d.round_number||1);
    document.getElementById('st-sg').textContent=(d.session_glasses??0)+' glasses';
    document.getElementById('st-at').textContent=(d.all_time_served??0)+' all-time';
    const ble=d.ble_status||{};
    const both=ble['0']==='connected'&&ble['1']==='connected';
    const el=document.getElementById('st-ble');
    el.textContent=both?'Both connected':'Check nodes';
    el.className='stat-val '+(both?'green':'amber');
  }).catch(()=>{});
}

refreshStatus();
setInterval(refreshStatus, 3000);
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

    def __init__(self, game, storage=None, ambient=None):
        # game instance injected by main.py - Dashboard never imports game directly
        self._game    = game
        self._ambient = ambient

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
        self._app.add_url_rule('/v4', 'index_v4', self._serve_v4)
        self._app.add_url_rule('/v5', 'index_v5', self._serve_v5)
        self._app.add_url_rule('/v6', 'index_v6', self._serve_v6)
        self._app.add_url_rule('/reset_rounds', 'reset_rounds',
                               self._reset_rounds, methods=['POST'])
        self._app.add_url_rule('/audio/volume', 'audio_volume',
                               self._audio_volume, methods=['POST'])
        self._app.add_url_rule('/audio/pause', 'audio_pause',
                               self._audio_pause, methods=['POST'])
        self._app.add_url_rule('/audio/resume', 'audio_resume',
                               self._audio_resume, methods=['POST'])
        self._app.add_url_rule('/audio/next', 'audio_next',
                               self._audio_next, methods=['POST'])
        self._app.add_url_rule('/audio/rescan_playlist', 'audio_rescan_playlist',
                               self._audio_rescan_playlist, methods=['POST'])
        self._app.add_url_rule('/ops', 'ops',
                               self._ops_page, methods=['GET'])
        self._app.add_url_rule('/new_session', 'new_session',
                               self._new_session, methods=['POST'])
        self._app.add_url_rule('/set_round', 'set_round',
                               self._set_round, methods=['POST'])
        self._app.add_url_rule('/force_round_end', 'force_round_end',
                               self._force_round_end, methods=['POST'])
        self._app.add_url_rule('/state', 'state_json',
                               self._state_json, methods=['GET'])

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
            'round_number':    state.get('round_number', 1),
            'round_size':      config.ROUND_SIZE,
            'live_fill_g':          state.get('live_fill_g', {0: None, 1: None}),
            'live_fill_updated_ms': state.get('live_fill_updated_ms', {0: None, 1: None}),
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

    def _audio_volume(self):
        if not self._ambient:
            return jsonify({'ok': False, 'error': 'no ambient player'})
        data  = request.get_json(silent=True) or {}
        level = float(data.get('level', 0.4))
        new   = self._ambient.set_music_volume(level)
        return jsonify({'ok': True, 'volume': round(new, 2)})

    def _audio_pause(self):
        if not self._ambient:
            return jsonify({'ok': False, 'error': 'no ambient player'})
        self._ambient.pause_music()
        return jsonify({'ok': True, 'state': 'paused'})

    def _audio_resume(self):
        if not self._ambient:
            return jsonify({'ok': False, 'error': 'no ambient player'})
        self._ambient.resume_music()
        return jsonify({'ok': True, 'state': 'playing'})

    def _audio_next(self):
        if not self._ambient:
            return jsonify({'ok': False, 'error': 'no ambient player'})
        track = self._ambient.next_track()
        return jsonify({'ok': True, 'track': track})

    def _audio_rescan_playlist(self):
        if self._ambient is None:
            return jsonify({"error": "no ambient player"}), 503
        result = self._ambient.rescan_playlist()
        return jsonify(result)

    def _ops_page(self):
        return render_template_string(_OPS_HTML)

    def _new_session(self):
        """Force-start a new session. Resets round number,
        round wins, and opens a fresh DB session."""
        import datetime as _dt
        with self._game._lock:
            # Close current session
            self._storage.close_session(self._game._session_id)
            # Clear round results
            self._storage.clear_round_results(self._game._session_id)
            # Open fresh session
            slug = _dt.datetime.now().strftime("%Y-%m-%d") + "-new"
            new_id = self._storage.open_session(2, slug=slug)
            self._game._session_id = new_id
            # Reset all counters
            self._game._glass_count = {0: 0, 1: 0}
            self._game.round_number = 1
            self._game.glasses_this_round = 0
            self._storage.set_round_number(1)
            self._storage.set_kv('service_stopped_cleanly', 'false')
            # Reset dashboard caches
            self._round_wins         = {'lemon': 0, 'melon': 0, 'tie': 0}
            self._round_wins_ts      = 0.0
            self._session_glasses    = 0
            self._session_glasses_ts = 0.0
        self._sio.emit('state', self._build_payload(self._game.get_state()))
        return jsonify({'ok': True, 'session_id': new_id, 'slug': slug})

    def _set_round(self):
        """Set round number to any value. Operator use only."""
        data = request.get_json(silent=True) or {}
        n = max(1, int(data.get('round', 1)))
        self._game.round_number = n
        self._storage.set_round_number(n)
        self._sio.emit('state', self._build_payload(self._game.get_state()))
        return jsonify({'ok': True, 'round_number': n})

    def _force_round_end(self):
        """Manually trigger round end from ops panel."""
        self._game._trigger_round_end()
        return jsonify({'ok': True})

    def _state_json(self):
        return jsonify(self._build_payload(self._game.get_state()))

    def _serve_index(self):
        """Alias: redirect to the active dashboard version so '/' never goes stale."""
        return redirect(f'/{config.ACTIVE_DASHBOARD_VERSION}', code=302)

    def _serve_v2(self):
        """Serve the crowd-facing v2 dashboard."""
        return render_template_string(HTML_V2, glass_volume_g=config.GLASS_VOLUME_G)

    def _reset_rounds(self):
        self._storage.set_round_number(1)
        self._game.round_number = 1
        # Option A: full tournament reset — clear round win history too
        # WHY: resetting to round 1 means starting a fresh tournament;
        # stale win counts from the previous tournament are misleading
        self._storage.clear_round_results(self._game._session_id)
        self._round_wins    = {'lemon': 0, 'melon': 0, 'tie': 0}
        self._round_wins_ts = 0.0
        self._game.glasses_this_round = 0
        self._game._round_in_progress = True
        return jsonify({'status': 'ok', 'round_number': 1})

    def _serve_v4(self):
        """Serve the v4 crowd-facing dashboard — Claude Design visual style."""
        response = make_response(render_template('v4.html'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    def _serve_v5(self):
        """Serve the v5 crowd-facing dashboard — Claude Design visual style."""
        response = make_response(render_template('v5.html'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    def _serve_v6(self):
            """Serve the v6 crowd-facing dashboard — Claude Design visual style."""
            response = make_response(render_template('v6.html'))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

    def _serve_v3(self):
        """Serve the crowd-facing v3 dashboard with atmospheric background and cause panel."""
        response = make_response(render_template('v3.html'))
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
