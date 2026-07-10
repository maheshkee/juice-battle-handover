# SESSION CLOSE PROTOCOL — Juice Battle

Follow this exactly at the end of every session.
No exceptions. No "I'll do it next time".

---

## Step 1 — Write the session record

Create `sessions/SNNN_description.md` where NNN is the next sequential number.
The 2–3 word slug describes what actually happened (not what was planned).

Contents:
- Date and session number
- What chunk was worked on
- What was implemented (file names, key decisions)
- Verified results (actual test output, not expected)
- Blockers encountered and their current status
- What changed from the original plan and why
- Any new hardware findings (mark VERIFIED vs DERIVED)

This file is permanent and immutable once the session ends.

---

## Step 2 — Update HANDOFF_FINAL.md (always replace, never append)

This is the single most important document in the project.
The next session reads this FIRST before doing anything.

Required sections:
```
# HANDOFF_FINAL — Juice Battle
# Updated: [date] Session S[NNN]

## Current position
[One sentence: what phase, what chunk, what state the system is in]

## What was just completed
[Bullet list of what this session did — linked to SNNN file]

## Exact next task
[Precise description of what to do next — specific enough for CLI]
[File to create or modify, what to implement, what to verify]

## Context needed for next session
[Anything the next session must know that isn't in documents]
[Active assumptions, open questions, in-progress work]

## Files changed this session
[List of every file touched, created, or deleted]

## Known issues / blockers
[Any unresolved problems and their current status]

## Hardware state
[What is connected, what is powered, what has been calibrated]
```

---

## Step 3 — Update PROJECT_CONTEXT.md

One-page current state. Always replace. Never append.
Should answer in under 30 seconds: where are we, what works, what's next.

---

## Step 4 — Update ARCHITECTURE.md if design changed

Only if the architecture changed this session.
If you changed a data schema, a module boundary, or a protocol choice → update it.
If you only implemented what was already designed → skip this step.

---

## Step 5 — Update RESEARCH.md if new hardware facts were discovered

Confirmed hardware behaviour goes here — not in session records.
Mark every entry as either VERIFIED (tested on real hardware) or DERIVED (calculated/inferred).
Never carry values forward from a different hardware platform without a re-derivation note.

---

## Step 6 — Append to LEARNINGS_AND_INSIGHTS.md if something surprised you

Format: `L-NNN: [what we learned and why it matters for future decisions]`

---

## What never goes in any document

- WiFi credentials or MQTT passwords (these go in `config.h` which is gitignored)
- Hostnames hardcoded — use `arduino@AQ3` (mDNS) not a static IP
- Tool names in git commit messages
- Estimated or assumed values presented as verified — always mark clearly
- The same fact in two documents — pick the one document whose job it is
- Architecture decisions mixed into LEARNINGS — they are different documents

---

## Opening prompt for next session

Start the next session with:

```
Project: Juice Battle
Read sessions/HANDOFF_FINAL.md fully before responding.
Today we [describe the chunk].
Confirm you have read the handoff and state our current position.
```

---

## Key principle

Real measured numbers → SESSIONS (SNNN files)
Why they matter → LEARNINGS_AND_INSIGHTS
Pure hardware facts → RESEARCH
Current state → PROJECT_CONTEXT
Design → ARCHITECTURE
Next task → HANDOFF_FINAL

Never mix these. Each document has exactly one job.
