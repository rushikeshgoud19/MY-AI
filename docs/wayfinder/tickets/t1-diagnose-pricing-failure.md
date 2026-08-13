# Diagnose why the pricing question fabricated numbers

`wayfinder:task` · **CLOSED** · blocks: T2, T3, T4, T5

## Question

The probe "What does Mistral charge per million tokens for ministral-8b right
now, and is the orchestra's 5-call design cheaper than one mistral-large call?"
produced confident invented prices and arithmetic wrong by 25x. Which layer
failed: the grounding backends, the relevance gate, or the advocates ignoring
what was fetched?

## Resolution

Ran the exact question through `scripts/run_orchestra.py` and captured the
NDJSON. **None of the three suspected layers failed — the search never happened.**

```json
{"kind":"grounding","ok":false,"query":"","sources":[],"chars":0,
 "backend":"none","reason":"no factual grounding applicable to this question"}
```

`_QUERY_SYS` asks ministral-8b for a search phrase and permits it to reply `NONE`
when "the question is purely normative, ethical, or a matter of opinion". It read
a live-pricing lookup as opinion. The backend chain (marginalia → duckduckgo →
firecrawl → wikipedia) was never invoked, so the advocates argued with nothing in
front of them and filled the vacuum.

Secondary finding, independent of the above: the judge **did** detect the
fabrication — scores `light:4, ayanokoji:3, vanitas:5, senku:9`, with light's
named defect being "uses outdated/unsourced pricing and conflates Mistral
models". The final synthesised verdict nevertheless asserted
`€0.14 / €0.42 per million, as of June 2024`. A defect the judge named was
laundered back into the answer by the synthesis step.

Tertiary: stance retune works — Light Yagami ran as COST FIRST, not its fixed
ATTACK THE PREMISE, so the judge did re-aim the panel for this question.

Raw capture: 17 events, 11 model calls, 7017 tokens, 17.0s.
