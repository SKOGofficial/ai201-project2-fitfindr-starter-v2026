"""
feature/full-ui branch only. Not used by main or serve.py.

Flask's own signed session cookie is the single source of truth for "who is
logged in" (see the design note in supabase_client.py for why). This module
is just the two small pieces of glue that follow from that: reading/writing
the cookie, and a decorator that redirects to /login when it's empty.
"""

from functools import wraps

from flask import redirect, session, url_for


def log_in_as(user_id: str, email: str) -> None:
    session["user_id"] = user_id
    session["email"] = email


def log_out() -> None:
    session.clear()


def current_user_id() -> str | None:
    return session.get("user_id")


def current_user_email() -> str | None:
    return session.get("email")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user_id() is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped
