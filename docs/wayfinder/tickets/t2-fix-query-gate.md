# Stop the query-writer refusing to search factual questions

`wayfinder:task` · **CLOSED** · blocked by: T1 (closed)

## Question

`_QUERY_SYS` may answer `NONE` when it judges a question "purely normative,
ethical, or a matter of opinion". T1 proved it applies that escape to questions
that are substantially factual lookups, silently disabling grounding for exactly
the class of question that needs it most.

What is the narrowest prompt change that makes mixed factual/normative questions
search, without making every ethics question burn a search call?

## Resolution

Rewrote `_QUERY_SYS` with two changes:

1. It now asks for a **web search query**, not a "Wikipedia search phrase". The
   backend chain tries marginalia and duckduckgo long before wikipedia, so the
   old phrasing was optimising for the last-resort backend.
2. `NONE` is narrowed: any question with a checkable part must be searched for
   THAT part, ignoring the opinion part. `NONE` survives only for questions where
   nothing at all could be checked against a source. Three worked examples
   included, since ministral-8b at temp 0 follows examples better than rules.

Also fixed the `REFERENCE MATERIAL` header, which hardcoded "fetched from
Wikipedia" regardless of which backend answered — it now names the real backend,
because claiming encyclopedia authority for a blog result changes how the
advocates weigh it.

**Verified both directions** by re-running the real pipeline:

- Pricing probe → `ok=true backend=marginalia+ddg chars=682`,
  query `"Mistral API pricing per million tokens"`, 3 sources. Was
  `ok=false backend=none` before.
- Pure-ethics probe ("is it ever right to lie to someone you love") →
  `ok=false reason="no factual grounding applicable"`. The escape hatch survives.

## Residual — does NOT belong to this ticket

The pricing verdict is still wrong, in a new way. Grounding returned weak sources
(a Mistral *valuation* article, a generic "AI Service Providers" page), and the
panel asserted €0.25/€0.75 anyway, then computed one mistral-large call as
~8x cheaper per token than ministral-8b — implausible on its face, and it inverted
the conclusion a second time.

So repairing the search was necessary and not sufficient. Two consequences,
carried to the map:

- T4 must gate on source QUALITY, not just source presence. "A number appeared in
  the reference block" is too weak a test when the block is a valuation blog.
- Arithmetic performed ON grounded numbers is itself ungrounded, and nothing
  currently checks it. New fog.
