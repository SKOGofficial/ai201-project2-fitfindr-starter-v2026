#!/usr/bin/env python3
"""
FitFindr with accounts — login, saved search history, a persisted wardrobe,
favorites. feature/full-ui branch only; not part of any graded unit.

    python webapp.py                      run it on your machine
    gunicorn webapp:app                   run it the way a host runs it

Separate from serve.py on purpose: serve.py is unit 9's graded artifact
(POST /ask, GET /health, nothing else) and this file never touches it. Both
import the same run_agent() from agent.py — neither has its own copy of the
agent loop.

Same reasons as serve.py apply to the one-at-a-time lock below: run_agent()
spawns an MCP subprocess per tool call and generate.py's rate/token counters
are plain module globals, so two overlapping agent runs in this process would
break both. gunicorn webapp:app with the default sync worker, same as
serve.py — not gevent/eventlet, for the same asyncio.run() reason documented
there.
"""

import json
import os
import secrets
import sys
import threading
import time
from typing import Optional

import config  # noqa: F401 — loads .env, fixes Windows console encoding

from flask import Flask, flash, redirect, render_template, request, session, url_for

import auth
import supabase_client as db
import trace as trace_module
from agent import run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

app = Flask(__name__)

_secret = os.getenv("FLASK_SECRET_KEY")
if not _secret:
    _secret = secrets.token_hex(32)
    print(
        "  [webapp] FLASK_SECRET_KEY not set — using a random key for this "
        "process. Sessions (logins) won't survive a restart. Set it in .env "
        "for anything longer-lived than local testing.",
        flush=True,
    )
app.secret_key = _secret

_one_at_a_time = threading.Lock()

# ── search cooldown ───────────────────────────────────────────────────────────
# Global, not per-user: generate.py's REQUESTS_PER_MINUTE pacing already
# protects the Gemini quota, but it does so by making a queued request wait
# silently — from the browser that just looks like the page is slow. This
# rejects a too-soon search immediately, with a message, before it ever
# touches the model or the one-at-a-time lock. That second part matters for
# Render specifically: this process has one lock guarding one agent run at a
# time, and each run spawns an MCP subprocess — a burst of searches (several
# people hitting a shared demo link at once, or one person double-clicking)
# would otherwise queue up holding threads and spawning subprocesses rather
# than failing fast.
#
# 8 seconds, not something stricter: a real search already takes ~7-9s (three
# model calls plus an MCP round trip), so this mostly closes the gap between
# "click again out of impatience" and "the previous search would have
# finished anyway" — it isn't meant to make normal use feel throttled.
SEARCH_COOLDOWN_SECONDS = int(os.getenv("SEARCH_COOLDOWN_SECONDS", "8"))

_cooldown_lock = threading.Lock()
_last_search_started_at = 0.0


def _seconds_until_search_allowed() -> float:
    """0.0 if a search may start now; otherwise how many seconds to wait.

    Claims the slot as a side effect when it returns 0.0, so two requests
    that check at nearly the same instant can't both pass — only one gets
    0.0, the other sees the time already claimed.
    """
    global _last_search_started_at
    with _cooldown_lock:
        now = time.monotonic()
        elapsed = now - _last_search_started_at
        if elapsed < SEARCH_COOLDOWN_SECONDS:
            return SEARCH_COOLDOWN_SECONDS - elapsed
        _last_search_started_at = now
        return 0.0


@app.context_processor
def inject_user():
    return {
        "user_id": auth.current_user_id(),
        "user_email": auth.current_user_email(),
    }


# ── timing telemetry ──────────────────────────────────────────────────────────
# Where does a search's ~7-9s actually go? run_agent() already calls
# trace.step() at each of its four points (parse, search, suggest_outfit,
# create_fit_card) — see trace.py. Rather than teach agent.py or trace.py
# anything new (both are shared with serve.py, the graded unit 9 artifact,
# and changing shared behavior there is out of scope for this branch), this
# wraps trace.step() for the duration of one call: record how long it's been
# since the last step, then call the real step() unchanged. The swap is safe
# without extra locking because `_one_at_a_time` already guarantees only one
# agent run — and so only one of these wrapped calls — executes at a time in
# this process.

def _run_agent_timed(query: str, wardrobe: dict):
    """Returns (result, total_seconds, step_timings) where step_timings is
    [(step_name, seconds_since_previous_step), ...]."""
    step_timings = []
    last = [time.perf_counter()]
    original_step = trace_module.step

    def timed_step(name, inputs=None, returned=None, note=""):
        now = time.perf_counter()
        step_timings.append((name, round(now - last[0], 3)))
        last[0] = now
        return original_step(name, inputs=inputs, returned=returned, note=note)

    trace_module.step = timed_step
    started = time.perf_counter()
    try:
        result = run_agent(query, wardrobe)
    finally:
        trace_module.step = original_step
    total = round(time.perf_counter() - started, 3)
    return result, total, step_timings


def _log_timing(query: str, total: float, step_timings: list) -> None:
    print(json.dumps({
        "route": "/search", "query_chars": len(query),
        "total_seconds": total,
        "steps": [{"name": n, "seconds": s} for n, s in step_timings],
    }), file=sys.stdout, flush=True)


# ── auth ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", active_page="login", narrow_page=True)

    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    try:
        user_id = db.sign_in(email, password)
    except Exception as exc:  # noqa: BLE001 — surface as a flash, not a 500
        flash(f"Couldn't log in: {exc}", "error")
        return redirect(url_for("login"))

    auth.log_in_as(user_id, email)
    flash("Logged in.", "success")
    return redirect(url_for("home"))


@app.post("/signup")
def signup():
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    try:
        result = db.sign_up(email, password)
    except Exception as exc:  # noqa: BLE001
        flash(f"Couldn't create account: {exc}", "error")
        return redirect(url_for("login"))

    if result["needs_confirmation"]:
        flash("Account created — check your email to confirm it, then log in.", "info")
        return redirect(url_for("login"))

    auth.log_in_as(result["user_id"], email)
    flash("Account created and logged in.", "success")
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    auth.log_out()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


@app.get("/settings")
def settings():
    return render_template("settings.html", active_page="settings", narrow_page=True)


# ── search ────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    wardrobe_count = None
    if auth.current_user_id():
        wardrobe_count = len(db.list_wardrobe_items(auth.current_user_id()))
    return render_template("home.html", active_page="home", wardrobe_count=wardrobe_count, narrow_page=True)


@app.post("/search")
def search():
    query = (request.form.get("query") or "").strip()
    if not query:
        flash("Enter something to search for.", "error")
        return redirect(url_for("home"))

    wait = _seconds_until_search_allowed()
    if wait > 0:
        flash(
            f"Please wait {wait:.0f}s before searching again — this protects "
            "the shared model quota and the server's single search slot.",
            "error",
        )
        return redirect(url_for("home"))

    user_id = auth.current_user_id()
    if user_id:
        wardrobe = db.wardrobe_dict_for(user_id)
    elif request.form.get("empty_wardrobe"):
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    with _one_at_a_time:
        result, elapsed_seconds, step_timings = _run_agent_timed(query, wardrobe)
    _log_timing(query, elapsed_seconds, step_timings)

    if user_id:
        try:
            db.save_search(user_id, query, result)
        except Exception as exc:  # noqa: BLE001 — a lost history row isn't fatal
            flash(f"Search succeeded, but saving it to history failed: {exc}", "error")

    session["last_result"] = {
        "query": query,
        "session": result,
        "saved": False,
        "elapsed_seconds": elapsed_seconds,
    }
    return redirect(url_for("results"))


@app.get("/results")
def results():
    last = session.get("last_result")
    if last is None:
        flash("No recent search to show.", "info")
        return redirect(url_for("home"))
    return _render_result(
        last["query"],
        last["session"],
        saved=last.get("saved", False),
        elapsed_seconds=last.get("elapsed_seconds"),
    )


def _render_result(
    query: str, result: dict, saved: bool, elapsed_seconds: Optional[float] = None
):
    if result.get("error"):
        return render_template("results.html", active_page="home", query=query,
                                error=result["error"], elapsed_seconds=elapsed_seconds,
                                narrow_page=True)
    return render_template(
        "results.html", active_page="home", query=query, error=None,
        item=result["selected_item"], outfit_suggestion=result["outfit_suggestion"],
        fit_card=result["fit_card"], saved=saved, elapsed_seconds=elapsed_seconds,
        narrow_page=True,
    )


@app.post("/favorite")
@auth.login_required
def favorite_this():
    last = session.get("last_result")
    if last is None or last["session"].get("error"):
        flash("Nothing to save.", "error")
        return redirect(url_for("home"))

    result = last["session"]
    db.add_favorite(
        auth.current_user_id(),
        result["selected_item"],
        result["outfit_suggestion"],
        result["fit_card"],
    )
    last["saved"] = True
    session["last_result"] = last
    flash("Saved to favorites.", "success")
    return redirect(url_for("results"))


# ── history ───────────────────────────────────────────────────────────────────

@app.get("/history")
@auth.login_required
def history():
    entries = db.list_search_history(auth.current_user_id())
    return render_template("history.html", active_page="history", entries=entries)


@app.get("/history/<entry_id>")
@auth.login_required
def history_entry(entry_id):
    entry = db.get_search_history_entry(auth.current_user_id(), entry_id)
    if entry is None:
        flash("That search wasn't found.", "error")
        return redirect(url_for("history"))
    return _render_result(entry["query"], entry["session"], saved=False)


# ── favorites ─────────────────────────────────────────────────────────────────

@app.get("/favorites")
@auth.login_required
def favorites():
    favs = db.list_favorites(auth.current_user_id())
    return render_template("favorites.html", active_page="favorites", favorites=favs)


@app.post("/favorites/<favorite_id>/remove")
@auth.login_required
def remove_favorite_route(favorite_id):
    db.remove_favorite(auth.current_user_id(), favorite_id)
    flash("Removed from favorites.", "info")
    return redirect(url_for("favorites"))


# ── wardrobe ──────────────────────────────────────────────────────────────────

@app.get("/profile")
@auth.login_required
def profile():
    items = db.list_wardrobe_items(auth.current_user_id())
    return render_template("profile.html", active_page="profile", items=items)


@app.post("/profile/add")
@auth.login_required
def add_wardrobe_item_route():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    if not name or not category:
        flash("Name and category are required.", "error")
        return redirect(url_for("profile"))

    colors = [c.strip() for c in (request.form.get("colors") or "").split(",") if c.strip()]
    style_tags = [t.strip() for t in (request.form.get("style_tags") or "").split(",") if t.strip()]
    notes = (request.form.get("notes") or "").strip() or None

    db.add_wardrobe_item(auth.current_user_id(), name, category, colors, style_tags, notes)
    flash("Added to your wardrobe.", "success")
    return redirect(url_for("profile"))


@app.post("/profile/<item_id>/delete")
@auth.login_required
def delete_wardrobe_item_route(item_id):
    db.delete_wardrobe_item(auth.current_user_id(), item_id)
    flash("Removed from your wardrobe.", "info")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    debug = os.getenv("AI201_DEBUG", "0") == "1"
    print(f"\nFitFindr (full UI) is listening on http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
