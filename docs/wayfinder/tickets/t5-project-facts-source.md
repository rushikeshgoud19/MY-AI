# Give the tribunal Rushi's own project facts

`wayfinder:grilling` · OPEN · blocked by: T2, T4

## Question

**P5** recommended Oracle Cloud Free Tier to someone with no credit card — the
exact constraint stated in the question, and a fact already recorded in the
`mizune-free-infra` memory note. No web search fixes this: the constraint is
private to Rushi, and the answer was already written down somewhere the tribunal
cannot see.

(P3 was originally cited here too, as a false-premise failure. It is not one —
the APK really does run a foreground service; see `probes.md`. That correction
*strengthens* this ticket rather than weakening it: the premise was checkable
against the repo, and neither the panel nor the person writing this map checked
it. A facts source that includes current repo state would have settled it.)

Where should curated project facts live, given the map's hard constraint that the
orchestra runs BOTH on the Azure VM and locally?

Candidates:
- `MIZUNE_FACTS.md` committed to this repo — both contexts read it, git syncs it,
  staleness is visible in the diff, and Rushi controls what counts as truth.
- Mizune's own ChromaDB memory via her API — always current, but conversational
  rather than curated, and the local path needs her online.
- The `~/.claude` memory notes the galaxy indexes — richest and already written,
  but laptop-only, so the VM path gets nothing.

Also to decide: how facts are SELECTED per question (concept overlap? keyword?),
and how a stale fact is prevented from becoming the next confident falsehood —
grounding a premise on an outdated note is the same failure wearing a new coat.
