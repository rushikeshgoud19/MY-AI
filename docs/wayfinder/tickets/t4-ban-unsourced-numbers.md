# Ban unsourced quantities in advocate answers

`wayfinder:task` · **CLOSED** · blocked by: T2 (closed)

## Question

`_ADVOCATE_SYS` said nothing about evidence. Across the nine probes the advocates
invented €0.30 (25x wrong), "110M msg/sec", a "90-minute heartbeat" nobody
mentioned, "1-3% accuracy gains", and a citation "[A Comparative Analysis], 2023"
that appears not to exist.

Reshaped twice: T6 already covers *computed* figures via CALC lines, so what
remained was **asserted** figures and **fabricated citations** — neither computed
nor covered — plus the source-quality question T2 exposed.

## Resolution

Split three ways, by what is decidable:

**1. Attribution (prompt).** `_ADVOCATE_SYS` now requires any price, benchmark,
percentage, date or study the advocate did NOT compute to come from the REFERENCE
MATERIAL, naming its source in square brackets exactly as it appears there. If it
is not there, the figure is unverified. Never invent a source, paper or year, and
never cite from memory.

**2. Fabricated citations (code — decidable).** `_check_citations()` extracts
citation-shaped spans (`[Title], 2023`, `(Smith et al., 2019)`, `[Exact Title]`)
and tests each against the normalised reference text. Absent → defect, merged into
`defects` and the score capped at 5.0, same channel as the arithmetic check. If
nothing was grounded at all, ANY citation is unsupported by construction. Bare
`[1]` and `[unknown]` are ignored — they are not citations, and flagging them
would train the panel to stop bracketing anything.

**3. Source quality (judge — a judgement, not a computation).** No deterministic
gate. `_JUDGE_REVIEW_SYS` now says to judge the source, not just the number: a
current price or limit taken from a funding story, a directory listing or a dated
blog is the defect even when the figure looks reasonable. Code was deliberately
kept out of this — "is this source the kind of thing that can carry this fact" has
no clean decidable test, and the module's principle is that code owns what is
decidable, not what is arguable.

## Verification

`_check_citations` unit-tested on 9 cases: probe 7's exact
`([A Comparative Analysis], 2023)` flagged; `(Smith et al., 2019)` flagged; real
sources from the block pass case- and punctuation-insensitively; a citation with
no grounding at all flagged; `[1]` and `[unknown]` correctly ignored.

Live run of probe 7 — the probe that produced the fake citation:
**no fabricated citation, and none of the invented statistics.** Vanitas attributed
to `[7900xtx LLM inference notes]`, a real block source; Senku's CALC lines
(`1000/10 = 100`, `1000/(10/5) = 500`) both check out.

## Two residuals

**Prompt bug, fixed in this ticket:** "write NO CALC line at all" was read as an
instruction to write the words "NO CALC", which Ayanokoji did. Reworded to say
what to do rather than what not to do. Worth remembering as a class of bug — a
negative instruction phrased with the literal token in it.

**Source RELEVANCE is still not caught, and part 3 above did not work.** In the
same run Vanitas used a consumer-GPU forum post about 7900XTX local inference to
argue about an API-based orchestra, concluding "cut costs by 80%" — a real source,
correctly cited, and entirely inapplicable. The judge scored it 8. So the new
"judge the source" rule did not fire on a clear mismatch. Graduated to
[Judge the fit between a claim and the source it cites](t7-source-fit.md).
