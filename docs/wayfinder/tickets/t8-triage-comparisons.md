# Triage reads a settled comparison as a design choice

`wayfinder:grilling` · **CLOSED** · surfaced by the full probe re-run

## Question

"Is it faster to append 10,000 rows to SQLite inside one transaction or outside
one?" has one right answer. Triage called it CONTESTED and convened the panel:
11 calls, ~6k tokens, to reach what one call would have produced. Can a
*measurable* comparison be separated from a *preference* comparison without
weakening the "when in doubt reply CONTESTED" default?

## Resolution

Built a triage-only bench (`scratchpad/triage_bench.py`) rather than judging the
change on the one probe that exposed it: 15 questions — the examples inside
`_TRIAGE_SYS`, the advisory cases `_ADVISORY_RE` was written for, and three
measurable comparisons — each classified twice to catch flip-flopping. One cheap
call per classification, no debates.

**Baseline: 13/15, 0 flip-flops.** That measurement found a SECOND bug this ticket
did not know about:

> `_ADVISORY_RE` promoted **"How do you spell 'necessary'?"** to CONTESTED. Its
> `how (?:do|should|can) (?:i|we|you)` branch matched "how do you spell" — while
> `_TRIAGE_SYS` lists spelling as a SETTLED example. The code override was
> contradicting the prompt it exists to backstop, and had been since it was
> written.

Two fixes:

1. `_ADVISORY_RE` restricted to **first person** (`i|we`, dropping `you`). Advice
   is asked about one's own situation; "how do you spell X" is a question about the
   world. "How can I make landing pages as good as Apple's?" still matches, so the
   case the override was built for is untouched.
2. `_TRIAGE_SYS` gained the distinction plus two worked examples: naming two
   options does not make a question contested — a comparison with a measurable
   answer is SETTLED however it is phrased, one that depends on the asker's
   situation is CONTESTED. The "when in doubt reply CONTESTED" default is
   unchanged.

## Verification

**After: 15/15, 0 flip-flops.** Both failures fixed and — the thing that mattered —
**no regression on the contested side**: all seven judgement questions still route
to debate, including "Is SQLite good enough for my app?" (the historically stubborn
case) and "Should I use SQLite or Postgres". The settled path did not become
greedy, which is what this ticket warned against.

End-to-end on the real pipeline, probe 1:

```
TRIAGE=SETTLED (single answer; no debate needed)
calls=2 tokens=501          # was 11 calls, ~6,000 tokens
```

Same answer, correctly reasoned (one disk write instead of 10,000).

## Note

The bench lives in the session scratchpad, not the repo — it is a measurement
tool, and the numbers it produced are recorded here. If triage is touched again,
rebuild it from this ticket rather than trusting a remembered score: the 13/15
baseline was itself a surprise against a note claiming 8/9.
