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

import os
import secrets
import threading

import config  # noqa: F401 — loads .env, fixes Windows console encoding

from flask import Flask, flash, redirect, render_template, request, session, url_for

import auth
import supabase_client as db
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


@app.context_processor
def inject_user():
    return {
        "user_id": auth.current_user_id(),
        "user_email": auth.current_user_email(),
    }


# ── auth ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", active_page="login")

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


# ── search ────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    wardrobe_count = None
    if auth.current_user_id():
        wardrobe_count = len(db.list_wardrobe_items(auth.current_user_id()))
    return render_template("home.html", active_page="home", wardrobe_count=wardrobe_count)


@app.post("/search")
def search():
    query = (request.form.get("query") or "").strip()
    if not query:
        flash("Enter something to search for.", "error")
        return redirect(url_for("home"))

    user_id = auth.current_user_id()
    if user_id:
        wardrobe = db.wardrobe_dict_for(user_id)
    elif request.form.get("empty_wardrobe"):
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    with _one_at_a_time:
        result = run_agent(query, wardrobe)

    if user_id:
        try:
            db.save_search(user_id, query, result)
        except Exception as exc:  # noqa: BLE001 — a lost history row isn't fatal
            flash(f"Search succeeded, but saving it to history failed: {exc}", "error")

    session["last_result"] = {"query": query, "session": result, "saved": False}
    return redirect(url_for("results"))


@app.get("/results")
def results():
    last = session.get("last_result")
    if last is None:
        flash("No recent search to show.", "info")
        return redirect(url_for("home"))
    return _render_result(last["query"], last["session"], saved=last.get("saved", False))


def _render_result(query: str, result: dict, saved: bool):
    if result.get("error"):
        return render_template("results.html", active_page="home", query=query, error=result["error"])
    return render_template(
        "results.html", active_page="home", query=query, error=None,
        item=result["selected_item"], outfit_suggestion=result["outfit_suggestion"],
        fit_card=result["fit_card"], saved=saved,
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
