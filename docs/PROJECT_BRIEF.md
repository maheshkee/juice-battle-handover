# PROJECT BRIEF — Juice Battle

## Vision

A live, crowd-facing competition system for market stalls.
Two juice jars sit on weight scales. As visitors pour juice, their jar's persona gains points,
reacts emotionally, and battles the rival on a real-time animated dashboard.
The goal is to attract attention, drive engagement, and make choosing a juice fun.

---

## Problem it solves

Market stalls selling juice have no engagement mechanism.
People pick a juice passively, pour it, and leave.
This system turns every pour into a visible game event — creating social proof,
crowd curiosity, and repeat visits to see who's winning.

---

## MVP (what we build first)

- Two ESP32-C3 sensor nodes, one per jar, each with CZL601 + ADS1232
- Weight data transmitted over WiFi to the UNO Q hub
- Hub detects pour events and calculates volume drawn in ml
- Hub runs a simple scoring system: ml poured = points
- Live web dashboard served from the UNO Q via App Lab
- Dashboard shows two jar personas, scores, and a recent-event feed
- Operator can tare both scales and reset the game from the dashboard

**MVP does NOT require:**
- Animations (static UI is fine for MVP)
- Persona emotion states (static character images are fine)
- Sound / buzzer
- Historical analytics or graphs

---

## Non-goals (explicitly out of scope)

- Mobile app
- Cloud connectivity or remote dashboard
- Multiple jars (system designed for exactly 2)
- Any external payment or ordering integration
- Long-term data retention (session-only is fine for MVP)

---

## Future features (post-MVP, do not implement now)

- Animated persona reactions (happy, sad, taunting, celebrating)
- Battle narrative text feed ("Orange attacks! +15 points!")
- Crowd voting / QR code interaction
- Historical leaderboard across stall sessions
- Audio reactions (buzzer + sound effects)
- 4-jar expansion (modular receiver supports N nodes)
- Operator analytics dashboard

---

## Constraints

### Hardware
- UNO Q: 2GB RAM, 16GB eMMC (or 4GB/32GB variant)
- ESP32-C3 SuperMini: 3.3V GPIO, WiFi 2.4GHz only
- ADS1232: AVDD=5V, DVDD=3.3V, SPI-like bit-bang protocol
- CZL601: single-point load cell, 5kg or 10kg rated capacity (confirm per unit)

### Network
- All devices on the same WiFi network (local LAN only)
- No internet connectivity required
- MQTT broker runs on the UNO Q (localhost) or on the LAN router

### Power
- UNO Q powered via USB-C barrel jack
- ESP32 nodes powered via USB-C (from phone chargers or a USB hub)

### Environmental
- Used at a market stall — bright outdoor or semi-outdoor conditions
- Dashboard must be visible in daylight
- System must survive being powered off between market days (cold-start recovery)

---

## Success criteria for MVP

1. A pour of 200ml is detected and registered within 3 seconds
2. Both nodes stream reliably for 2+ hours without manual intervention
3. Dashboard reflects a pour event within 5 seconds of it happening
4. Cold start to fully operational in under 60 seconds
5. An operator with no technical background can tare the scales and reset the game
