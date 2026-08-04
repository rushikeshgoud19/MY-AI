# Stop synthesis re-asserting defects the judge already named

`wayfinder:grilling` · OPEN · blocked by: T1 (closed) · frontier

## Question

T1 showed the judge scored the fabricated pricing down (3–5/10) and named
"unsourced pricing" as the defect — then the synthesis step produced a final
verdict containing those same invented figures, now with a date attached.

The detection layer works and the output layer ignores it. Where should the
correction be enforced?

Options to weigh:
- `_JUDGE_FINAL_SYS` gains an explicit rule: never assert a quantity that appears
  only in a low-scored answer.
- Code-side: strip or flag numeric claims that no grounded source supports —
  consistent with the module's existing "CODE OWNS THE DECISION" principle.
- Feed the defect list into the synthesis prompt so the judge sees its own
  findings when writing the answer (it currently may not).

The third is cheapest and most in the spirit of the existing design; confirm
whether the defects are actually in scope at synthesis time before choosing.
