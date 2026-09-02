# Juice Battle — Remaining Scope & Next-Version Candidates
Draft — review and edit before this goes into the repo. Not yet placed by CLI.

---

## What's left in the current version (v5)

These are scoped or in-progress items, not yet closed:

- **Dashboard v5, Chunk 4 — backend live fill-level streaming.** Scoped, not implemented.
  Firmware message `MSG_DIAG` (5s cadence) identified as the data source. Chunks 1–3 are
  confirmed live on production `/v5`.
- **Ambient audio crash on service restart.** `pygame.error: mixer not initialized`, ALSA
  reports `no such device`. Surfaced, not yet root-caused.
- **JB-1 occasional disconnects.** Root cause identified as a 4-second GATT blind-window race
  condition (`abort_event` threading in `ble_scanner.py`). Partially mitigated — not fully closed.
- **Codebase migration to company repos.** Blocked on: (1) confirming the name of the second
  target org/repo, (2) setting up push credentials on the dev machine for both remotes.
  Decision already made to preserve full git history rather than a clean snapshot.
- **New ambient voice line (gTTS)** + simplification of `play_round_begin()` in `hub/ambient.py`.
  Queued, not started.
- **Perfboard/PCB build.** Continuity check (multimeter beep mode) on four crossover wires
  (PDWN, DOUT, SCLK, A0) required before first power-on. Soldering not started.

## Known open issues (carry forward regardless of version)

- **Watchdog design flaw:** `watchdog_fn` keys off a single global `last_packet_time`. One
  healthy node feeds it indefinitely while the other is dead, so the adapter-reset path never
  triggers in exactly the failure mode it was built to catch. Needs per-node tracking.
- **Undocumented concurrent changes:** a colleague has made live changes to the system
  (e.g. a PulseAudio systemd override) that aren't captured in any handoff doc yet. Worth
  reconciling before the UI handoff so the incoming colleague isn't debugging against
  undocumented state.

---

## Candidate features — next version (draft, needs your call)

These are pulled from the original project roadmap's later phases (integration/testing,
field polish) that were never built, plus natural extensions of work already in flight.
None of these are committed — flagging them so you can accept, reject, or reprioritize.

- [ ] **Historical trend / analytics view** — once Chunk 4 streams live fill-level data, persist
      it for a post-session view (busiest hour, biggest single pour, etc.)
- [ ] **Operator controls on dashboard** — tare all scales, reset match, pause/resume, without
      SSH access. From the original field-polish phase, never built.
- [ ] **Auto-recovery after power cycle** — reconnect BLE and resume game state automatically
      instead of requiring a manual restart. Also from field-polish phase.
- [ ] **Scale beyond 2 jars** — node ID assignment is currently hardcoded to JB-0/JB-1 only.
- [ ] **Stale-node indicator on dashboard** — a node going offline is currently silent to the
      crowd-facing display; only visible in logs.

---
*Draft generated 2026-08-31. Placement into the repo (path, filename convention) is pending
the doc-location audit — see Chunk 2.*
