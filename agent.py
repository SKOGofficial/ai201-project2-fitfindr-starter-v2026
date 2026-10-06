"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import json
import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable, generate


FROM_DATABASE_TAG = "(from database)"
NO_MATCH_TAG = "(no match)"

_PARSE_PROMPT = """Extract search filters from this secondhand clothing request.
Reply with ONLY a JSON object with exactly these keys:
  "description": the item keywords (string, without the size or price words),
  "size": the size requested as a string such as "M" or "US 8", or null,
  "max_price": the price ceiling as a number, or null.

Request: {query}"""


def _parse_query(query: str) -> dict:
    """Ask the model for description / size / max_price. Falls back to the raw query."""
    fallback = {"description": query, "size": None, "max_price": None}
    raw = generate(_PARSE_PROMPT.format(query=query), temperature=0.0)
    match = re.search(r"{.*}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0))
    except (AttributeError, ValueError):
        return fallback
    size = data.get("size")
    price = data.get("max_price")
    try:
        price = float(price) if price is not None else None
    except (TypeError, ValueError):
        price = None
    return {
        "description": str(data.get("description") or query),
        "size": str(size) if size else None,
        "max_price": price,
    }


def _no_match_message(parsed: dict) -> str:
    tried = [f"'{parsed['description']}'"]
    if parsed["size"]:
        tried.append(f"size {parsed['size']}")
    if parsed["max_price"] is not None:
        tried.append(f"under ${parsed['max_price']:g}")
    loosen = ["different keywords"]
    if parsed["size"]:
        loosen.append("a different size or none")
    if parsed["max_price"] is not None:
        loosen.append("a higher budget")
    return (
        f"{NO_MATCH_TAG} Nothing matched {', '.join(tried)}. "
        f"Try {', '.join(loosen)}."
    )


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    TODO — build this, following the branch rule you wrote in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings() with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)

    # The loop looks at what the last step produced before choosing the next one.
    step_name = "parse"
    count = 0
    try:
        while step_name != "done":
            count += 1
            trace.check_iterations(count)

            if step_name == "parse":
                session["parsed"] = _parse_query(query)
                step_name = "search"

            elif step_name == "search":
                parsed = session["parsed"]
                session["search_results"] = search_listings(
                    parsed["description"], parsed["size"], parsed["max_price"]
                )
                # THE BRANCH: nothing found -> explain and stop; fit_card stays None.
                if not session["search_results"]:
                    session["error"] = _no_match_message(parsed)
                    return session
                session["selected_item"] = session["search_results"][0]
                step_name = "outfit"

            elif step_name == "outfit":
                session["outfit_suggestion"] = suggest_outfit(
                    session["selected_item"], session["wardrobe"]
                )
                step_name = "card"

            elif step_name == "card":
                card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
                session["fit_card"] = f"{card}\n{FROM_DATABASE_TAG}"
                step_name = "done"
    except ModelUnavailable as exc:
        session["error"] = f"The model couldn't be reached, so the run stopped early: {exc}"
    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
