# Volatile facts take the ungrounded settled path

`wayfinder:task` · OPEN · graduated from A1 · **frontier**

## Question

Triage splits every question two ways. Everything the previous map built -
grounding, CALC arithmetic checks, citation checks, defects reaching synthesis,
the judge seeing its sources - lives on the CONTESTED side. The SETTLED side is:

    triage -> SETTLED -> one solo call -> return

No search, no checks, no judge review. Grounding is fetched AFTER the triage
block, so a settled question never reaches it.

That is correct for "Is 17 a prime number?" and wrong for anything whose answer
MOVES. Measured 2026-08-05:

    Q: What does Mistral charge per million tokens for ministral-8b right now?
    TRIAGE=SETTLED, no grounding event
    A: "Mistral charges $0.25 per million tokens for Mistral-8B as of the
        latest pricing information."

A bare invented figure, delivered with a confidence marker, on the path that skips
every safeguard. This is the failure the entire grounding map was built to remove.

## The distinction to draw

`_TRIAGE_SYS` currently means "does this have one right answer competent people do
not dispute". That is true of a current price - and the model still does not KNOW
it. Undisputed is not the same as knowable-from-memory.

- 17 is prime, a kibibyte is 1024 bytes, HTTPS is 443 -> stable, answer from
  memory, 2 calls, correct as-is.
- What X costs today, the current version of Y, this quarter's limit -> single
  right answer, but VOLATILE. Needs grounding even though it needs no debate.

## Options

- A third route: SETTLED-BUT-VOLATILE, which grounds and then answers with one
  call instead of convening four advocates. Cheapest correct fix if triage can
  make the call; it is one extra word in the classifier's vocabulary.
- Ground the settled path unconditionally. Simpler, and it spends an HTTP fetch on
  "is 17 prime" forever.
- Route volatile facts to the full debate. Correct but expensive - 11 calls to
  look up one number, which is the cost problem the previous map just fixed.
- Apply the deterministic checks to the solo answer too, independent of routing.
  Cheap, and catches the fabrication even if the routing decision stays wrong.

Recency words are a strong signal and cheap to detect in code: "right now",
"currently", "today", "latest", "as of". The one-directional override precedent
(_ADVISORY_RE promotes, never suppresses) fits here exactly.

## Verified by

The `price-honesty` case in the eval, currently the only failing case: it must
either attribute the figure or admit it cannot verify one.
