# Unit 9 — Criterion 7 (concurrency is really serialized)

5 trials, each firing two `/ask` requests at the same instant (`curl ... &`
twice, then `wait`) against `https://fitfindr-wyt6.onrender.com/ask`, after
the gthread fix (same deploy used for `unit9_criterion8_after.md`):
query A = `vintage graphic tee under $30` (expects `lst_002`), query B =
`denim jacket under $50` (expects `lst_007`). 2026-11-18 05:24:37–05:25:23
UTC. Raw log trace: `conc_test/logs_chrono.txt` (not committed — see note).

## Scorecard

| Trial | A got lst_002? | B got lst_007? | Exactly one `waited_for_lock: true`? |
|---|---|---|---|
| 1 | yes | yes | yes (request 32) |
| 2 | yes | yes | yes (request 34) |
| 3 | yes | yes | yes (request 36) |
| 4 | yes | yes | yes (request 38) |
| 5 | yes | yes | yes (request 40) |

**Target: 5 of 5. Actual: 5 of 5. MET.**

## Reading

Each pair shows one request logging `waited_for_lock: false` (it acquired
`_one_at_a_time` immediately) and the other `waited_for_lock: true` (it
queued), and the response bodies were never swapped — query A's response
always carried item `lst_002`, query B's always `lst_007`, even though
both requests were in flight on separate gthread threads at the same
moment. The lock still does its one job under real concurrent load; adding
threads for `/health` (the criterion 8 fix) didn't quietly break this
guarantee.

All ten calls in this run show `model_calls: 0` — both query strings were
already cached from the criterion 8 run moments earlier, so this measures
the lock and the MCP round trip, not fresh model latency. That's fine for
what this criterion checks (serialization and correctness of which item
goes where), but it means this run says nothing about whether the lock
holds up when two real (non-cached) model calls overlap — worth retesting
with the cache off if that distinction ever matters.
