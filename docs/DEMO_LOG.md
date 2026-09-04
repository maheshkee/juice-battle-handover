# Juice Battle — Demo Run Log

Test demos on AQ3 (the locked hub) in the run-up to the IoT Summit stall on
**15 Sep 2026, 09:00–17:00**. One row per run. "Duration" = powered-and-live time,
not counting setup.

| # | Date | Start (IST) | End (IST) | Duration | Gate (GLASS_VOLUME_G) | ROUND_SIZE | Notes |
|---|------|-------------|-----------|----------|-----------------------|------------|-------|
| 1 | 2026-09-04 | ~10:00 | ~12:00 | ~2 h | 120 g | 10 | First live run on AQ3. Pour ding missed at boot (mixer race) → SoundPlayer lazy-retry fix. `ble_status` recovery fix. Counts verified. |
| 2 | 2026-09-04 | 16:03 | 17:27 | ~1 h 24 min | 100 g | 10 | Gate 120→100 (120 too tight). `POUR_MAX_G_FRAC` 3.0→4.0 (ceiling → 400 g). **Distinct-pour guard** added mid-run after a live double-count bug (person A's sub-threshold leftover credited to person B). Session `2026-09-04-001`: 140 pour events, 121 glasses. First pour 16:04:52, last 17:26:08. User verdict: "its good". |

## How to close a row
When a demo ends, note the stop time, compute duration, and record anything that
broke or was tuned. The DB session's own start timestamp is the authoritative
"live from" mark if this log's estimate needs checking.
