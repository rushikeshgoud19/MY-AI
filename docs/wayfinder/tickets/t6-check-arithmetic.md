# Check the arithmetic the panel performs on grounded numbers

`wayfinder:grilling` · **CLOSED** · graduated from fog by T3

## Question

Sourcing a number and computing with it are different problems, and only the
first was fixed. The pricing probe produced three different wrong answers across
three runs — the last one plausible, correctly concluded, and still ~2.8x off,
then extrapolated faithfully to "€14,000 saved over 10,000 questions".

How should arithmetic be checked?

## Resolution

**Enforce it, do not ban it.** The third option — forbid derived quantities and
let advocates state only inputs and a direction — was tempting and rejected:
"A is cheaper than B" with no magnitude guts the COST FIRST stance, which exists
precisely to put a number on things. And after T3 there is now a channel that
carries a defect all the way into the final answer, so an enforced check has
somewhere to go.

Rejected equally: having the judge recompute. That adds an opinion where the
answer is decidable, and the module's own principle is CODE OWNS THE DECISION
wherever a thing is decidable.

Implemented:

1. `_ADVOCATE_SYS` requires a trailing `CALC: <expression> = <figure>` line for
   any figure the advocate worked out — digits and operators only, max two, not
   counted toward the 120-word budget, and **no line at all** when nothing was
   computed. The framing that matters: *a figure you cannot express as a CALC
   line is a figure you have not actually computed — say it is unknown.*
2. `_check_arithmetic()` evaluates each expression with `orchestra_tools.calc`
   (the AST walker that was already in the repo and that nothing was required to
   use) and compares against the stated figure with 5% tolerance — enough for
   honest rounding, nowhere near the 2.8x and 25x errors observed.
3. Failures are merged into `defects` and the score is **capped at 5.0**, below
   `ADOPT_MIN_SCORE`, so an answer whose own arithmetic contradicts itself can
   never short-circuit the debate as CASE 1 ADOPT. An `arithmetic` event is
   emitted so the console can show the check fired.

The expression is captured loosely (`.{1,200}?`) rather than with a tight numeric
character class. A tight class silently ignores a malformed CALC line — the case
most likely to be hiding a number nobody computed — and would have left calc's
rejection path dead code. Anything non-arithmetic is refused by the AST walk and
reported as "not evaluable".

## Verification

Unit-tested `_check_arithmetic` on 10 cases, including the exact historical
failures — `5*100000/1000000*0.24 = 1.68` (flagged, real value 0.12) and
`50000/1000000*0.24 = 0.30` (flagged, real value 0.012) — correct arithmetic,
honest rounding, comma thousands, `5/0`, `2**99999`, a bare name lookup, and
`__import__("os").system(...)`, which is reported as not evaluable rather than
executed.

Live run of the pricing probe: advocates now emit checkable CALC lines
(`(0.25 + 0.75) * 5 = 5`, `5 * (4 + 12) = 80`, `(3.00 / 0.25) = 12` — all
correct), two advocates **refused to invent** prices and said so outright, and the
verdict computed €5.00 vs €16.00 and named the token-parity assumption as a
caveat. First self-consistent arithmetic this probe has produced.

⚠️ **HONEST LIMIT**: the checker did not FIRE in that run, because the panel's
arithmetic was correct for once. So the function is proven by unit test and the
wiring by code reading — the flag-to-defect-to-verdict path has not yet been
observed end-to-end in a live debate. It fires the next time an advocate miscounts;
watch for the `arithmetic` event. Do not claim that path works until it has.
