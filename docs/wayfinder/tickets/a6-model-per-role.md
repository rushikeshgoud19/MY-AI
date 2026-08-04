# Does the model per role change accuracy?

`wayfinder:task` · OPEN · blocked by: A1

## Question

The panel is four small Mistral models with a mistral-medium judge, chosen on
2026-08-02 for JUDGING skill (winner-picking and defect-naming) — not for factual
accuracy, which was never benchmarked. mistral-large was rejected as judge for
being 429-fragile, which is an availability argument, not a correctness one.

With an eval in place this becomes measurable rather than arguable:

- Does a larger model on SYNTHESIS only (one call per debate) move the score?
- Do the advocate models matter for factual questions, or is grounding quality
  doing all the work? If the second, model choice is settled and this closes.
- Does the 429 fragility that ruled large out as judge also rule it out for a
  single synthesis call, where one retry is affordable?

Do not start before A1. This is exactly the ticket that produces a confident wrong
conclusion when graded by impression.
