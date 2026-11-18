# Unit 9 — Criterion 8 (log completeness), after

Same 20 requests as the before run (`unit9_criterion8_before.md`), same
order, fired against `https://fitfindr-wyt6.onrender.com/ask` after
redeploying with `gunicorn --worker-class gthread --threads 4 serve:app`
(2026-11-18 05:19:53–05:22:23 UTC).

Full raw trace: `unit9_criterion8_after_raw.txt`.

## Scorecard

| Outcome | Count |
|---|---|
| Requests sent | 20 |
| Structured JSON log lines produced | 20 |
| `status` field matching the real outcome | 20 of 20 (5 `ok`, 5 `no_match`, 5 `bad_request`, 5 `error`) |
| Instance restarts during the run | 0 |

**Target: 20 of 20. Actual: 20 of 20. MET.**

## Why I believe this is the fix, not luck

`request_id: 2` (`90s track jacket in size M`) took **44991.1 ms** —
almost 45 seconds, the shape of a real rate-limit pacing wait, the exact
condition that killed the instance in the before run. This time `/health`
kept answering throughout (no restart event anywhere in the trace — the
before run's raw log had "Instance restarted" partway through; this one
has none), because a second gthread thread was free to serve it while the
request thread sat in `generate.py`'s rate-limiter sleep. The one
condition that caused the before failure recurred here and did not cause
the same failure.

The 5 `bad_request` tries all logged `duration_ms: 0.1` — correctly
instant, no model call attempted, matching `serve.py`'s 400 path. The 5
`error` tries reused the same query text as the very first request in
this run (`vintage graphic tee under $30`, cached from `request_id: 1`),
so their one model call (the parse step, which runs before the crash in
`suggest_outfit`) was a cache hit — `model_calls: 0, tokens: 0` is correct
for that reason, not because parsing was skipped. The ~4-5s each still
took is `search_listings`' real MCP subprocess round trip plus the crash.
