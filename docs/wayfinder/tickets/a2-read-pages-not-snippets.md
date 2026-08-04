# Grounding reads search snippets, never the page

`wayfinder:task` · OPEN · blocked by: A1

## Question

`gather_grounding` builds the entire reference block out of search-result
DESCRIPTIONS:

```python
for h in hits[:3]:
    chunk = f"[{h['title']}] {h['extract']}"   # extract = the snippet
```

capped at `max_chars=900` across all three. `marginalia_search` and `ddg_search`
both return a `url` for every hit — and nothing ever opens it. Four advocates and
a judge argue from at most 900 characters of search-engine blurb.

This is almost certainly the largest single accuracy lever in the system. The
Mistral pricing probe is the clean example: a pricing PAGE exists, has a table on
it, and the panel instead read a valuation article's summary line because that is
what the snippet contained.

To decide:

- Fetch the top hit's body, or the top N? Each fetch is an HTTP round trip on a
  path that currently costs zero LLM calls and ~1s.
- How much of a fetched page enters the block, and chosen how? A pricing table is
  worth more than a page's first 900 chars, so naive truncation may lose exactly
  the fact that was wanted. Consider extracting the region around the query terms.
- `_get` and `_strip_tags` already exist in `orchestra_tools`. What is missing is
  size limiting, content-type checking, and a timeout budget that cannot stall a
  debate — the module's rule is that losing search must degrade the answer, never
  break it.
- Does the bigger block push the advocates' 120-word answers off? They already
  receive the block; more of it costs input tokens on five calls.

## Verified by

The eval score from A1 moving, plus the pricing probe specifically: does the
reference block come to contain actual per-token rates from a pricing page rather
than a sentence about a funding round.
