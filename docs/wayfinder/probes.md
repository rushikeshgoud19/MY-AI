# The nine probes

The regression suite this map is measured against. Each targets one mechanism.
Run with `python scripts/run_orchestra.py "<question>"` and read the NDJSON
`triage`, `grounding`, `scores` and `verdict` events — not just the prose.

Baseline results are from the run on 2026-08-05, before any fix.

| # | Probe | Targets | Baseline |
|---|-------|---------|----------|
| 1 | Is appending 10k rows to SQLite faster inside one transaction or outside? | triage precision | PASS |
| 2 | What does Mistral charge per million tokens for ministral-8b, and is 5 calls cheaper than one mistral-large? | grounding | **FAIL** — invented prices, arithmetic 25x wrong, conclusion inverted |
| 3 | Since Mizune's APK already runs a foreground service, should the WS reconnect live there or in the boot receiver? | false premise / ATTACK THE PREMISE | **INVALID PROBE** — see below |
| 4 | What regex parses the `### **USER** — *timestamp*` blocks out of the memory export? | stance retune | PARTIAL — pattern good, starved stances emitted filler |
| 5 | I have no credit card. Rank the genuinely free ways to host Mizune's brain 24/7 with public HTTPS. | project facts | **FAIL** — recommended Oracle Free Tier, which requires a card |
| 6 | Mizune flaps offline every few hours. Should I add a watchdog that restarts on missed heartbeats? | groupthink | PASS — refused the obvious yes, led with root cause |
| 7 | What's the strongest argument the 5-model orchestra is worse than one good model? | self-criticism | PARTIAL — right conclusion, fabricated citation |
| 8 | Should the WhatsApp and ACP/Buzz paths share one memory service, or should Buzz cache and sync? | trade-off honesty | **FAIL** — hallucinated 110M msg/sec, reasoned about a fictional system |
| 9 | Rank by what breaks Mizune first: ACP auth mismatch, WebView kill, unpruned 3.4k-turn log, judge 429s. | do rounds 1-2 do anything | PASS on content; round-0 vs round-2 delta not yet measured |

## Probe 3 is invalid — the premise is TRUE

Written to test whether the panel attacks a false premise, on the belief that the
APK was a bare Capacitor WebView with zero services. It is not:
`mizune-android/.../service/MizuneService.kt` calls `startForeground()` and
returns `START_STICKY`, and the manifest holds `FOREGROUND_SERVICE`,
`FOREGROUND_SERVICE_DATA_SYNC` and `FOREGROUND_SERVICE_MICROPHONE`. The belief
came from an Aug-1 planning document describing the state *before* that work
landed.

So the panel accepting the premise was CORRECT, and its answer (put the reconnect
in the existing foreground service) is defensible. **This probe tests nothing as
written** and needs replacing with a premise that is actually false before the
ATTACK THE PREMISE stance can be judged at all.

Standing lesson for this map: a probe whose answer depends on project state must
be checked against the code, not against a memory of the code. That is the same
failure mode the map exists to fix, committed by the person writing the map.

## The pattern

Reasoning is sound; **quantities are invented**. Every failure is a fabricated
number or citation, not a broken argument. 2, 6, 7 and 8 all produced confident
figures with no source behind them.

## Probe 2 after T2

Grounding now fires (`marginalia+ddg`, 3 sources). The answer is still wrong: it
grounded on a valuation article and computed a per-token comparison off by ~8x.
Still FAIL — see T4 and the map's Not-yet-specified.
