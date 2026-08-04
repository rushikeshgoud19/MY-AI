# Check the arithmetic the panel performs on grounded numbers

`wayfinder:grilling` · OPEN · graduated from fog by T3 · frontier

## Question

Sourcing a number and computing with it are different problems, and only the
first is now fixed. The pricing probe has produced three different wrong answers
across three runs:

| run | state | result |
|---|---|---|
| baseline | no grounding | invented prices, 25x arithmetic error, conclusion inverted |
| after T2 | grounded | real-ish prices, ~8x error, conclusion inverted again |
| after T3 | grounded, defects honoured | plausible prices, still ~2.8x off, conclusion now correct |

The last one is the clearest case: with its own stated rates (€0.24/€0.96 per
million for ministral-8b, €2.20/€8.80 for large), five 100k-token calls are
~€0.60 and one large call ~€1.10. It reported €1.68 and €3.08 — then
extrapolated faithfully from the wrong figures to "€14,000 saved over 10,000
questions". Confident, internally consistent, and wrong.

How should arithmetic be checked?

Prior art in this repo: `server/orchestra_tools.py` already ships an AST-walking
calculator (never `eval`, with int `bit_length()` guards) built for exactly this
class of problem. It is currently available for grounding but nothing forces a
numeric claim through it.

Options to weigh:
- Require advocates to SHOW the multiplication, then verify the shown arithmetic
  with the existing calculator and hand mismatches to the judge as a defect.
  Senku's brief already demands "show arithmetic rather than assert a
  precise-sounding number" — so the instruction exists and is not enforced.
- Have the judge recompute during review, as a scoring criterion.
- Accept it: forbid derived quantities entirely and let advocates state the
  inputs plus the direction of the comparison, never the product.

The third is the cheapest and may be the most honest — the *decision* Rushi needs
is "which is cheaper", and the exact euro figure is decoration that keeps being
wrong. Weigh that against the panel becoming vague.

Constraint: whatever is chosen must not fire on the settled path (2 calls) and
must not add a model call per advocate.
