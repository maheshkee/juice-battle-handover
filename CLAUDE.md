# CLAUDE.md — Juice Battle
# Current position updated: 2026-09-04 — AQ3 locked as production/demo hub

## Current position
Firmware and hub are both built and hardware-verified. This is no longer active
feature development — the project is in live product testing / demo, working
toward stall deployment. Both nodes (JB-0, JB-1) connect, score, and have each
completed a verified end-to-end pour test with correct glass counts (2026-08-20).

## Live-tuning during demo runs (2026-09-04)
- `GLASS_VOLUME_G` 150 → 120 → **100** g. 120 was "too tight" in live testing.
- `POUR_MAX_G_FRAC` 3.0 → **4.0** so the jar-lift ceiling holds at ~400 g after
  the gate drop (was heading to 300 g).
- **Distinct-pour guard added to `game.py` (billing-correctness fix).** Bug seen
  live: person A withdrew ~95 g (no glass), then person B withdrew ~105 g and the
  count jumped by **2** — A's leftover was credited to B. Fix: a `POUR_ACTIVE`
  since the last settle marks a physically separate pour; any sub-threshold
  partial from the previous pour is discarded (`DISTINCT_POUR_CLR`) before the
  new one is counted. Split-settle of ONE pour has no `POUR_ACTIVE` between
  fragments, so it still accumulates. Residual known gap: a very slow trickle
  (<~30 g/s) never fires `POUR_ACTIVE`, so it could still merge — uncommon at
  stall pour speeds. Verified: `hub/test_distinct_pour.py`, 5/5.
- Demo run times tracked in `docs/DEMO_LOG.md`.

## AQ3 is the locked production + demo board (2026-09-04)
Verified working reference: git tag **`demo-live-2026-09-04`** (commit `17b7612`).
On 2026-09-04 09:15 IST, AQ3 came up clean: scanner connected to both nodes in
~15 s, live HEARTBEAT/DIAG streaming, `/state` ble_status/node_status all good,
audio (music + announcements) audible with underruns NOT climbing, kiosk on `/v6`.
Both `juice-ble-scanner` and `juice-battle` are `enabled` on AQ3 → auto-start on
power-up. Nothing to type for a live session — just power on.
- **Dharanova-2 is NOT used as a hub.** Its on-board BLE could not hold a GATT
  link to the nodes (connect → drop within 4 s, both nodes, persistent through
  reboot + BlueZ cache clear + node power-cycle). The nodes themselves are fine —
  proven by AQ3 connecting to them immediately. Keep Dharanova-2's
  `juice-ble-scanner` + `juice-battle` **stopped and disabled**.
- **RULE: only ONE provisioned board may run `juice-ble-scanner` at a time.**
  Two BLE centrals racing the same node MACs each steal the link mid-handshake —
  this is what stalled the 2026-09-04 AM demo prep (AQ3's scanner was still
  enabled and holding both nodes while Dharanova-2 tried to connect).
- v6 dashboard now shows a per-node BLE indicator: `JB-0` / `JB-1` chips top-
  right of the centre panel — green + slow pulse = connected, solid amber =
  disconnected, grey = no state yet. Driven by `data.ble_status` in the Socket.IO
  `state` payload; `hub/game.py` `_node_status` defaults to `disconnected` and
  only flips to `connected` on a real `NODE_CONNECTED` from the scanner.

## Audio config is now repo-managed (2026-09-03)
The 2026-08-20 audio fix lived only as a hand-edited `~/.asoundrc` + a hand-edited
installed unit on AQ3 — never committed. A clone onto a second board (Dharanova-2)
ran `setup.sh` and got the pre-fix raw-`hw:` config → underrun storm again.
Now committed so any clone works from `setup.sh` alone:
- `hub/asoundrc` — canonical dmix config (byte-identical to AQ3's working file);
  `setup.sh` STEP 3 installs it to `~/.asoundrc` (backs up any existing one).
- `hub/juice-battle.service` — `AUDIODEV=hw:Device` removed (it bypassed dmix).
- `deploy.sh` now re-syncs unit files to `/etc/systemd/system` before restart, so
  the installed units can't silently drift from the repo again.
- `hub/setup.sh` and `hub/deploy.sh` were stale divergent copies — now thin
  wrappers that exec the root scripts.
All sound assets (incl. `flute.mp3`, `fuzzy_horizon.mp3`) are already committed,
so audio needs no internet/manual downloads — just `pygame` + the USB adapter.

## Board provisioning is now fully in `setup.sh` (2026-09-03)
More AQ3-only hand-fixes were folded into the repo so a clone + `setup.sh` yields
a working board with no further manual steps:
- `hub/udev/99-juice-battle-audio.rules`, `hub/udev/99-juice-pendrive.rules` —
  committed; `setup.sh` STEP 7 installs them. (Audio-replug restart + music-USB
  auto-mount previously only existed on AQ3 / in the retired `hub/setup.sh`.)
- `hub/lightdm/50-juice-battle-autologin.conf` — LightDM drop-in, no password at
  boot. `setup.sh` STEP 8. Mirrors AQ3's hand-edited `/etc/lightdm/lightdm.conf`.
- `hub/sudoers/juice-battle` — passwordless `systemctl` for the two JB services;
  `setup.sh` STEP 8 installs via `visudo -c`. (May be superseded by AQ3's exact
  existing `/etc/sudoers.d/juice-battle` if it differs — that file wins.)
- `setup.sh` STEP 8 also suppresses the Arduino App Lab autostart (the thing that
  popped a keyring/login prompt over the kiosk).
- `setup.sh` apt line now installs `python3-gi python3-dbus bluez chromium curl`
  (BLE scanner + kiosk deps that were assumed present).
- `requirements.txt` added; `setup.sh` uses it. `qrcode`/`pillow`/`dbus-python`
  dropped from the pip list — confirmed unused at runtime.
Autologin/kiosk changes need a reboot (or `systemctl restart lightdm`) to apply.
NOTE: the new `setup.sh` steps have NOT been run on a real board yet.

## What was just completed (2026-08-20)
- Audio: root-caused a "mixer not initialized" + underrun-storm failure to a
  stray PulseAudio override fighting raw `hw:` ALSA access. Fixed by routing
  `.asoundrc` through `dmix`; PulseAudio override retired (backed up, not
  deleted). Confirmed clean under sustained load + audible playback.
- Full end-to-end pour test verified for BOTH nodes: real positive deltas,
  correct split-pour accumulation, correct glass counting, correct round-end/
  tie logic, correct anomaly-ceiling rejection of jar-lift events. DB and
  `/state` reconciled exactly against the log.
- Docs cleanup pass started: `hub/README.md` rewritten, `hub/SYSTEM_RUNBOOK.md`
  spot-fixed (stale `/v3` kiosk URL → `/v4`, stale JB-1 MAC corrected), root
  `HANDOFF_FINAL.md` removed (superseded, S014-era).

## Open, unresolved as of today — do not assume settled
- **Calibration polarity investigation (Chunks 21/24b/26, 2026-08-20):** earlier
  the same day, JB-0 produced an inverted (negative) pour reading that never
  scored. Root-caused as far as source analysis allows: `ads1232.cpp`
  hardcodes a blanket ADC negation (`return -data`, comment: "green/white
  wires physically swapped") shared identically by both nodes with no
  per-node branching, while `cal.cpp`'s `cal_to_grams()` polarity fix
  (2026-08-13, tuned for JB-1's replacement chip) is a *global* sign flip,
  not a self-correcting one. If that fix reached JB-0 without a matching
  recalibration, JB-0's math and its S003-era NVS calibration would now
  disagree on sign — fully explains the symptom without needing a real wire
  fault. **Not confirmed** which firmware/NVS state each node is actually
  running — that requires physical/serial verification, not git archaeology.
  The later same-day test (Chunk 27) worked correctly on both nodes, so this
  did not block, but the root cause is not closed out.
- Root README.md's "test extraction repo, not the working repo" framing is
  contradicted by current git state (`origin` is 6 commits ahead of
  `project13/juice-battle-main`, 0 behind) — needs a real decision, not just
  a doc fix, on which repo is authoritative before relying on that framing.

## Locked rules (non-negotiable)
- Never hardcode thresholds that depend on sigma_live
- Orchestrator law: juicebattle.ino and hub/main.py own zero logic
- Hub = brain (accumulates, decides, scores). Node = sensor (detects, reports).
- Every C++ module returns {value_g, sigma_g, quality, diagnosis}
- delayMicroseconds(2) on every GPIO edge

## Corrected from earlier versions of this file
- ~~"NODE_ID lives only in config.h"~~ — no longer true. `NODE_ID` is resolved
  at boot from the BT MAC via a `NODE_MAC_TABLE` in `juicebattle.ino` itself
  (`resolve_node_id()`), specifically so one identical binary works on either
  node. Don't look for it in config.h.

## Recovered from duplicate — 2026-08-31
The block below is an S003-era snapshot preserved verbatim from the now-deleted
`docs/CLAUDE.md` (last updated 2026-07-16). **Historical only** — current state is
at the top of this file. The same session's full results also live in
`docs/SESSIONS.md` § S003.

> **Current position (as of S003, 2026-07-16):**
> S003 complete. Phase 1 firmware in progress.
> cal.cpp + scale.cpp written and verified on hardware.
> Next session S004: boot redesign (baseline replaces tare, noise under load).
> Session after S005: stability.cpp.
>
> **Completed in S003:**
> - Polarity bug found and fixed (negation in ads1232.cpp - TODO swap wires)
> - cal.h / cal.cpp written, 3-point piecewise model verified
> - 3 calibration runs completed. Best: Run1 confidence=0.968 sigma=2.54g
> - Validation sweep: 4/4 PASS. Worst 1.64% at 200g, best 0.03% at 10kg
> - scale.h / scale.cpp written, interactive scale verified on hardware
> - Boot design corrected: baseline = current platform state (no jar removal)
> - Noise must be measured under operating load, not empty platform
>
> **Locked values added in S003:**
> - CAL_MAX_ACCEPTABLE_SPREAD = 0.08f (derived from real CZL601 nonlinearity)
> - SCALE_NOISE_CLAMP_G = 6.0f
> - Best cal NVS: raw_zero=94690 raw_500=148353 raw_1000=201742 raw_5000=630410
> - Signal polarity: ads1232.cpp returns -raw_value (software fix, wire swap pending)
