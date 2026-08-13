# Give the tribunal Rushi's own project facts

`wayfinder:grilling` · OPEN · blocked by: A1 · carried from the grounding map

## Question

Carried over from `orchestra-grounding.md`, where it was ruled out of scope: it
makes the tribunal better INFORMED rather than less DISHONEST, which was that
map's destination. Here it is in scope.

Questions about Mizune, the VM, the APK or Rushi's constraints cannot be answered
from the web at all. The panel currently handles them by admitting ignorance —
honest, and useless. Probe 5 is the shape: it now correctly says no free host
exists without a card, but it says it generically, not because it knows he has no
card.

The hard constraint from the previous map still holds and is the crux: **the
orchestra runs BOTH on the Azure VM (`server/ai.py`, `server/processor.py`) and
locally (`scripts/run_orchestra.py`)**, so the console's `localhost:4517` cannot
be the source. Candidates: a facts file committed to this repo, her ChromaDB
memory via her own API, or the `~/.claude` memory notes (laptop-only).

Also unresolved: how facts are selected per question, and how a stale fact is
stopped from becoming the next confident falsehood. The APK premise in probe 3 is
the warning — a memory note asserting "zero services" would have been WRONG, and
the panel would have repeated it with more confidence than before.
