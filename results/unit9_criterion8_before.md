# Unit 9 — Criterion 8 (log completeness), before

Run: 20 requests against `https://fitfindr-wyt6.onrender.com/ask`, fired
sequentially, 2026-11-18 05:12:10–05:13:25 UTC — 5 matching queries, 5
impossible queries, 5 missing-`query` bodies, 5 malformed-`wardrobe` bodies
(items missing `name`/`category`/`colors`/`style_tags`, which
`tools.py::suggest_outfit` indexes directly — reachable without touching the
deployed code).

Full raw trace (Render logs, chronological): `unit9_criterion8_before_raw.txt`.

## What happened

The first 8 requests (all 5 matching queries + the first 3 impossible
queries) completed normally and each produced one correct structured log
line (`request_id` 2–9 — `request_id` 1 was an earlier manual verification
call outside this run's window). Then:

```
05:13:01.53  [rate limit] 15 requests used this minute. Waiting 15s. This is normal.
05:13:15.49  [INFO] Handling signal: term
05:13:20.95  ==> Instance srv-dbuj2duk1f9s73adsst0-r7bmt restarted
05:13:33.26  [INFO] Starting gunicorn 23.0.0
```

`gunicorn serve:app` with no `--workers`/`--threads` flag runs one thread
total. `generate.py`'s own rate limiter correctly started a 15s pacing
sleep on the 16th model call of the minute — but that sleep blocks the
*only* thread the process has, including the one that would answer
Render's own `/health` poll (observed every ~5s in the logs, both before
and after this incident). After several missed health checks, Render
concluded the instance was dead and force-restarted it. The in-flight
request (impossible query 4, `graphic tee under $5`) was killed mid-parse.
The remaining 11 requests (impossible query 5 + all 5 missing-query +
all 5 malformed-wardrobe tries) arrived during the ~18s restart window and
got an immediate 502 from Render's edge proxy — they never reached Flask,
so they produced zero app-level log lines.

## Scorecard

| Outcome | Count |
|---|---|
| Requests sent | 20 |
| Structured JSON log lines produced | 8 |
| Of those 8, `status` field correct | 8 of 8 |
| Requests that got an HTTP response but **no** log line | 1 (impossible query 4 — killed mid-request) |
| Requests that never reached the app at all (502 during restart) | 11 |

**Target: 20 of 20. Actual: 8 of 20. MISSED.**

## Diagnosis

- **Where:** not a logging bug and not a bug in the criterion's wording — an
  infrastructure/concurrency-model mismatch. `serve.py`'s single-lock design
  (needed so `generate.py`'s module-level rate/token counters and
  `mcp_client.call_tool`'s per-call subprocess spawns aren't shared across
  concurrent runs) was built assuming the only cost of "one thread" is that
  a second *user* request waits. It does not account for the host's own
  health check needing a thread too.
- **Mechanism:** any single `/ask` call that blocks the one thread for
  longer than Render tolerates a few missed health checks — a rate-limit
  pace-wait, a slow model call, or an MCP subprocess spin-up — can trigger
  an unrelated, disruptive instance restart that destroys whatever request
  (or queue of requests) was in flight at the time, with no application-level
  record of what was lost.
- **Fix attempted:** switch the Render start command from `gunicorn
  serve:app` to `gunicorn --worker-class gthread --threads 4 serve:app`.
  `gthread` uses real OS threads, not an event loop, so
  `mcp_client.call_tool`'s `asyncio.run()` still works per-thread (unlike
  `gevent`/`eventlet`, which `serve.py`'s own docstring already rules out
  for that exact reason). `/health` can now be served on a free thread while
  `/ask` is blocked on another. The Python-level `_one_at_a_time` lock keeps
  serializing actual agent runs across those threads, so the one-run-at-a-
  time guarantee the rest of the design depends on is unchanged.
