# FitFindr

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, every
> command, and what to do when something breaks.
>
> Once `python test.py` passes:
>
> ```bash
> python app.py listings --full -n 6      # read the data (Milestone 1)
> python app.py fields                    # what you can filter on
> python app.py ask 'vintage graphic tee under $30'
> ```
>
> All three tools are stubs, so that last command will do nothing useful yet.
> That's the starting position.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     HOW TO USE THIS FILE

     This is your submission. Fill each section in as you finish the milestone
     it belongs to — don't leave it all to the end.

     Unit 3 asks for the first five sections. Unit 4 adds the five below them.
     Leave the unit 4 sections alone until then; they're here so you know
     what's coming.

     Everything is pasted as TEXT. No screenshots, no images, no video links.
     A typed block of output gets full credit; a picture of the same output
     gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 3 — THE BUILD ═══════════════════════ -->

## What This Does

A user types a plain-language request for a secondhand clothing item, such as "vintage graphic tee under $30". FitFindr parses out the keywords, size and price ceiling, searches a 40-listing mock dataset (Depop, Poshmark, thredUp), and picks the best match. It then suggests one or two outfits that combine that item with pieces from the user's wardrobe (or general styling advice if the wardrobe is empty) and writes a short, postable fit card tagged `(from database)`. If nothing matches, it stops and says which description, size and price it tried and what to loosen.



---

## Tool Inventory

<!-- Four lines per tool. This is worth 2 points and it's the single most
     common place students lose them.

     "Returns a list" earns NOTHING. The description has to say what is IN
     the list.

     The empty case isn't optional either — it's the thing your loop branches
     on, and if you don't decide it here you'll discover it as a crash in
     Milestone 5. -->

### `search_listings`

- **What it does:** Finds secondhand listings matching a keyword description, optionally filtered by size and a price ceiling, best match first.
- **Inputs:** `description` (str), `size` (str or None), `max_price` (float or None, inclusive). Size matches on whole tokens, case-insensitive: the listing size is split on spaces, `/` and parentheses, and the requested size must equal one token (`M` matches `S/M` and `M`, not `XL` or `US 9`).
- **Returns:** A list of at most 10 listing dicts, each with `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand` (str or None), `platform`, sorted by keyword-overlap score, highest first.
- **When it has nothing:** Returns an empty list `[]` (never None, never an exception).

### `suggest_outfit`

- **What it does:** Asks the model for one or two outfits built around a thrifted item and the pieces the user already owns.
- **Inputs:** `new_item` (dict, a listing as above), `wardrobe` (dict with an `items` list of wardrobe items: `id`, `name`, `category`, `colors`, `style_tags`, `notes`).
- **Returns:** A non-empty string of outfit suggestions that name specific wardrobe pieces.
- **When it has nothing:** With an empty wardrobe (`items == []`) it returns general styling advice for the item instead of failing; it never returns `""`.

### `create_fit_card`

- **What it does:** Asks the model to write a short, shareable caption-style fit card for the outfit.
- **Inputs:** `outfit` (str, the output of `suggest_outfit`), `new_item` (dict, a listing).
- **Returns:** A non-empty string: the fit card text. It varies between runs (TEMPERATURE 0.9).
- **When it has nothing:** If `outfit` is empty/blank or `new_item` is empty, returns a short error string and makes no model call.

---

## Planning Loop

<!-- Your branch rule, stated as a rule — the condition AND both paths — plus
     the file and function that holds it.

     Like this:
       "If search_listings returns an empty list, put a message in the session
        and stop. Otherwise take the first result and go to suggest_outfit."
        — agent.py::run_agent

     The grader checks your code against what you claim here, so the file and
     function have to be real. -->

**Branch rule:** If `search_listings` returns an empty list, write a message into `session["error"]` that names the description, size and price tried and what to loosen, leave `session["fit_card"]` as `None`, and stop. Otherwise take the first result as `session["selected_item"]` and continue to `suggest_outfit`, then `create_fit_card`.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** Asking the model: it returns JSON with `description`, `size` and `max_price`, stored in `session["parsed"]`.

**What moves through the session:** `parsed` (description, size, max_price) is written first and read by the search; `search_results` is written, then `selected_item` is set to `search_results[0]` and read by `suggest_outfit`; `outfit_suggestion` is written and read by `create_fit_card` along with `selected_item`; `fit_card` is written last. `error` is set only when the run stops early.

---

## Sample Run

<!-- Two things go here.

     1. One FULL query and its output, pasted as text.
     2. Your three per-tool terminal tests — the command and what it printed. -->

**One full query**

```
$ python app.py ask 'vintage graphic tee under $30'
  Found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop

  Outfit:   **Outfit 1: Y2K Streetwear**
Pair the baby tee with your baggy straight-leg jeans. Layer the black cropped zip hoodie unzipped over top, and finish with chunky white sneakers and your black crossbody bag. 

**Outfit 2: Contrast Grunge**
Tuck the butterfly tee into your wide-leg khaki trousers, cinched with the brown leather belt. Throw on the vintage black denim jacket and ground the sweet pastel print with black combat boots.

  Fit card: Butterflies really are taking over my whole wardrobe lately 🦋 Found this unreal Y2K baby tee and honestly cannot wait to style it for that low-rise streetwear vibe or contrast grunge look. Snagged it on depop for just $18 and it's already my favorite piece of the week! ✨
(from database)

3 model calls this session, 615 prompt + 191 output tokens
```

**The no-match path**

```
$ python app.py ask 'designer ballgown size XXS under $5'
  (no match) Nothing matched 'designer ballgown', size XXS, under $5. Try different keywords, a different size or none, a higher budget.

1 model calls this session, 94 prompt + 31 output tokens
```

**The three tools, tested one at a time**

```
$ python -c "from tools import search_listings; print([(r['id'], r['title'], r['price']) for r in search_listings('graphic tee', max_price=30)][:3])"
[('lst_002', 'Y2K Baby Tee — Butterfly Print', 18.0), ('lst_006', 'Graphic Tee — 2003 Tour Bootleg Style', 24.0), ('lst_017', 'Mesh Long-Sleeve Top — Black', 15.0)]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[1], get_example_wardrobe()))"
**Outfit 1: Streetwear Contrast**
Pair the baby tee with your baggy straight-leg jeans to balance the fitted silhouette. Layer the vintage black denim jacket on top and finish with chunky white sneakers and the black crossbody bag.

**Outfit 2: Y2K Casual**
Tuck the baby tee into your wide-leg khaki trousers for an earth-toned contrast, and wear it with chunky white sneakers and the black crossbody bag for a casual daytime look.
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('baby tee, baggy jeans, white sneakers', load_listings()[1]))"
Living my best 2000s pop star fantasy in this butterfly baby tee. 🦋 Pair it with some baggy denim and fresh white kicks and you're good to go. Snagged this on depop for just $18 and I’m lowkey obsessed.
```

---

## How I Used AI

<!-- Two specific moments. What you asked, what came back, what you changed.

     "I used Claude to help me code" is not enough.

     "I gave Claude my search_listings spec. It returned None on no match
     instead of an empty list, so I changed it" is the level we want. -->

**Moment 1**

- *What I asked for:* Claude implemented `create_fit_card`, and I ran it three times on the same item to check the output varied.
- *What came back:* three word-for-word identical cards, which looked like a broken tool.
- *What I changed:* nothing in the code. Claude traced it to `CACHE_ENABLED` in `config.py`, and re-running with `AI201_CACHE=0` gave three different cards. I kept the cache on while building.

**Moment 2**

- *What I asked for:* Claude to paste the no-match run into the README Sample Run.
- *What came back:* a made-up output format that did not match what `python app.py ask` really prints.
- *What I changed:* I re-ran the command and replaced it with the real terminal text.

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════

     Don't fill these in during unit 3.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Run Log — Before

<!-- Five criteria, five tries each, in this exact format.

     Five, because your criteria are written out of five. Mark each try PASS
     or FAIL, count the passes, and read that count against your target — a
     row targeting 4 of 5 with three PASS cells is MISSED (3/5).

     `python run_eval.py --label before` runs everything and writes the table
     into results/. Paste it here and fill in the verdicts. -->

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. A matching query completes all three tools | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. An impossible query stops before the second tool | 5 of 5 | PASS | PASS | PASS | FAIL | PASS | MISSED (4/5) |
| 3. Item in session matches the item passed to suggest_outfit | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Fit card text contains the item's price | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. `(from database)` on matches, `(no match)` and no fit card on stops | 5 of 5 | PASS | PASS | PASS | FAIL | PASS | MISSED (4/5) |

How to read the table: a **try is one run of one query, and each criterion's five tries are five different queries** (queries and reasons are in `scenarios.py`; they were committed before this run). Criteria 1, 3, 4 and the matching half of 5 are scored from the same five matching runs; criterion 2 and the other half of 5 from five impossible-query runs; criterion 5's try *k* pairs matching run *k* with impossible run *k* and passes only if both pass. Caching was off, temperature 0.9. The PASS/FAIL rules are the functions in `score_run.py`, which applies each criterion as written in `criteria.md`; the verdicts above are arithmetic only (passes against the target) and are diagnosed below. Full outputs: `results/scored_2026-10-14_0033_before.md` and the raw log `results/run_2026-10-14_0033_before.md`.

The one FAIL in the table is a single event: in impossible-query try 4 (`graphic tee under $5`) the model service answered `503 UNAVAILABLE` on the very first call (parsing the query), so the search never ran. Criterion 5 failed on that same run, so criteria 2 and 5 share one cause.

**Real output from one try per criterion**, pasted as text.

Criterion 1, try 1 (`python score_run.py --label before`; fit card from `tools.py::create_fit_card`, tag appended in `agent.py::run_agent`):

```
query: vintage graphic tee under $30
parse: {'description': 'vintage graphic tee', 'size': None, 'max_price': 30.0}
Item: lst_002 — Y2K Baby Tee — Butterfly Print ($18.0, depop)
Butterfly print baby tee straight out of the 2000s and I am obsessed 🦋 So easy to dress up with baggy denim or wide-leg trousers. Grab this over on my depop for just $18 before I change my mind and keep it!
(from database)
```

Criterion 2, try 1 passed, try 4 failed (message from `agent.py::_no_match_message`, returned by the branch in `agent.py::run_agent`; the failing one came from `generate.py::generate` raising `ModelUnavailable`, caught in `run_agent`):

```
query: designer ballgown size XXS under $5
(no match) Nothing matched 'designer ballgown', size XXS, under $5. Try different keywords, a different size or none, a higher budget.

query: graphic tee under $5
The model couldn't be reached, so the run stopped early: Couldn't reach the model: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The service is currently unavailable.', 'status': 'UNAVAILABLE'}}
```

Criterion 3, try 1 (the `suggest_outfit` argument is recorded by a wrapper in `score_run.py`; the session fields are set in `agent.py::run_agent`):

```
selected_item id: lst_002
search_results[0] id: lst_002
id(s) suggest_outfit received: ['lst_002']
```

Criterion 4, try 1 (checked by `score_run.py::score_4`):

```
Item: lst_002 ($18.0)  ->  matched /\$18(\.00)?(?!\d)/
Fit card: "...Grab this over on my depop for just $18 before I change my mind and keep it!"
```

Criterion 5, try 1 (tags set in `agent.py::run_agent`):

```
matching run:   ...keep it!\n(from database)
impossible run: (no match) Nothing matched 'designer ballgown', size XXS, under $5. Try different keywords, a different size or none, a higher budget.   [fit_card is None]
```

---

## Verdicts and Diagnoses

<!-- MET or MISSED per criterion against LAST UNIT's target, plus a sentence on
     how you decided.

     Then, for every miss: which of the four places it happened — a tool, the
     loop's branch, the session, or the model's output — AND the mechanism.

     Not a diagnosis:  "The fit card was bad."
     A diagnosis:      "The fit card criterion missed on 2 of 5 items. Both had
                        an empty brand field. My prompt puts the brand in the
                        first sentence, so the card opened with a blank and read
                        like a fragment. The tool worked; the prompt assumed a
                        field that isn't always there."

     Look for a pattern. Three misses on the same tool is one problem, not
     three. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 | A matching query completes all three tools | 4 of 5 | **MET** | 5 of 5 tries passed against a target of 4. In every run `parse`, `search_listings`, `suggest_outfit` and `create_fit_card` ran and a real fit card came back; I checked the two model tools by recording their calls, not just by looking for a card. One try parsed its size wrongly and still passed (see Diagnoses). |
| 2 | An impossible query stops before the second tool | 5 of 5 | **MISSED** | 4 of 5 passed against a target of 5. Try 4 (`graphic tee under $5`) never reached the search: the model service returned 503 on the first call. The agent did not call `suggest_outfit`, but it also did not return a message naming what to change (it printed a raw error), so it fails the criterion as written. I kept it as a FAIL instead of re-running it: a user would have got that raw error, and a re-run until it passed would have hidden it. |
| 3 | Item in session matches the item passed to `suggest_outfit` | 5 of 5 | **MET** | In all five matching runs `selected_item["id"]`, `search_results[0]["id"]` and the id `suggest_outfit` actually received (recorded by wrapping it) were the same. |
| 4 | Fit card contains the item's price | 5 of 5 | **MET** | The regex matched all five cards, which were for five different items (lst_002, lst_004, lst_038, lst_019, lst_023). |
| 5 | `(from database)` on matches; `(no match)` and no fit card on stops | 5 of 5 | **MISSED** | 4 of 5 passed against a target of 5. All five matching runs carried the tag. The one failure is the same try-4 event as criterion 2: that run's error began "The model couldn't be reached", not `(no match)`. So criteria 2 and 5 are one failure counted twice. |

**Diagnoses**

*Miss: criteria 2 and 5 (one event — impossible try 4, `graphic tee under $5`).*
- **Where:** a model call, at the first step of the loop (`agent.py::_parse_query` → `generate.py::generate`). It was not the branch (never reached; re-run three times it took the branch correctly 3 of 3, `results/diagnostics_before.md` section A), not a tool, and not the session.
- **Mechanism:** the service answered `503 UNAVAILABLE`. `generate()` only retries when the error looks like a rate limit (429, "resource exhausted", "rate limit"); every other error becomes `ModelUnavailable` straight away, so a temporary outage ends the whole run. `generate.py::_explain` has no case for it and falls through to `Couldn't reach the model: {exc}`, which prints the raw error dict and does not tell the user to wait and try again. Two separate defects: no retry for temporary failures, and a message with no next step.

*Pattern.* Everything that failed, or nearly failed, is in step 1, before the branch: the 503 (a failed run) and the wrong parse below (a run that passed). In every run that got past the parse, the branch, the two later tools and the session did what the spec said.

*A pass that hides a bug (criterion 1, matching try 3).* `a medium wash denim vest, nothing over $30` was parsed with `size: 'M'`: the model read "medium" in "medium wash" as a size. It is repeatable (5 of 5 parses identical at temperature 0) and it comes from the model's output in the parse prompt (`agent.py::_parse_query`), not from the tool. The try passed only because the listing it wanted (lst_038) happens to be size M. When I asked for another "Medium Wash" item, Levi's 501 jeans (lst_001, size `W30 L30`), the size-M filter hid it and the agent returned a denim vest instead, with no error and a tagged fit card (`results/diagnostics_before.md` section C). I did not count this as a miss, because criterion 1 as written was met. It is the thing my five criteria cannot see: they check that a run completed and that its state was consistent, not that the item returned is the one the user asked for.

*Were my targets low?* Partly. Criterion 3 cannot fail by construction (`selected_item` is `search_results[0]` and is passed straight on), so it checks consistency, not correctness. Criterion 5's tags are added by code, so it can only fail when criterion 1 or 2 fails; it failed here only through criterion 2's event. Criterion 1 scored 5 of 5 against a target of 4, and its wrong parse did not change the outcome. The one I would tighten is criterion 1, to "the item selected is the one a correct parse would select", not just "a card came back". I did not revise any criterion: none was unmeasurable (criterion 5 needed a pairing rule to get five tries out of two halves, described under the run log), so `criteria.md` is unchanged.



---

## Loop Trace

<!-- One full run, printed step by step, with the MCP call visible in it.

     `python app.py ask '...' --trace` once you've added the trace.step()
     calls in Milestone 2.

     Worth pasting BOTH the happy path and the empty-search path. The empty
     one should be visibly shorter, because it stops. If your two traces are
     the same length, your branch isn't working — and this is the fastest way
     anyone will ever find that out. -->

**Happy path**

```
$ python app.py ask 'vintage graphic tee under $30' --trace
[1] parse query (model)
      in:  vintage graphic tee under $30
      out: description='vintage graphic tee', size=None, max_price=30.0
[2] search_listings (via MCP)
      in:  description='vintage graphic tee', size=None, max_price=30.0
      out: 10 items: Y2K Baby Tee — Butterfly Print, Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey … +7 more
      →    branch: results found -> selected_item = first result (id lst_002)
[3] suggest_outfit (model)
      in:  item id lst_002 (Y2K Baby Tee — Butterfly Print, $18); wardrobe: 10 items
      out: **Outfit 1: Streetwear Contrast** Pair the Y2K Baby Tee with your **Baggy straight-leg jeans, dark wash**. Add…
[4] create_fit_card (model)
      in:  item id lst_002 (Y2K Baby Tee — Butterfly Print, $18); outfit: 620 chars
      out: Found the ultimate 2000s butterfly tee on depop for just $18 and I am obsessed. It’s giving total sweet-meets-…
      →    done: fit card tagged and stored in session
```

**Empty search**

```
$ python app.py ask 'designer ballgown size XXS under $5' --trace
[1] parse query (model)
      in:  designer ballgown size XXS under $5
      out: description='designer ballgown', size='XXS', max_price=5.0
[2] search_listings (via MCP)
      in:  description='designer ballgown', size='XXS', max_price=5.0
      out: [] (empty)
      →    branch: empty -> set session['error'], stop before suggest_outfit
```

**On the MCP move:** `search_listings` is now registered in `mcp_server.py` (`@mcp.tool()`, with a description that gives types, units, the size-match rule and the empty case), and `agent.py::run_agent` calls it with `mcp_client.call_tool("search_listings", {...})` instead of importing it from `tools.py`. The other two tools are still direct calls. I compared the direct function and the MCP call on 7 queries (with and without size and price, plus two that match nothing): the returned lists were identical, same dicts in the same order, and the empty case still comes back as `[]`, so the branch in `run_agent` needed no change. What did change: each call starts and stops a fresh server process, so a search went from about 6 ms direct to about 700 ms via MCP (2.4 s on the first, cold call); and there is now a way to fail that didn't exist before (`mcp_client.MCPError` if the server won't start or rejects the call), which `run_agent` does not catch.

**Failure modes triggered on purpose** (real output; none of the three crashed, so no new handlers were needed)

```
$ python app.py ask 'designer ballgown size XXS under $5'          # 1. empty search
  (no match) Nothing matched 'designer ballgown', size XXS, under $5. Try different keywords, a different size or none, a higher budget.
```

```
$ python app.py ask 'denim jacket under $50' --empty-wardrobe      # 2. empty wardrobe
(running with an empty wardrobe)

  Found:    Denim Jacket — Light Wash, Cropped — $42.0 on poshmark

  Outfit:   **Verdict:** Skip it at $42. Light wash cropped denim is common at thrift stores for under $20. 

If you already own it, try these:

*   **Model-Off-Duty Streetwear:** Pair with baggy cargo trousers in olive green, a fitted ribbed white tank top, and chunky retro sneakers. 
*   **Balancing Proportions:** Layer it over a black slip dress that hits at the midi length. Add combat boots to ground the sweetness of the dress.

  Fit card: Spotted this cute cropped light wash denim jacket on Poshmark, but $42 is honestly way too steep for something you can easily find at a local thrift for half that. Cute model-off-duty potential if you already have it in your closet, though!
(from database)
```

```
$ python app.py ask 'corduroy trucker jacket size L under $60'     # 3. model unavailable
  (bad key supplied through the GEMINI_API_KEY environment variable for this one run; .env was not edited)
  The model couldn't be reached, so the run stopped early: The model rejected your API key. Check GEMINI_API_KEY in your .env file, or create a fresh key at aistudio.google.com.
```



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**Plan, written before either change was made.** The one required improvement is to make `generate.py` ride out temporary model-service failures (the 503 behind the criterion 2 and 5 misses) and report an outage with a message that says what to do. I am also doing one optional stretch feature, declared here before I start it: **a second improvement from my diagnosis, measured the same way** — rewrite the parse prompt in `agent.py::_PARSE_PROMPT` so item-name words such as "medium wash" are not read as a size. Each change gets its own before/after measurement, and the two are made and measured one after the other so their effects can be told apart.

**What I changed:**

**Which failure it was meant to fix:**

### Run Log — After

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it made things worse, say that. Honestly reported, that earns full
     credit and is more interesting than one that worked. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [ ] criteria.md has five numbered criteria, each with a target
       [ ] Each criterion has a reason underneath it
       [ ] All five unit 3 sections above have real content
       [ ] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [ ] Planning Loop names the branch rule and agent.py::run_agent
       [ ] Sample Run: one full query plus the three per-tool tests, as text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [ ] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
