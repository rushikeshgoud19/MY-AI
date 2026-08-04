# MAP — Stop the tribunal inventing facts

`wayfinder:map` · local-markdown tracker · tickets in `./tickets/`

## Destination

The orchestra never states a number, price, or dated fact it cannot source — it
either grounds the claim or says it does not know. Reached when the nine probe
questions (see `probes.md`) run clean: no fabricated quantity survives into a
verdict, and answer quality on the contested questions does not drop.

## Notes

- Domain: `server/orchestra.py` (panel, prompts, rounds) and
  `server/orchestra_tools.py` (grounding backends). Read the module docstrings
  first — they carry measured results, not guesses.
- **The orchestra runs in TWO places**: `server/ai.py` + `server/processor.py`
  on the Azure VM, and `scripts/run_orchestra.py` locally via the Agentic OS
  console. Any grounding source must be readable from both. The console's
  `localhost:4517` is NOT reachable from the VM — that rules out the dashboard
  API as a fact source.
- Advocates have a hard 120-word budget. Every prompt rule added spends argument
  budget, so rules must earn their words.
- Verify by re-running the real thing: `python scripts/run_orchestra.py "<q>"`
  and reading the NDJSON `grounding` / `scores` / `verdict` events. A change that
  is not visible in those events did not happen.
- Execution rides in this map (deviates from wayfinder's plan-only default):
  tickets that are pure prompt edits get implemented and verified in the same
  session that decides them.

## Decisions so far

- [Diagnose why the pricing question fabricated numbers](tickets/t1-diagnose-pricing-failure.md) —
  Grounding **never fired**. `_QUERY_SYS` judged a factual pricing question to be
  "purely normative" and returned `NONE`, so the backend chain was never called
  (`backend: "none"`, `sources: []`). The chain itself is healthy. Separately:
  the judge *did* score the fabrication down (3–5/10) and named "unsourced
  pricing" as the defect, but the synthesis step folded the invented figures back
  into the final verdict anyway. Two distinct bugs, neither of them the one
  originally assumed (a thin memory source).
- [Stop the query-writer refusing to search factual questions](tickets/t2-fix-query-gate.md) —
  `_QUERY_SYS` rewritten to ask for a web query (not a Wikipedia phrase) and to
  reserve `NONE` for questions with no checkable part at all. Verified both ways:
  the pricing probe now grounds (`marginalia+ddg`, 682 chars, 3 sources) and a
  pure-ethics probe still skips the search. The `REFERENCE MATERIAL` header now
  names the real backend instead of always claiming Wikipedia. **The pricing
  answer is still wrong** — grounding was necessary, not sufficient.
- [Stop synthesis re-asserting defects the judge already named](tickets/t3-stop-verdict-laundering.md) —
  the defects were never *in scope* at synthesis: the final call received only the
  question and the answers, and un-revised low scorers were merged in unmarked.
  Each answer now carries the judge's own score, "not revised", and the defect it
  named, and `_JUDGE_FINAL_SYS` forbids restating a claim it flagged. Verified:
  the flagged claims are gone and the verdict flipped to the defensible
  conclusion. Arithmetic still wrong — graduated to its own ticket.

## Not yet specified

- Source QUALITY has no gate. The pricing run grounded on a company-valuation
  article and a generic directory page, and the advocates treated both as
  authoritative. Ranking or filtering hits before they enter the reference block
  is a decision T4 now depends on.

- Whether the ADOPT/REJECT threshold should treat "contains an unsourced
  quantity" as an automatic score cap, rather than leaving it to the judge's
  discretion. Depends on what T3 finds about where laundering happens.
- Whether triage should route "mixed" questions (part lookup, part judgement)
  differently — the pricing question is factual AND comparative, and the current
  binary SETTLED/CONTESTED has no way to say "search first, then debate".
- How stale a grounded fact may be before it is worse than no fact. Surfaces once
  a memory/facts source exists (T5).

## Out of scope

- Replacing the judge model or re-running the 18-debate soak. The judge's scoring
  was measured good on 2026-08-02 and this map's diagnosis confirms it caught the
  defect. Judge selection is a separate effort.
- The Agentic OS galaxy view itself. It is a consumer of memory, not part of the
  tribunal's correctness.
