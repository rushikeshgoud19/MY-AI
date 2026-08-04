# Triage reads a settled comparison as a design choice

`wayfinder:grilling` · OPEN · surfaced by the full probe re-run · frontier

## Question

"Is it faster to append 10,000 rows to SQLite inside one transaction or outside
one?" has one right answer that no competent person disputes. Triage classified it
CONTESTED and convened the full panel: 11 calls, ~6k tokens, to reach the answer a
single call would have produced.

`_ADVISORY_RE` is not responsible — it contains no "faster", and its override is
one-directional anyway. The triage model itself made the call, which is consistent
with its prompt: the question has an "X or Y" comparative shape that resembles a
design choice, and `_TRIAGE_SYS` ends with "WHEN IN DOUBT REPLY CONTESTED".

That instruction is correct and should stay — a wasted debate costs tokens, a
settled-path answer to a question deserving debate costs correctness. The question
is whether a *measurable* comparison can be separated from a *preference*
comparison without weakening that default.

Distinction to test:
- "Is X faster/smaller/cheaper than Y" — has a measurable answer → SETTLED.
- "Should I use X or Y" / "is X good enough" — depends on the situation → CONTESTED.

Existing prior art: `_TRIAGE_SYS` only became stable when it gained few-shot
examples, and the one stubborn miss was handled in code by `_ADVISORY_RE` rather
than by more prompting. Both levers are available; prefer the deterministic one
where the distinction is decidable.

Careful: "Is SQLite good enough for my app?" must stay CONTESTED (it is an
explicit example in the prompt and was the original stubborn case), and the fix
must not make the settled path greedy. Re-test the triage set that was measured
8/9 correct and stable, not just this one probe.

Cost of leaving it: every settled comparison costs ~6k tokens instead of ~150.
