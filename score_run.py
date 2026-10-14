#!/usr/bin/env python3
"""
Score a test run against criteria.md.   ← UNIT 4, MILESTONE 3

    python score_run.py --label before
    python score_run.py --label after

This wraps run_eval.py; it does not replace it. It runs every scenario in
scenarios.py once (run_eval.py's own raw log is still written to results/), and
on top of that fills in the PASS / FAIL cells by applying each criterion
exactly as it is written in criteria.md. The five criteria are scored from
five DIFFERENT queries each, one run per try — see the note at the top of
scenarios.py for why.

What it adds that run_eval.py can't do alone:
  - criterion 3 needs "the id of the item suggest_outfit actually received",
    so suggest_outfit and create_fit_card are wrapped here to record their
    arguments. The agent's own code is not touched.
  - criteria 1-5 are applied mechanically, with the reason for every FAIL.

The scoring rules are the functions below. They are deliberately literal.
Read them before you trust a verdict — they are the judgment, in code.
"""

import datetime as dt
import re
import sys

import config
import agent
import run_eval
import scenarios as scenario_module

# Targets, copied from criteria.md (the "at least 4 of 5" / "5 of 5" lines).
TARGETS = {1: 4, 2: 5, 3: 5, 4: 5, 5: 5}
NAMES = {
    1: "A matching query completes all three tools",
    2: "An impossible query stops before the second tool",
    3: "Item in session matches the item passed to suggest_outfit",
    4: "Fit card text contains the item's price",
    5: "Tags: (from database) on matches, (no match) + no fit card on stops",
}

# ── record what the tools actually received ──────────────────────────────────
_calls = {"suggest_outfit": [], "create_fit_card": []}
_real_suggest = agent.suggest_outfit
_real_card = agent.create_fit_card


def _spy_suggest(item, wardrobe):
    _calls["suggest_outfit"].append(item)
    return _real_suggest(item, wardrobe)


def _spy_card(outfit, item):
    _calls["create_fit_card"].append(item)
    return _real_card(outfit, item)


agent.suggest_outfit = _spy_suggest
agent.create_fit_card = _spy_card

_real_run_once = run_eval.run_once


def _run_once_with_spies(scenario, use_trace=True):
    for calls in _calls.values():
        calls.clear()
    record = _real_run_once(scenario, use_trace)
    record["calls"] = {name: list(items) for name, items in _calls.items()}
    return record


run_eval.run_once = _run_once_with_spies


# ── the five criteria, applied literally ─────────────────────────────────────
# Each returns (passed: bool, reason: str).

def _s(record):
    return record.get("session") or {}


def _card_body(session):
    return (session.get("fit_card") or "").replace(agent.FROM_DATABASE_TAG, "").strip()


def score_1(record):
    """Matching query: all three tools ran and a real fit card came back."""
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    s = _s(record)
    if s.get("error"):
        return False, f"run stopped early: {str(s['error'])[:100]}"
    n_outfit = len(record["calls"]["suggest_outfit"])
    n_card = len(record["calls"]["create_fit_card"])
    if not n_outfit or not n_card:
        return False, f"a tool was not called (suggest_outfit x{n_outfit}, create_fit_card x{n_card})"
    body = _card_body(s)
    if not body or body.startswith("Can't write a fit card"):
        return False, f"fit card is empty or a fallback string: {body[:80]!r}"
    return True, "parse, search, suggest_outfit and create_fit_card all ran; fit card returned"


def score_2(record):
    """Impossible query: stopped before suggest_outfit, with a message naming what to change."""
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    s = _s(record)
    if not s.get("parsed"):
        return False, f"search was never reached (error: {str(s.get('error'))[:100]})"
    if s.get("search_results"):
        return False, (f"query was NOT impossible for the agent: search returned "
                       f"{len(s['search_results'])} result(s) for parsed={s['parsed']}")
    if record["calls"]["suggest_outfit"]:
        return False, "suggest_outfit was called"
    if record["calls"]["create_fit_card"]:
        return False, "create_fit_card was called"
    if s.get("fit_card") is not None:
        return False, "fit_card is not None"
    msg = s.get("error") or ""
    if not re.search(r"\bTry\b", msg):
        return False, f"error message doesn't say what to change: {msg[:100]!r}"
    return True, "stopped after search, neither model tool called, message says what to change"


def score_3(record):
    """State: selected_item id == search_results[0] id == id suggest_outfit received."""
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    s = _s(record)
    received = record["calls"]["suggest_outfit"]
    if not received:
        return False, "suggest_outfit was never called, so nothing to compare"
    selected = (s.get("selected_item") or {}).get("id")
    first = (s["search_results"][0].get("id") if s.get("search_results") else None)
    got = received[0].get("id")
    if selected is not None and selected == first == got:
        return True, f"all three ids are {got}"
    return False, f"selected_item={selected}, search_results[0]={first}, suggest_outfit received={got}"


def score_4(record):
    """Fit card text matches \\$<price>(\\.00)?(?!\\d), price with a trailing .0 dropped."""
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    s = _s(record)
    item = s.get("selected_item")
    card = s.get("fit_card")
    if not item or not card:
        return False, "no item or no fit card to check"
    price = repr(item["price"])
    if price.endswith(".0"):
        price = price[:-2]
    pattern = r"\$" + re.escape(price) + r"(\.00)?(?!\d)"
    if re.search(pattern, card):
        return True, f"matched /{pattern}/"
    return False, f"no match for /{pattern}/ in the fit card"


def score_5_match(record):
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    card = _s(record).get("fit_card") or ""
    if re.search(re.escape(agent.FROM_DATABASE_TAG), card):
        return True, "fit card contains (from database)"
    return False, "fit card is missing the (from database) tag"


def score_5_stop(record):
    if record["crashed"]:
        return False, f"crashed: {record['crashed']}"
    s = _s(record)
    if not re.match(re.escape(agent.NO_MATCH_TAG), s.get("error") or ""):
        return False, f"error doesn't start with (no match): {str(s.get('error'))[:80]!r}"
    if s.get("fit_card") is not None:
        return False, "fit_card is not None"
    return True, "error starts with (no match) and fit_card is None"


# ── assemble the report ──────────────────────────────────────────────────────

def _score_everything(rows):
    """Return per-criterion lists of (record, scenario, passed, reason), five long."""
    matching = [(r["scenario"], r["tries"][0]) for r in rows if r["scenario"].get("criterion") == 1]
    impossible = [(r["scenario"], r["tries"][0]) for r in rows if r["scenario"].get("criterion") == 2]
    diagnostic = [(r["scenario"], r["tries"][0]) for r in rows if r["scenario"].get("criterion") is None]

    scored = {1: [], 2: [], 3: [], 4: [], 5: []}
    for scenario, record in matching:
        for number, fn in ((1, score_1), (3, score_3), (4, score_4)):
            ok, why = fn(record)
            scored[number].append((scenario, record, ok, why))
    for scenario, record in impossible:
        ok, why = score_2(record)
        scored[2].append((scenario, record, ok, why))
    # Criterion 5, try k = the k-th matching run paired with the k-th impossible run.
    for (m_scn, m_rec), (i_scn, i_rec) in zip(matching, impossible):
        ok_m, why_m = score_5_match(m_rec)
        ok_i, why_i = score_5_stop(i_rec)
        scored[5].append(((m_scn, i_scn), (m_rec, i_rec), ok_m and ok_i,
                          f"matching run: {why_m}; impossible run: {why_i}"))
    return scored, diagnostic


def _verdict(number, passes):
    return f"{'MET' if passes >= TARGETS[number] else 'MISSED'} ({passes}/5)"


def _parse_note(scenario, record):
    exp = scenario.get("expect")
    got = _s(record).get("parsed")
    if not exp or not got:
        return ""
    ok = (str(got.get("size") or "").lower() == str(exp["size"] or "").lower()
          and (got.get("max_price") == (float(exp["max_price"]) if exp["max_price"] is not None else None)))
    top = (_s(record).get("selected_item") or {}).get("id")
    top_note = ""
    if "top" in exp:
        top_note = f"; selected {top} (a perfect parse selects {exp['top']})"
    return (f"parse: {got}  [size/price {'as expected' if ok else 'DIFFERENT from expected '}"
            f"{'' if ok else str({k: exp[k] for k in ('size', 'max_price')})}]{top_note}")


def write_scored_report(rows, args):
    scored, diagnostic = _score_everything(rows)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    label = f"_{args.label}" if args.label else ""
    path = config.RESULTS_DIR / f"scored_{stamp}{label}.md"

    lines = [
        f"# Scored run{f' — {args.label}' if args.label else ''}",
        "",
        "- Produced by: `score_run.py` (wraps `run_eval.py`; the raw log for the same run is the matching `run_*` file)",
        "- Loop: `agent.py::run_agent` · `search_listings` via MCP (`mcp_server.py`) · other two tools direct",
        "- Caching off, temperature " + str(config.TEMPERATURE),
        f"- When: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- A try = one run of one query. Each criterion's five tries are five different queries (see `scenarios.py`).",
        "  Criterion 5's try k pairs matching run k with impossible run k and passes only if both halves pass.",
        "",
        "| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    table = {}
    for number in (1, 2, 3, 4, 5):
        cells = ["PASS" if ok else "FAIL" for _, _, ok, _ in scored[number]]
        passes = cells.count("PASS")
        target = f"{TARGETS[number]} of 5"
        table[number] = (passes, cells)
        lines.append(f"| {number}. {NAMES[number]} | {target} | {' | '.join(cells)} | {_verdict(number, passes)} |")
    lines += ["", "Verdicts are arithmetic only (passes vs. the target in criteria.md). Diagnosis is separate.", "",
              "---", "", "## What each try produced", ""]

    for number in (1, 2, 3, 4, 5):
        lines += [f"### Criterion {number} — {NAMES[number]}", ""]
        for k, (scn, rec, ok, why) in enumerate(scored[number], 1):
            if number == 5:
                m_scn, i_scn = scn
                m_rec, i_rec = rec
                lines += [f"**Try {k}: {'PASS' if ok else 'FAIL'}** — {why}", "",
                          f"- matching query: `{m_scn['query']}`",
                          f"- impossible query: `{i_scn['query']}`", ""]
                lines += ["Fit card (matching run):", "", "```", str(_s(m_rec).get("fit_card")), "```", "",
                          "Error (impossible run):", "", "```", str(_s(i_rec).get("error")), "```", ""]
                continue
            lines += [f"**Try {k}: {'PASS' if ok else 'FAIL'}** — {why}", "",
                      f"- query: `{scn['query']}`"]
            note = _parse_note(scn, rec)
            if note:
                lines.append(f"- {note}")
            lines.append("")
            s = _s(rec)
            if number in (1, 4) and s.get("fit_card"):
                item = s.get("selected_item") or {}
                lines += [f"Item: {item.get('id')} — {item.get('title')} (${item.get('price')}, {item.get('platform')})", "",
                          "Fit card:", "", "```", str(s["fit_card"]), "```", ""]
            elif number == 2:
                lines += ["Error message:", "", "```", str(s.get("error")), "```", ""]
            elif number == 3:
                got = [i.get("id") for i in rec["calls"]["suggest_outfit"]]
                lines += [f"- selected_item id: {(s.get('selected_item') or {}).get('id')}",
                          f"- search_results[0] id: {(s['search_results'][0].get('id') if s.get('search_results') else None)}",
                          f"- id(s) suggest_outfit received: {got}", ""]

    for scn, rec in diagnostic:
        s = _s(rec)
        lines += [f"### Diagnostic (not one of the five): {scn['name']}", "",
                  f"- query: `{scn['query']}`  (empty wardrobe)",
                  f"- crashed: {rec['crashed']}",
                  f"- error: {s.get('error')}",
                  f"- outfit_suggestion non-empty: {bool((s.get('outfit_suggestion') or '').strip())}", ""]
        if s.get("outfit_suggestion"):
            lines += ["Outfit:", "", "```", str(s["outfit_suggestion"]), "```", ""]
        if s.get("fit_card"):
            lines += ["Fit card:", "", "```", str(s["fit_card"]), "```", ""]

    path.write_text("\n".join(lines), encoding="utf-8")

    print("\n" + "=" * 78)
    for number in (1, 2, 3, 4, 5):
        passes, cells = table[number]
        print(f"  {number}. target {TARGETS[number]} of 5   {' '.join(cells)}   {_verdict(number, passes)}")
    print("=" * 78)
    print(f"Wrote {path.relative_to(config.ROOT)}")


_real_write_report = run_eval.write_report


def _write_both(rows, args):
    _real_write_report(rows, args)      # run_eval's own raw log, unchanged
    write_scored_report(rows, args)


run_eval.write_report = _write_both


if __name__ == "__main__":
    label = ""
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    # One run per scenario: the five tries of a criterion are five different queries.
    sys.argv = ["run_eval.py", "--tries", "1", "--label", label]
    print("score_run.py: one run per scenario; each criterion's five tries are five different queries.\n"
          "(The '1 tries' warning below is expected.)\n")
    run_eval.main()
