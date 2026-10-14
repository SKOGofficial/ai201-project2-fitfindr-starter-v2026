# Diagnostics — before the improvement (not part of the scored table)

Ad-hoc checks run after `scored_2026-10-14_0033_before.md`, to work out *why* the
misses and near-misses happened. They call `agent.run_agent` and
`agent._parse_query` directly with the cache turned off (`config.CACHE_ENABLED = False`),
so every model call is a real one. Nothing here changes a verdict or replaces a try
in the scored table.

## A. Re-run of the failed query (criterion 2, try 4), full agent, 3 times

The scored run failed on `graphic tee under $5` because the model service returned
503 on the parse call. Re-running the same query:

```
  run 1: parsed={'description': 'graphic tee', 'size': None, 'max_price': 5.0} search_results=0 fit_card=None
          error="(no match) Nothing matched 'graphic tee', under $5. Try different keywords, a higher budget."
  run 2: parsed={'description': 'graphic tee', 'size': None, 'max_price': 5.0} search_results=0 fit_card=None
          error="(no match) Nothing matched 'graphic tee', under $5. Try different keywords, a higher budget."
  run 3: parsed={'description': 'graphic tee', 'size': None, 'max_price': 5.0} search_results=0 fit_card=None
          error="(no match) Nothing matched 'graphic tee', under $5. Try different keywords, a higher budget."
```

3 of 3 take the branch correctly. The branch was never the problem; the 503 was a
transient outage that the agent has no way to ride out.

## B. The parse step on the "medium wash" query, 5 times (`agent._parse_query`, temperature 0.0)

Scored run, matching try 3, parsed `a medium wash denim vest, nothing over $30` as
size `M`. Repeating just the parse step:

```
  parse 1: {'description': 'medium wash denim vest', 'size': 'M', 'max_price': 30.0}
  parse 2: {'description': 'medium wash denim vest', 'size': 'M', 'max_price': 30.0}
  parse 3: {'description': 'medium wash denim vest', 'size': 'M', 'max_price': 30.0}
  parse 4: {'description': 'medium wash denim vest', 'size': 'M', 'max_price': 30.0}
  parse 5: {'description': 'medium wash denim vest', 'size': 'M', 'max_price': 30.0}
```

5 of 5 the same, so it is repeatable, not a fluke. Controls with the same prompt:

```
  'a denim vest, nothing over $30': {'description': 'denim vest', 'size': None, 'max_price': 30.0}
  'light wash denim jacket under $50': {'description': 'light wash denim jacket', 'size': None, 'max_price': 50.0}
  'a medium sized denim vest under $30': {'description': 'denim vest', 'size': 'M', 'max_price': 30.0}
```

The model reads the word "medium" as a size even when it is part of the item name
("medium wash"). That try still passed only because the listing it wanted
(lst_038, Denim Vest — Medium Wash) happens to be size M.

## C. Does that mis-parse return the wrong item? (full agent, once)

Another listing has "Medium Wash" in its title but is not size M: lst_001, Vintage
Levi's 501 Jeans, size `W30 L30`, $38.

```
query: medium wash Levi's 501 jeans under $40
perfect parse -> search_listings('Levi 501 jeans medium wash', None, 40): [('lst_001', "Vintage Levi's 501 Jeans — Mediu", 'W30 L30'), ('lst_016', 'High-Waisted Denim Shorts — Cuto', 'W27')]
agent parsed: {'description': "medium wash Levi's 501 jeans", 'size': 'M', 'max_price': 40.0}
search_results: 4 | fit_card: "Channeling serious 90s riot grrrl energy with this studded medium wash denim vest. It's giving total rockstar off-duty, and you can grab it on Depop for just $27. Perfect for layering over band tees or a black turtleneck!\n(from database)"
error: None
```

The user asked for Levi's 501 jeans and was handed a denim vest. The run completed
all three tools and returned a tagged fit card, so criteria 1, 3, 4 and the
matching half of 5 would all have scored it PASS.

## Scripts used

Run from the project root with the project's virtualenv. A: `agent.run_agent("graphic tee under $5", {"items": []})` three times.
B and the controls: `agent._parse_query(q)` for each `q` above. C: `agent.run_agent("medium wash Levi's 501 jeans under $40", {"items": []})` once, compared with `tools.search_listings("Levi 501 jeans medium wash", None, 40)`.
