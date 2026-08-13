# Stop synthesis re-asserting defects the judge already named

`wayfinder:grilling` · **CLOSED** · blocked by: T1 (closed)

## Question

T1 showed the judge scored the fabricated pricing down (3–5/10) and named
"unsourced pricing" as the defect — then the synthesis step produced a final
verdict containing those same invented figures, now with a date attached.

The detection layer works and the output layer ignores it. Where should the
correction be enforced?

## Resolution

Investigated first, as the ticket asked. **The defects were not in scope at
synthesis time at all** — the final call was:

```python
run(judge_model, _JUDGE_FINAL_SYS,
    f"QUESTION: {question}\n\nREVISED ANSWERS:\n{block(final_pool)}", ...)
```

Question plus answers, nothing else. The judge re-read the fabrication with no
memory of having caught it. Compounding it, `final_pool = {**answers, **revised}`
merges un-revised originals back in unmarked, so a 3/10 answer that never
improved arrived looking identical to a 9/10 revision.

So option three from this ticket was correct and the other two were unnecessary.
Implemented:

1. `scored_block()` replaces `block()` for the synthesis call only. Each answer
   now carries `YOUR SCORE n/10`, `not revised` where applicable, and
   `DEFECT YOU NAMED: …` above its text.
2. `_JUDGE_FINAL_SYS` gained three rules: never carry a claim you marked
   defective; never restate a figure you flagged as unsourced or outdated (drop
   it or say it could not be verified); weight low-scored and un-revised answers
   accordingly.

No code-side numeric stripping was added — the module's "CODE OWNS THE DECISION"
principle applies to *decisions*, and deleting numbers from prose is a text
surgery with no clean failure mode. The judge is being asked to honour findings
it already produced, which the 2026-08-02 benchmark showed it is good at.

**Verified** on the pricing probe. Scores sharpened to
`light:3, senku:9, ayanokoji:6, vanitas:4` with specific defects, and the verdict
no longer restates the flagged claims — it now sources its figures from the 9/10
grounded answer and reaches the OPPOSITE conclusion to the pre-fix run
(five ministral-8b calls cheaper than one mistral-large call, which is the
defensible direction).

## Residual — belongs to the new ticket, not here

The probe still fails. With the verdict's OWN quoted rates (€0.24/€0.96 for
ministral-8b, €2.20/€8.80 for large), five 100k-token calls come to ~€0.60 and one
large call to ~€1.10. The verdict states €1.68 and €3.08, then extrapolates
consistently from those wrong figures ("€1.40 × 10,000 questions = €14,000").

Three runs of this probe have now produced three different wrong numbers. The
sourcing is fixed; the multiplication is not. Graduated to
[Check the arithmetic the panel performs on grounded numbers](t6-check-arithmetic.md).
