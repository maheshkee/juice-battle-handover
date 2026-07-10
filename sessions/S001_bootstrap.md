# SESSION S001 — Bootstrap
# Date: 2026-07-10

## Chunk
Pre-Phase 0: Project Bootstrap
Goal: Establish working contracts, module architecture, directory structure.

## What was done
1. Defined 8-phase project lifecycle with Project Bootstrap as pre-Phase 0
2. Agreed on Chat (planning) vs CLI (implementation) working mode split
3. Defined orchestrator law: main.py and node.ino own zero logic
4. Analysed gas monitor — identified patterns to carry forward vs what is new
5. Confirmed ADS1232 (not HX711) for this project
6. Created full directory structure and all contract documents

## Decisions made
- ADS1232 confirmed (not HX711)
- Project root: /home/arduino/arduino_apps/juice_battle/
- Session naming: S001, S002... sequential, never resets
- HANDOFF_FINAL: always fully replaced, single file
- Module architecture: finalised in INTERFACE_CONTRACTS.md

## Verified results
All files created and reviewed. No hardware testing done yet.

## Open questions for Phase 0
- MQTT vs UDP for ESP32 → UNO Q
- Display hardware for dashboard
- Load cell capacity (5kg or 10kg) — check physical label
