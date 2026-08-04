# One search query per question, however many facts it needs

`wayfinder:grilling` · OPEN · blocked by: A1

## Question

`_QUERY_SYS` returns exactly one search phrase, and `gather_grounding` runs it
once. A question with two factual halves gets grounding for one of them at best.

The pricing probe asks two things — what ministral-8b costs AND what
mistral-large costs — and the single query "Mistral API pricing per million
tokens" has to serve both. The panel then supplied the missing half itself,
which is the exact behaviour this whole line of work is trying to stop.

To decide:
- Allow the query-writer to return up to N queries (2? 3?), merged into one block.
- Or derive follow-up queries from what the first search failed to answer, which
  is more precise and needs a second cheap call.
- Cost: each query is HTTP only, no LLM call, so N queries cost ~1s each and more
  input tokens on five calls. Cheap enough that the real limit is block size.
- Interaction with A2: if pages are fetched rather than snippets, one query may
  already answer both halves, and this ticket may shrink or vanish. Sequence
  after A2 and re-read before starting.
