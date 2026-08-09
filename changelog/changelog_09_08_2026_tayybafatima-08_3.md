# Changelog — feat/tayybafatima-08/mock-data-generator

## What changed
Added `bridge/mock_source.py` — generates a deterministic 30-minute greenhouse
temperature profile (ambient drift, a heater ramp, a fan-triggered cooldown,
and one guaranteed spike above 30°C) and replays it into the backend's real
`/api/v1/ingest` endpoint, matching the `Reading` model exactly.

## Why it matters
This unblocks every other workstream before real hardware exists — Unity, the
chat UI, and the automated tests can all develop against `MODE=mock` from
Day 6 AM instead of waiting on the Arduino. The fixed seed and fixed start
timestamp mean the same "interesting moment" (the >30°C spike) lands in the
same place every single run, which is what makes the demo reliable rather
than a coin flip on whether something interesting happens to occur.

Verified: two consecutive runs produce byte-identical CSV output; a full
181-row replay against a local test backend implementing the real ingest
contract returned HTTP 200 for every row.
