"""
feature/full-ui branch only. Not used by main, serve.py, or anything graded.

The one place webapp.py talks to Supabase — one client, built once, reused
across requests (the official client is safe to share across threads; it
just wraps an HTTP session).

Design decision worth stating up front: webapp.py never hands a Supabase
access token to the browser and never runs a Supabase client in JS. Supabase
Auth is used purely to verify a password and look up/create a user; once
that succeeds, Flask's own signed session cookie (see auth.py) is the only
thing that says "this request is logged in as user X" from then on. Every
database call below uses the **service role** key, which bypasses Row-Level
Security entirely, so every function here takes a user_id and filters by it
explicitly — the RLS policies in supabase/schema.sql are real and correct,
but they're defense-in-depth for a future browser-side client, not what's
protecting these routes today. If this key or the filtering below ever has a
bug, there is no second gate.
"""

import os

from supabase import create_client, Client

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

_client: Client | None = None


class SupabaseNotConfigured(Exception):
    """Raised when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY aren't set."""


def get_client() -> Client:
    global _client
    if _client is None:
        if not _SUPABASE_URL or not _SUPABASE_KEY:
            raise SupabaseNotConfigured(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env "
                "(feature/full-ui branch only — see .env.example)."
            )
        _client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    return _client


# ── auth ──────────────────────────────────────────────────────────────────────

def sign_up(email: str, password: str) -> dict:
    """
    Returns {"user_id": str, "needs_confirmation": bool}.

    needs_confirmation is True when the Supabase project requires email
    confirmation before a session is issued — sign_up() then returns a user
    but no session. webapp.py shows "check your email" rather than logging
    the user in.
    """
    client = get_client()
    res = client.auth.sign_up({"email": email, "password": password})
    if res.user is None:
        raise ValueError("Sign-up failed — Supabase returned no user.")
    return {
        "user_id": res.user.id,
        "needs_confirmation": res.session is None,
    }


def sign_in(email: str, password: str) -> str:
    """Returns the user_id on success. Raises on bad credentials."""
    client = get_client()
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    if res.user is None:
        raise ValueError("Invalid email or password.")
    return res.user.id


# ── wardrobe ──────────────────────────────────────────────────────────────────

def list_wardrobe_items(user_id: str) -> list[dict]:
    client = get_client()
    res = (
        client.table("wardrobe_items")
        .select("id, name, category, colors, style_tags, notes")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return res.data or []


def add_wardrobe_item(user_id: str, name: str, category: str,
                       colors: list[str], style_tags: list[str],
                       notes: str | None) -> dict:
    client = get_client()
    res = (
        client.table("wardrobe_items")
        .insert({
            "user_id": user_id,
            "name": name,
            "category": category,
            "colors": colors,
            "style_tags": style_tags,
            "notes": notes,
        })
        .execute()
    )
    return res.data[0]


def delete_wardrobe_item(user_id: str, item_id: str) -> None:
    client = get_client()
    client.table("wardrobe_items").delete().eq("id", item_id).eq("user_id", user_id).execute()


def wardrobe_dict_for(user_id: str) -> dict:
    """The shape run_agent() expects: {"items": [...]}. Empty is valid input."""
    return {"items": list_wardrobe_items(user_id)}


# ── search history ────────────────────────────────────────────────────────────

def save_search(user_id: str, query: str, session: dict) -> dict:
    """
    `session` is the dict run_agent() returned. search_results is dropped
    before storing — it's the full candidate list (up to 10 listings), and
    nothing downstream ever needs more than selected_item, which is kept.
    """
    client = get_client()
    trimmed = {k: v for k, v in session.items() if k != "search_results"}
    res = (
        client.table("search_history")
        .insert({"user_id": user_id, "query": query, "session": trimmed})
        .execute()
    )
    return res.data[0]


def list_search_history(user_id: str) -> list[dict]:
    client = get_client()
    res = (
        client.table("search_history")
        .select("id, query, session, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def get_search_history_entry(user_id: str, entry_id: str) -> dict | None:
    client = get_client()
    res = (
        client.table("search_history")
        .select("id, query, session, created_at")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


# ── favorites ─────────────────────────────────────────────────────────────────

def add_favorite(user_id: str, item: dict, outfit_suggestion: str, fit_card: str) -> dict:
    client = get_client()
    res = (
        client.table("favorites")
        .insert({
            "user_id": user_id,
            "item": item,
            "outfit_suggestion": outfit_suggestion,
            "fit_card": fit_card,
        })
        .execute()
    )
    return res.data[0]


def list_favorites(user_id: str) -> list[dict]:
    client = get_client()
    res = (
        client.table("favorites")
        .select("id, item, outfit_suggestion, fit_card, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def remove_favorite(user_id: str, favorite_id: str) -> None:
    client = get_client()
    client.table("favorites").delete().eq("id", favorite_id).eq("user_id", user_id).execute()
