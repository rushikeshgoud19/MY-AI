# Judge the fit between a claim and the source it cites

`wayfinder:grilling` · **CLOSED** · graduated from fog by T4

## Question

Fabricated citations are caught deterministically and real sources are correctly
attributed. What was NOT caught is a real, correctly-cited source that cannot
support the claim resting on it — probe 2 reading API prices off a valuation
article, probe 7 arguing hosted-API cost from 7900XTX consumer-GPU forum notes and
scoring 8/10 for it. The T4 prompt rule was already there and did not fire.

## Resolution

The ticket said to check one thing first, and it was the whole answer:
**the judge could not see the reference material.** Both judge calls were

```python
run(judge_model, _JUDGE_REVIEW_SYS,  f"QUESTION: … ADVOCATE ANSWERS: …")
run(judge_model, _JUDGE_FINAL_SYS,   f"QUESTION: … REVISED ANSWERS: …")
```

Question and answers only. `ground_prefix` went to the advocates and never to the
judge. So T4's "judge the source, not just the number" asked a reader to assess
sources it had never been shown — the instruction was not weak, it was
unanswerable. The other three options in this ticket were premature, as suspected.

Implemented:

1. `ground_prefix` is now passed to BOTH judge calls — review and synthesis. Cost
   is ~250 tokens on two calls; grounding is capped at 900 chars.
2. `_JUDGE_REVIEW_SYS` upgraded from an abstract rule to worked examples, the same
   move that stabilised `_TRIAGE_SYS`: a price off a funding story, throughput for
   a hosted API argued from a consumer-GPU thread, a figure with no source at all.
   Plus the ordering that matters — **an admitted unknown should score HIGHER than
   a confident unattributed number** — and "the prose is not the evidence".

## Verification

Re-ran probe 7 against the identical grounding set (same three sources, including
the 7900XTX thread):

| advocate | before | after | judge's defect after |
|---|---|---|---|
| senku | 9 | **4** | consumer-GPU local inference latency does not translate to hosted API throughput |
| vanitas | 8 | **3** | misapplies 7900XTX forum data to API context |
| light | 7 | 7 | cites the forum thread to argue API efficiency — different systems |
| ayanokoji | 6 | **9** | (none — cited nothing, argued structurally) |

The ranking inverted for exactly the right reason: the answer that made no
source claim at all is now the winner, and all three source-misfit answers were
independently named. The verdict now closes with "hardware-specific latency
(e.g. 7900 XTX) or unverified API pricing cannot be used to generalize
performance or cost" — it names the trap instead of falling into it.

Standing lesson for this map, now twice earned: before strengthening an
instruction that is not firing, check whether its reader has the information the
instruction requires. T4's rule and T3's defects both failed for the same reason —
the judge was asked about something outside its context window.
