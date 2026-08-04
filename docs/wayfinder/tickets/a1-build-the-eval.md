# Build a scored accuracy eval

`wayfinder:task` · OPEN · **frontier — blocks A2, A3, A4, A5, A6, A7**

## Question

Every accuracy claim in the previous effort was made by reading a verdict and
forming an opinion. That was enough to find bugs and not enough to prove an
improvement, and twice a remembered number turned out to be stale. Before any
further change to grounding, there has to be a score.

Build an eval of questions whose answers are KNOWN and checkable, plus a runner
that scores a batch and reports a single number.

To decide while building it:

- **What is gradeable?** A price or a limit has a right answer that can be
  string- or range-matched. "Should I use SQLite or Postgres" does not. The eval
  should probably hold only questions with a checkable answer, and the advice-
  shaped ones stay in `probes.md` as a qualitative suite. Confirm that split
  rather than assuming it.
- **How is a verdict graded automatically?** Options: exact/range match on an
  extracted number; a required-substring list; a cheap model grading against a
  reference answer. The third is the usual choice and the least trustworthy —
  a grader that is itself a small model is the thing this whole map exists to
  distrust. Prefer deterministic where the answer is a number.
- **Does it grade the ANSWER or the PROCESS?** Both matter: a right answer reached
  from an inapplicable source is luck, and the previous effort showed the panel
  getting the direction right while every figure was wrong. Consider scoring
  grounded-ness and arithmetic separately from correctness, since those events are
  already emitted (`grounding`, `factcheck`).
- **How many questions, and where from?** Enough that one lucky run does not move
  the score. Some should be questions the panel currently gets WRONG, or the eval
  starts at 100% and can only go down.
- **Cost.** A full debate is ~11 calls. A 30-question eval is ~330 calls per run.
  Decide whether the eval runs the whole pipeline or only the parts under test.

## Done when

A command runs the eval and prints a score, the score is recorded here as the
baseline, and re-running it produces the same number on unchanged code.
