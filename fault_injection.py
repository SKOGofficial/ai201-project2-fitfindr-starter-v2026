#!/usr/bin/env python3
"""
Fault-injection test for the model adapter.   ← UNIT 4, MILESTONE 5

    python fault_injection.py

The real 503 that failed impossible-query try 4 was a one-off, so re-running the
full test can't show whether a fix works — it would probably pass either way.
This forces the failure instead: it replaces the model client with one that
answers with the exact text of that 503 (copied from results/scored_*_before.md),
then runs the real agent on the query that failed.

Three cases:
  1. one 503, then the service recovers   (what actually happened in the test)
  2. a 503 that never clears              (a real outage)
  3. a bad API key                        (must still fail fast — no retries)

Only the transport is faked; `agent.run_agent`, `generate.generate`, the MCP
search and the branch are all the real code. time.sleep inside generate.py is
replaced by a recorder so the test doesn't wait, and the delays it *would* have
slept are printed.
"""

import contextlib
import io
import re
import sys
import types
from time import monotonic

import config
config.CACHE_ENABLED = False

import agent
import generate

QUERY = "graphic tee under $5"      # the query that failed in the scored run

ERR_503 = ("503 UNAVAILABLE. {'error': {'code': 503, 'message': "
           "'The service is currently unavailable.', 'status': 'UNAVAILABLE'}}")
ERR_BAD_KEY = ("400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': "
               "'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT'}}")


class FlakyClient:
    """Raises `error` for the first `fail_first` calls (None = always), then delegates to `real`."""

    def __init__(self, error, fail_first, real=None):
        self.error, self.fail_first, self.real = error, fail_first, real
        self.calls = 0
        self.models = types.SimpleNamespace(generate_content=self._generate_content)

    def _generate_content(self, **kwargs):
        self.calls += 1
        if self.fail_first is None or self.calls <= self.fail_first:
            raise Exception(self.error)
        return self.real.models.generate_content(**kwargs)


def run_case(name, error, fail_first, expect, needs_real=False):
    real = generate._get_client() if needs_real else None      # build the real client first
    client = FlakyClient(error, fail_first, real)
    delays = []
    generate._client = client
    generate._call_times.clear()
    real_time = generate.time
    generate.time = types.SimpleNamespace(monotonic=monotonic, sleep=delays.append)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            session = agent.run_agent(QUERY, {"items": []})
    finally:
        generate.time = real_time
        generate._client = None

    message = session["error"] or ""
    ok, why = expect(session, client.calls, delays)
    print(f"--- {name}")
    print(f"    model requests made: {client.calls}   delays it would have slept: {delays}")
    print(f"    session['error']: {message!r}")
    print(f"    {'PASS' if ok else 'FAIL'}: {why}\n")
    return ok


def expect_recovers(session, calls, delays):
    if (session["error"] or "").startswith("(no match)") and calls >= 2:
        return True, "retried past the 503 and the run reached the branch normally"
    return False, "the run did not get past the 503"


def expect_clear_outage_message(session, calls, delays):
    message = session["error"] or ""
    if "{'error'" in message:
        return False, "the message still contains the raw error dict"
    if not re.search(r"wait|try again", message, re.I):
        return False, "the message doesn't tell the user what to do"
    if not message:
        return False, "no message"
    return True, f"readable message that says what to do, after {calls} request(s)"


def expect_fails_fast(session, calls, delays):
    message = session["error"] or ""
    if calls != 1 or delays:
        return False, f"retried a non-transient error ({calls} requests, delays {delays})"
    if "API key" not in message:
        return False, "message doesn't mention the API key"
    return True, "failed on the first request, no retries, message names the key"


if __name__ == "__main__":
    print(f"Query: {QUERY!r}   (cache off; only the model transport is faked)\n")
    results = [
        run_case("1. one 503, then the service recovers", ERR_503, 1, expect_recovers, needs_real=True),
        run_case("2. a 503 that never clears (outage)", ERR_503, None, expect_clear_outage_message),
        run_case("3. bad API key (must NOT retry)", ERR_BAD_KEY, None, expect_fails_fast),
    ]
    print(f"{sum(results)}/{len(results)} cases pass")
    sys.exit(0 if all(results) else 1)
