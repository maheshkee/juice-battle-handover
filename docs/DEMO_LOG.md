# Juice Battle — Demo Run Log

Test demos on AQ3 (the locked hub) in the run-up to the IoT Summit stall on
**15 Sep 2026, 09:00–17:00**. One row per run. "Duration" = powered-and-live time,
not counting setup.

| # | Date | Start | End | Duration | Gate (GLASS_VOLUME_G) | ROUND_SIZE | Notes |
|---|------|-------|-----|----------|-----------------------|------------|-------|
| 1 | 2026-09-04 | ~10:00 IST | ~12:00 IST | ~2 h | 120 g | 10 | First live run on AQ3. Pour ding missed at boot (mixer race) → SoundPlayer lazy-retry fix. `ble_status` recovery fix. Counts verified. |
| 2 | 2026-09-04 | 15:45 IST | — | (running) | 100 g | 10 | Gate lowered 120→100 (120 felt too tight). `POUR_MAX_G_FRAC` 3.0→4.0 to hold the jar-lift ceiling near 360 g (now 400 g). Fresh DB. |

## How to close a row
When a demo ends, note the stop time, compute duration, and record anything that
broke or was tuned. The DB session's own start timestamp is the authoritative
"live from" mark if this log's estimate needs checking.
