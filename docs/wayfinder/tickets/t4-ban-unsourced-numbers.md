# Ban unsourced quantities in advocate answers

`wayfinder:task` · OPEN · blocked by: T2 (closed) · **frontier — reshaped by T2**

## Reshaped by T2's result

"Only cite numbers from the REFERENCE MATERIAL block" is now known to be too weak.
With grounding repaired, the pricing probe fetched a *company valuation article*
and the panel quoted prices off it as authoritative. The rule must gate on whether
the source plausibly carries that kind of fact, not merely on whether a number
appeared somewhere in the block. Decide the source-quality test as part of this
ticket, or split it out.

## Question

`_ADVOCATE_SYS` currently says nothing about evidence. Across the nine probes the
advocates invented: €0.30 (25x wrong), "110M msg/sec", a "90-minute heartbeat"
nobody mentioned, "1-3% accuracy gains", and a citation "[A Comparative
Analysis], 2023" that appears not to exist.

Add a rule: a quantity, price, benchmark or citation may only appear if it is in
the REFERENCE MATERIAL block; otherwise say the magnitude is unknown and argue
the shape of the trade-off instead.

Sequenced AFTER T2 deliberately — with grounding repaired, the reference block is
usually populated, so the rule suppresses invention rather than suppressing
answers. Applying it while grounding is still broken would gut every answer.

Constraint: advocates have 120 words total. Measure whether the rule costs enough
budget to truncate recommendations.

Verified by: re-run probes 2, 6, 7, 8 and confirm no unsourced quantity appears;
confirm answers still end with a complete recommendation sentence.
