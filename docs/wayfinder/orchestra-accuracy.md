# MAP — Make the tribunal's answers correct, and prove it

`wayfinder:map` · local-markdown tracker · tickets in `./tickets/` (prefix `a`)

Follow-on from [Stop the tribunal inventing facts](orchestra-grounding.md), which
reached its destination: the panel no longer states figures it cannot source, and
says "unverified" instead of inventing. Being honest about what it does not know
is not the same as being right about what it does.

## Destination

The tribunal's factual answers are CORRECT, and correctness is MEASURED rather
than judged by whoever is reading. Reached when a scored eval of questions with
known answers runs on demand, and the grounding pipeline has been improved against
that score rather than against impressions.

## Notes

- Same domain as the previous map: `server/orchestra.py`,
  `server/orchestra_tools.py`. Read the module docstrings first; they carry
  measured results.
- **Measurement comes first and blocks everything.** The previous effort improved
  real things but graded them by reading verdicts and forming an opinion, and it
  twice found that a remembered number was stale (triage "8/9" measured 13/15).
  An accuracy change that cannot be scored is a change nobody can defend.
- Verify against the real pipeline: `python scripts/run_orchestra.py "<q>"` and the
  NDJSON events. Bench harnesses belong in the session scratchpad, but their
  NUMBERS belong in the ticket.
- Execution rides in this map, as before: tickets that are small and provable get
  implemented and verified in the session that decides them.
- Cost discipline is a standing constraint. The settled path is 2 calls / ~500
  tokens and a contested debate ~11 calls / ~6k. Any accuracy gain that multiplies
  that has to say so out loud and justify it.

## Decisions so far

<!-- nothing yet; charting resolves nothing -->

## Not yet specified

- Whether the panel should be able to run ONE follow-up search when it concludes a
  figure is unknown, rather than settling for the ignorance it just admitted.
  Depends on what the eval says the actual failure rate of first-search is.
- Provenance: `gather_grounding` returns source TITLES only, so a verdict in the
  journal cannot be re-checked against what it was built from months later. Sharp
  enough to fix, not yet clear whether it is an accuracy problem or a UI one.
- Whether accuracy differs enough by question TYPE — pure lookup, comparison,
  prediction, advice — to need different machinery per type. Suspected from the
  probe results but unmeasured, and the eval will say.

## Out of scope

- Changing the judge model, or re-running the 2026-08-02 judge benchmark. Judge
  selection is its own effort and its measured basis still stands.
- The Agentic OS console and the decision journal UI. They consume verdicts; they
  do not make them more correct.
