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
| 7 | What's the strongest argument the 5-model orchestra is worse than one good model? | self-criticism | PARTIAL → **citation fixed** after T4; see below |
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

## Full re-run after T2/T3/T4/T6/T7 (2026-08-05)

All grounded via `marginalia+ddg`, 11 calls each.

| # | scores | fact-check fired | outcome |
|---|--------|------------------|---------|
| 1 | light 3, senku 8, ayanokoji 6, vanitas 4 | arithmetic: vanitas | answer CORRECT but **triage said CONTESTED** — 11 calls for a settled fact. **Fixed: now SETTLED, 2 calls / 501 tokens** |
| 2 | light 4, senku 9, ayanokoji 3, vanitas 2 | — | PASS, self-consistent arithmetic, caveat named |
| 5 | light 9, senku 4, ayanokoji 3, vanitas 6 | citation: senku | **PASS** — "no provider offers a genuinely free 24/7 public HTTPS backend without credit card verification"; the Oracle recommendation is gone |
| 6 | light 9, senku 3, ayanokoji 4, vanitas 7 | — | PASS — "do not add a watchdog yet… it masks the root cause" |
| 7 | light 7, senku 4, ayanokoji 9, vanitas 3 | — | PASS — source misfit caught and named |
| 8 | light 7, senku 3, ayanokoji 6, vanitas 4 | arithmetic + citation: senku | **PASS** — real trade-off argument; the hallucinated "110M msg/sec" is gone |
| 9 | light 7, senku 4, ayanokoji 6, vanitas 3 | citation: senku | PASS — ranks log bloat first, argued from token math |

**The deterministic checks fire in live debates.** Probes 1, 5, 8 and 9 each had an
advocate flagged and score-capped — which retires the "proven by unit test only"
caveat carried by the arithmetic and citation tickets. In every case the flagged
advocate finished at 3–4 and did not win.

**New failure, not previously visible:** probe 1's triage. `_ADVISORY_RE` does not
contain "faster", so the triage model itself classified a settled benchmark
question as CONTESTED — the comparative "X or Y" shape reads like a design choice,
and the prompt says "when in doubt reply CONTESTED". Correct answer, ~6k tokens to
reach it. See
[Triage reads a settled comparison as a design choice](tickets/t8-triage-comparisons.md).

## The pattern

Reasoning is sound; **quantities are invented**. Every failure is a fabricated
number or citation, not a broken argument. 2, 6, 7 and 8 all produced confident
figures with no source behind them.

## Probe 2 across three runs

| run | state | result |
|---|---|---|
| baseline | grounding never fired | invented prices, arithmetic 25x wrong, conclusion inverted |
| after T2 | grounding repaired | real-ish prices off a valuation article, ~8x error, inverted again |
| after T3 | defects reach synthesis | plausible prices from the 9/10 answer, conclusion CORRECT, arithmetic still ~2.8x off |

| after T6 | arithmetic checked | **PASS** — CALC lines all correct, two advocates refused to invent prices, verdict €5.00 vs €16.00 with the token-parity caveat named |

Probe 2 took four runs to go from "invented everything" to "showed its working and
said what it did not know". Each fix narrowed the failure rather than papering over
it: grounding never ran (T2), the judge's own findings were discarded before
synthesis (T3), and nothing checked the multiplication (T6).

Residual risk on probe 2 is now the PRICES themselves — €0.25/€0.75 and €4/€12
came off a grounded page dated 2024-06-25 that may be stale. That is source fit,
not arithmetic — see
[Judge the fit between a claim and the source it cites](tickets/t7-source-fit.md).

## Probe 7 after T4

The fabricated `([A Comparative Analysis], 2023)` and the invented "1-3% accuracy
gains" are both **gone**. Vanitas attributed to `[7900xtx LLM inference notes]`, a
real source from the block, and Senku's arithmetic (`1000/10 = 100`,
`1000/(10/5) = 500`) checks out.

But `[7900xtx LLM inference notes]` is a consumer-GPU forum thread being used to
argue about an API-based orchestra, and the judge scored that answer 8. The panel
has stopped making sources up and has not yet learned to ask whether a source
applies. That is the whole content of the source-fit ticket.
