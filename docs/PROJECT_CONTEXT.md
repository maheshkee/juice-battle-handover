# PROJECT CONTEXT — Juice Battle
# One-screen current state. Always replace. Never append.
# Last updated: Session S001 — Bootstrap

## Where we are
Phase: PROJECT BOOTSTRAP (Pre-Phase 0)
Current chunk: Creating project structure and working contracts.
System state: No code written yet. No hardware tested yet.

## What is working
Nothing yet. Bootstrap only.

## What was just done (S001)
- Agreed on project lifecycle (8 phases)
- Defined working mode: Claude Chat = thinking, Claude CLI = implementation
- Defined module architecture for both hub and ESP32 nodes
- Created full project directory structure and all contract documents
- Confirmed ADS1232 (not HX711) for this project
- Identified what transfers from gas monitor (patterns) vs what is new

## Open questions
- What communication protocol between ESP32 and UNO Q? (MQTT on localhost vs UDP)
  → Decision pending Phase 0 architecture session
- Display hardware for dashboard? (browser on attached screen, external monitor, tablet?)
  → Decision pending Phase 0

## Next task (Phase 0, Chunk 1)
Run git init and create the first commit.
Then begin Phase 0: Architecture & Clarity.
Start by confirming the MQTT vs UDP decision.

## Hardware status
- All hardware in hand
- Nothing wired yet
- Nothing calibrated yet

## Key files to know
- docs/ARCHITECTURE.md — system design (stub, Phase 0 will fill it)
- docs/INTERFACE_CONTRACTS.md — data schemas (stub, Phase 0 will fill it)
- docs/HARDWARE_MANIFEST.md — hardware inventory (specs to be verified)
- WORKING_CONTRACT.md — engineering rules
