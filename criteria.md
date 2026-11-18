# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:** This target depends on the model's pure ability to parse the relevant information out of the query, and it may not be strong enough for complicated requests, so 5 of 5 would be unfair to it.
<!-- Why 4 of 5 and not 5 of 5? Something about your search, probably —
     "my search is a plain keyword match and some phrasings will miss" is a
     real answer. -->

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:** This case seems to be working well. The model can probably tell clearly when a query is completely out of scope; it seems improbable that it would miss, since it may be trained to recognise real possibilities over tokens that typically won't be associated with each other in a normal sentence.
<!-- Why is 5 of 5 reasonable here when criterion 1 isn't? What's different
     about this path? -->

---

## 3. Something about state

<!-- YOU WRITE THIS ONE.

     How would you know that the item your search found is the same item the
     next tool received? Name something countable or observable.

     This is the criterion people find hardest, because state failure doesn't
     look like state failure — it looks like a tool problem. Something that
     compares session["selected_item"] against what actually reached
     suggest_outfit is the shape you're after. -->

In at least 5 of 5 matching runs, `session["selected_item"]["id"]` equals
`session["search_results"][0]["id"]` and equals the `id` of the item dict that
`suggest_outfit` actually received (checked by wrapping `suggest_outfit` and
recording its argument).



**Why this target:** This is a sanity check, really.



---

## 4. Something about the fit card

<!-- YOU WRITE THIS ONE.

     The fit card calls a model, so the same input can produce different words
     each time. That's not a bug — it's the nature of the tool. So what would
     make it acceptable?

     Think about what you'd actually be unhappy to see. A caption that never
     mentions the price? Two different items producing the same opening
     sentence? A card longer than a caption anyone would post? Any of those can
     be turned into a number. -->

In 5 of 5 fit cards, for 5 different items, the card text matches the regex
`\$<price>(\.00)?(?!\d)`, where `<price>` is that listing's price with a trailing
`.0` dropped (for example `$18` or `$18.00`).



**Why this target:** I want this checked with a regex, not by eye.



---

## 5. Your choice

<!-- YOU WRITE THIS ONE TOO.

     Pick something you actually care about getting right. Speed, the empty
     wardrobe path, what happens when the model can't be reached, whether the
     search respects a price ceiling — anything, as long as it names a number
     or an observable outcome. -->

In 5 of 5 matching runs the fit card contains the literal tag `(from database)`,
and in 5 of 5 impossible-query runs `session["error"]` starts with `(no match)`
and `session["fit_card"]` is `None`. Both are checked with a regex.



**Why this target:** This is a test at the end of the pipeline. If every earlier criterion passed within its threshold, there is some leeway for design failure while still solving the meat of the problem.



---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Unit 9 — deployed, instrumented service

These three are new, written against `serve.py` running as a real deployment
on Render rather than against the CLI. No template this time — chosen,
worded and targeted from scratch, against the service as actually deployed.

## 6. Cold start

After the free-tier dyno has been idle 20+ minutes (Render spins it down),
the first `GET /health` afterward returns `{"status": "ok"}` within 60
seconds — in 5 of 5 tries.

**Why this target:** Render's own docs describe free-tier cold start as "a
few seconds to about a minute." 60s gives real headroom above that without
being a target I can't miss — a dyno that takes 90s to wake up is a problem
worth knowing about, not noise to average away.

## 7. Concurrency is really serialized

Firing two `/ask` requests at the same moment, each with a different query:
in 5 of 5 trials, both responses come back correct and not swapped (each
response's fit card is for its own query's item, not the other request's),
and exactly one of the two logged lines for that pair has
`waited_for_lock: true`.

**Why this target:** `serve.py` claims one-at-a-time processing via a single
lock. Checking only "neither request crashed" could pass even if the lock
did nothing and the two requests happened not to collide. Requiring exactly
one `waited_for_lock: true` per pair is the one thing that's false if the
lock isn't doing real work.

## 8. Every request logs itself honestly

Across 20 requests — 5 matching queries, 5 impossible queries, 5 with a
missing `query` field, and 5 with a malformed `wardrobe` that is missing
required item fields (`tools.py::suggest_outfit` indexes `w['name']`,
`w['category']`, `w['colors']`, `w['style_tags']` directly, so a client
wardrobe missing any of those raises an uncaught exception, caught by
`serve.py`'s `except Exception` as a 500) — exactly 20 JSON log lines
appear, each parses as valid JSON, and each one's `status` field matches
what actually happened (`ok` / `no_match` / `bad_request` / `error`) — 20
of 20.

**Why this target:** completeness (no request goes unlogged, none logs
twice) and correctness (the label is true, not just present) are both
things I'd want to know are broken, and neither implies the other — a
server that logs every request with the wrong status would still pass a
completeness-only check.
