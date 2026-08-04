# Volatile facts take the ungrounded settled path

`wayfinder:task` · **CLOSED** · graduated from A1

## Question

Everything the grounding map built lives on the CONTESTED side. The SETTLED side is
`triage -> one solo call -> return`, with grounding fetched *after* the triage
block, so a settled question never reaches it. Correct for "Is 17 a prime number?",
wrong for anything whose answer MOVES:

```
Q: What does Mistral charge per million tokens for ministral-8b right now?
TRIAGE=SETTLED, no grounding event
A: "Mistral charges $0.25 per million tokens for Mistral-8B as of the
    latest pricing information."
```

## Resolution

**Undisputed is not the same as knowable from memory.** A current price has exactly
one right answer that competent people do not dispute — and the model does not have
it. So the split is no longer settled-vs-contested but three ways:

| route | when | cost |
|---|---|---|
| SETTLED | stable fact | 2 calls |
| SETTLED + volatile | one right answer, but it moves | **3 calls** |
| CONTESTED | genuine judgement | ~11 calls |

Implemented:

1. `_VOLATILE_RE` — recency and moving-quantity markers ("right now", "currently",
   "latest", "as of", "price", "free tier", "rate limit", "current version").
   Deliberately generous: a false positive costs one HTTP fetch on a path that
   still makes two model calls, a miss costs an invented figure with nothing behind
   it. Follows the `_ADVISORY_RE` precedent — it changes the route, never suppresses
   a debate.
2. The grounding block was hoisted out of the debate path into `fetch_grounding()`
   so both routes use one implementation. A volatile settled question grounds, then
   answers with ONE call instead of convening four advocates.
3. `_SOLO_GROUNDED_SYS` — answer from the reference material, name the source in
   brackets, and if it is not there say you could not verify a current figure and
   where to check. Never supply one from memory.
4. **The solo answer now gets the same deterministic checks as an advocate's.**
   There is no judge on this path to hand a defect to, so a failed arithmetic or
   citation check is treated exactly like a failed call: fall through and convene
   the panel, which does have somewhere to put it.

## Verification

`_VOLATILE_RE` unit-tested 10/10 — the pricing, "latest version" and "current free
tier" questions detected; prime, kibibyte, ports, git SHA and the SQLite
transaction question correctly left alone.

Live, the same question that produced the fabrication:

```
GROUNDING ok=true backend=marginalia+ddg
TRIAGE=SETTLED volatile=true (volatile fact; grounded single answer)
A: "Could not verify a current figure. Check the [Pricing] section for the
    latest rates."
calls=3 tokens=969
```

It declined rather than reading a price off the valuation article that grounding
returned — the source-fit behaviour from the previous map carrying through to a
path that had none of it an hour ago.

**Eval: 15/15, up from 15/16.** `price-honesty` now passes, grounded, on 3 calls.

## Three corrections to my own records

- The eval has **15 cases, not 16** — that number was wrong in the A1 ticket and in
  its commit message. Corrected in both.
- `price-honesty` was marked `settled: False`, so the run reported "triage routed
  6/7". That expectation predated this route: SETTLED-and-grounded IS the correct
  and cheapest outcome. Corrected to `settled: True`, giving 7/7.
- The eval counted grounding by inferring from the triage verdict
  (`if triage != "SETTLED"`), which excluded the volatile path from its own
  denominator. It now counts from the emitted event.
