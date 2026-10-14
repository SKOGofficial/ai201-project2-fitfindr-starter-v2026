#!/usr/bin/env python3
"""
Before/after check for the parse prompt.   ← UNIT 4, MILESTONE 5 (second improvement)

    python parse_check.py

The diagnosis: `agent._parse_query` read "medium" in "a medium wash denim vest"
as a size, so the size-M filter hid real listings (and for a Levi's query it
returned the wrong item with no error). The five scored criteria can't show
whether a fix for that works — they all passed before it — so this checks the
parse step directly, with the model really called (cache off, temperature 0).

Three groups of queries:
  TRAPS     "medium" (or similar) is part of the item's colour or wash, so
            size must come back null and the word must stay in the description.
            Two were seen while diagnosing (marked seen); the rest were written
            before the prompt was changed and not looked at.
  SIZES     a real size is asked for, so it must still come back as that size.
            This is the regression guard: a fix that makes the model stop
            returning sizes at all would pass the traps and break these.
  END TO END the Levi's query through the whole agent: the user asked for the
            Levi's 501 jeans (lst_001) and must get them.

Each parse is run 3 times; a case passes only if all 3 agree and are right.
"""

import contextlib
import io
import re
import sys

import config
config.CACHE_ENABLED = False

import agent

REPEATS = 3

# (query, seen while diagnosing?, words that must stay in the description)
TRAPS = [
    ("a medium wash denim vest, nothing over $30", True, ["medium", "wash"]),
    ("medium wash Levi's 501 jeans under $40", True, ["medium", "wash"]),
    ("medium wash denim shorts", False, ["medium", "wash"]),
    ("a medium brown leather belt under $20", False, ["medium", "brown"]),
    ("dark wash baggy jeans under $40", False, ["dark", "wash"]),
]

# (query, seen?, accepted sizes, case-insensitive)
SIZES = [
    ("a medium sized denim vest under $30", True, {"m"}),
    ("90s track jacket in size M", True, {"m"}),
    ("platform sneakers size 8", True, {"8", "us 8"}),
    ("crochet top in S/M under $25", False, {"s/m"}),
    ("vintage polo shirt in medium under $25", False, {"m"}),
    ("I'm a medium, looking for a flannel shirt", False, {"m"}),
    ("size medium henley long sleeve", False, {"m"}),
]


def parse_n(query):
    return [agent._parse_query(query) for _ in range(REPEATS)]


def main():
    print(f"Parse prompt check — model really called, {REPEATS} parses per query\n")
    trap_pass = size_pass = 0

    print("TRAPS: size must be null, and the colour/wash words must stay in the description")
    for query, seen, keep in TRAPS:
        parses = parse_n(query)
        sizes = [p["size"] for p in parses]
        ok = all(p["size"] is None and all(w in p["description"].lower() for w in keep) for p in parses)
        trap_pass += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {'(seen)  ' if seen else '(unseen)'} {query!r}")
        print(f"        sizes: {sizes}   description: {parses[0]['description']!r}")

    print("\nSIZES: a real size must still come back as that size")
    for query, seen, accepted in SIZES:
        parses = parse_n(query)
        sizes = [p["size"] for p in parses]
        ok = all((p["size"] or "").lower() in accepted for p in parses)
        size_pass += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {'(seen)  ' if seen else '(unseen)'} {query!r}")
        print(f"        sizes: {sizes}   (accepted: {sorted(accepted)})")

    print("\nEND TO END: the Levi's query through the whole agent")
    query = "medium wash Levi's 501 jeans under $40"
    with contextlib.redirect_stdout(io.StringIO()):
        session = agent.run_agent(query, {"items": []})
    top = (session["selected_item"] or {}).get("id")
    e2e = top == "lst_001"
    print(f"  {'PASS' if e2e else 'FAIL'}  {query!r}")
    print(f"        parsed: {session['parsed']}")
    print(f"        selected_item: {top} — {(session['selected_item'] or {}).get('title')}   (the user asked for lst_001)")

    print(f"\nTraps {trap_pass}/{len(TRAPS)} · Sizes {size_pass}/{len(SIZES)} · End to end {int(e2e)}/1")
    sys.exit(0 if (trap_pass == len(TRAPS) and size_pass == len(SIZES) and e2e) else 1)


if __name__ == "__main__":
    main()
