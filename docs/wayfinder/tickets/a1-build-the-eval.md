# Build a scored accuracy eval

`wayfinder:task` · **CLOSED** · blocks A2, A3, A4, A5, A6, A7 (now unblocked)

## Question

Every accuracy claim in the previous effort was made by reading a verdict and
forming an opinion — enough to find bugs, never enough to prove an improvement.
Build an eval of questions with KNOWN answers and a runner that scores a batch.

## Resolution

`scripts/orchestra_eval.py`. 15 cases, two scores, deterministic grading.

**Grading is regex-only, deliberately.** The obvious design is a model grading the
answer against a reference. This map exists because small models assert things
confidently and wrongly, so grading with one puts the failure mode inside the
measuring instrument. Every case declares `all_of` / `none_of` patterns; the
grader is `re.search`. That restricts the eval to questions with a checkable
answer, which is the correct restriction — advice-shaped questions stay
qualitative in `probes.md`.

**Two scores, because they fail independently.** CORRECTNESS grades the verdict
text. PROCESS reads the emitted events — did grounding fire, did triage route
cheaply, did the fact-checkers trip. The previous effort produced a run that was
directionally right with every figure wrong; one score cannot express that.

`--only <id>` runs a subset, `--repeat N` measures variance.

## Baseline (2026-08-05)

| slice | correctness | process | cost |
|---|---|---|---|
| settled cases (11) | 11/11 | triage routed all correctly | 2.0 calls / ~450 tok each |
| contested cases (3) | 3/3 | grounded 3/3 | 11.0 calls / ~10k tok each |
| price-honesty | **0/1** | triage WRONG, ungrounded | 2 calls |

**15/16 correctness** (15 cases; the count was written as 16 in the first
version of this ticket and the commit that landed it - it is 15). The one failure is real and is the point of the exercise:
the eval must contain something the panel gets wrong or it starts at 100% and can
only fall.

## What building it found — the important part

The first version of this eval scored **12/12 with every single case on the SETTLED
path** and `grounded 0/0 attempted`. Checkable facts are, by definition, the ones
triage routes to the 2-call solo path — so an eval made of checkable facts never
touches the debate at all. That design flaw is what surfaced the finding:

> **The SETTLED path is completely ungrounded, and every fix from the previous map
> lives in the CONTESTED path only.** Asked "What does Mistral charge per million
> tokens for ministral-8b right now?", triage says SETTLED and the answer is
> `"Mistral charges $0.25 per million tokens for Mistral-8B as of the latest
> pricing information"` — a bare figure from model memory, no grounding event
> emitted, no CALC line, no citation check, no judge. The exact failure the whole
> grounding effort eliminated, alive and well on the other path.

Graduated to
[Volatile facts take the ungrounded settled path](a8-settled-path-ungrounded.md).

Three contested cases were then added — a checkable fact wrapped in a question that
genuinely depends on the asker's situation — so the eval exercises both paths.

## Note on the "done when" criterion

The ticket asked that re-running produce the same number on unchanged code. That is
not achievable: advocates run at temp 0.35–0.4 and the search backends change under
us. `--repeat` exists to measure the spread instead. Treat a one-case move as noise
and a three-case move as signal until the variance is actually characterised.
