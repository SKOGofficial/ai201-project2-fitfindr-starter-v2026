"""
The runs your test needs. ← UNIT 4, MILESTONE 3

Each of your five criteria needs something run against it. A criterion about
the empty-search branch needs an impossible query. One about the fit card needs
the same item run more than once. Working that out is Milestone 3's first step,
and this file is where you write it down.

`run_eval.py` runs everything here five times and writes the run log — five
because your criteria are written out of five.

Three scenarios are filled in to show the shape. Add or change whatever your
own criteria need — these are a starting point, not a fixed set.
"""

# How these scenarios map onto the five criteria (see criteria.md)
# ----------------------------------------------------------------
# One try = one run of one scenario. Each criterion's five tries are five
# DIFFERENT queries, one run each, because:
#   - criterion 1's target is 4 of 5 *because* harder phrasings are harder to
#     parse, so the five matching queries vary in how they are phrased;
#   - criterion 4 says "5 different items", so each matching query is chosen
#     to land on a different top listing.
#
# The five MATCHING scenarios (criterion 1) are also the runs that score
# criteria 3, 4 and the "matching" half of 5.  The five IMPOSSIBLE scenarios
# (criterion 2) also score the "impossible" half of 5.  `also_scores` lists
# the extra criteria a scenario is used for; score_run.py reads it.
#
# `expect` is what a perfect parse would produce, checked against
# data/listings.json before any run (every matching query returns its `top`
# listing, every impossible query returns []). It is diagnostic only — it is
# never what decides PASS or FAIL.
#
# These were written and committed before the first "before" run.

SCENARIOS = [
    # ── criterion 1 (+3, 4, 5): five different matching queries ──────────────
    {
        "name": "matching 1/5: simple tee, price only",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 1,
        "also_scores": [3, 4, 5],
        "expect": {"description": "vintage graphic tee", "size": None, "max_price": 30, "top": "lst_002"},
    },
    {
        "name": "matching 2/5: size M, no price",
        "query": "90s track jacket in size M",
        "wardrobe": "example",
        "criterion": 1,
        "also_scores": [3, 4, 5],
        "expect": {"description": "90s track jacket", "size": "M", "max_price": None, "top": "lst_004"},
    },
    {
        "name": "matching 3/5: 'medium' is part of the item name, not a size",
        "query": "a medium wash denim vest, nothing over $30",
        "wardrobe": "example",
        "criterion": 1,
        "also_scores": [3, 4, 5],
        "expect": {"description": "medium wash denim vest", "size": None, "max_price": 30, "top": "lst_038"},
    },
    {
        "name": "matching 4/5: shoe size given as a bare number",
        "query": "platform sneakers size 8",
        "wardrobe": "example",
        "criterion": 1,
        "also_scores": [3, 4, 5],
        "expect": {"description": "platform sneakers", "size": "8", "max_price": None, "top": "lst_019"},
    },
    {
        "name": "matching 5/5: chatty, slash size, price ceiling",
        "query": "hey, looking for a cottagecore crochet top in S/M, $25 or less please",
        "wardrobe": "example",
        "criterion": 1,
        "also_scores": [3, 4, 5],
        "expect": {"description": "cottagecore crochet top", "size": "S/M", "max_price": 25, "top": "lst_023"},
    },

    # ── criterion 2 (+5): five different impossible queries ──────────────────
    # Each returns [] under a correct parse. Three fail on keywords, two on a
    # filter (price floor of the data is $12; no listing is size XXS).
    {
        "name": "impossible 1/5: no such item, plus size and price",
        "query": "designer ballgown size XXS under $5",
        "wardrobe": "example",
        "criterion": 2,
        "also_scores": [5],
        "expect": {"description": "designer ballgown", "size": "XXS", "max_price": 5},
    },
    {
        "name": "impossible 2/5: no such item, no filters",
        "query": "a wetsuit for surfing",
        "wardrobe": "example",
        "criterion": 2,
        "also_scores": [5],
        "expect": {"description": "wetsuit surfing", "size": None, "max_price": None},
    },
    {
        "name": "impossible 3/5: no such item, short phrasing",
        "query": "looking for a kimono robe",
        "wardrobe": "example",
        "criterion": 2,
        "also_scores": [5],
        "expect": {"description": "kimono robe", "size": None, "max_price": None},
    },
    {
        "name": "impossible 4/5: item exists, price ceiling below everything",
        "query": "graphic tee under $5",
        "wardrobe": "example",
        "criterion": 2,
        "also_scores": [5],
        "expect": {"description": "graphic tee", "size": None, "max_price": 5},
    },
    {
        "name": "impossible 5/5: item exists, size nobody has",
        "query": "denim jacket in size XXS",
        "wardrobe": "example",
        "criterion": 2,
        "also_scores": [5],
        "expect": {"description": "denim jacket", "size": "XXS", "max_price": None},
    },

    # ── diagnostic: not one of the five criteria ─────────────────────────────
    {
        # A user with nothing saved. One of unit 4's three failure modes.
        "name": "empty wardrobe",
        "query": "denim jacket under $50",
        "wardrobe": "empty",
        "criterion": None,
    },
]

WARDROBES = ("example", "empty")


def validate() -> list[str]:
    """Complain about anything malformed, before a long run rather than during."""
    problems = []
    for i, scenario in enumerate(SCENARIOS, 1):
        if not scenario.get("query", "").strip():
            problems.append(f"scenario {i} has no query")
        if scenario.get("wardrobe") not in WARDROBES:
            problems.append(
                f"scenario {i} has wardrobe {scenario.get('wardrobe')!r} — "
                f"it should be one of {WARDROBES}"
            )
    return problems
