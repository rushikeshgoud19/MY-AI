# What the context budget costs

`ContextManager.hard_budget` (`server/context_manager.py`) keeps prompts small by
dropping the oldest turns until conversation history fits under
`context_token_budget`. Production runs it at **4000**.

That knob is the reason input tokens are small. This measures the other side of the
trade — and the answer is more specific than "quality drops".

## Run it

```bash
python eval/context_budget_eval.py
```

```bash
python eval/context_budget_eval.py --live --json eval/results.json
```

Offline needs no API key. `--live` calls `mistral-small-latest` and grades real answers.

## Method

Each probe plants a distinctive token in an early turn — *"my deploy key is
NOVA-7731"* — buries it under **D** filler exchanges, then asks for it back. An answer
is correct iff it contains the planted token.

**The grader is exact match, not a model.** There is no LLM judge here, so there is no
judge to calibrate. That is deliberate: this codebase already learned that a prompted
judge finds a way to pass everything (see the design note in `server/orchestra.py` —
18 adopts out of 18). Correctness of a needle lookup is decidable, and decidable things
belong in code.

Filler turn lengths are drawn from the real distribution in `.data/session_store.db`
(session `main`, n=367 turns with counts: min 1 / median 24 / max 254 tokens). They are
generated, not copied, so no private conversation content lives in the repo. Everything
is seeded — the same seed gives the same corpus, and every budget sees identical input.

Two tiers:

- **offline** — runs the real `ContextManager` over a depth × budget grid and records
  whether the planted fact *survived the trim*. This is the ceiling on answer quality.
- **live** — at the production budget, calls the model across the depth sweep and
  grades the answer. Retention is the ceiling; this shows how close the model gets.

## Result: retention (16 probes per cell, seed 20260823)

```
 depth  untrimmed |       b=1000       b=2000       b=4000       b=8000
     0         32 |   100%    32t   100%    32t   100%    32t   100%    32t
     2        637 |    94%   637t   100%   637t   100%   637t   100%   637t
     4       1499 |    12%   942t   100%  1499t   100%  1499t   100%  1499t
     8       2994 |     0%   934t     0%  1879t   100%  2994t   100%  2994t
    12       4159 |     0%   898t     0%  1893t    38%  3898t   100%  4159t
    16       5368 |     0%   893t     0%  1923t     0%  3931t   100%  5368t
    24       8458 |     0%   873t     0%  1936t     0%  3918t    38%  7915t
    32      11245 |     0%   897t     0%  1871t     0%  3934t     0%  7929t
    48      16633 |     0%   915t     0%  1821t     0%  3875t     0%  7904t
```

**Recall horizon** — the deepest point at which a fact is still fully recoverable:

| budget | horizon | prompt tokens at horizon |
|---:|---:|---:|
| 1000 | 0 exchanges | ~32 |
| 2000 | 4 exchanges | ~1,499 |
| **4000 (production)** | **8 exchanges** | **~2,994** |
| 8000 | 16 exchanges | ~5,368 |

Doubling the budget roughly doubles the horizon. Cost scales linearly with how far back
the system can remember, which is the least surprising possible result and worth having
as a number rather than an intuition.

## Result: live answers vs the ceiling

`mistral-small-latest`, budget 4000, 16 probes per depth, 112 calls, 0 errors:

```
 depth   fact kept    answered      gap
     0       16/16       16/16        0
     4       16/16       16/16        0
     8       16/16       16/16        0
    12        6/16        6/16        0
    16        0/16        0/16        0
    24        0/16        0/16        0
    32        0/16        0/16        0
```

**The gap is zero at every depth.** The model answered correctly on exactly the probes
where the fact survived, and missed on exactly the probes where it didn't.

So the budget is not degrading reasoning. It is deleting evidence. Below the horizon
the trimming is free — the model uses everything that survives. Above it, the loss is
total, and a better model does not recover it, because the fact was gone before the
model was ever called.

## What this does not measure

Worth stating plainly, because it is the first thing to push on:

- **This is needle-in-a-haystack recall**, the easiest retrieval shape there is. A
  single distinctive token is either present or absent. It does not measure degradation
  in multi-fact synthesis, tone, or instruction-following, all of which could erode
  well before a fact disappears.
- **Filler is synthetic and topically unrelated** to the planted fact. Real history has
  partial restatements and paraphrases, which would push the effective horizon further
  out than measured here.
- **`_estimate_tokens` is `len // 4`**, the same approximation production uses. It is
  not a real tokenizer, so every token figure here is an estimate with the same bias as
  the system it measures.
- **It isolates one knob.** Total request size also includes the system prompt, persona,
  memory recall and tool schemas. This measures the history budget only.

## The number to take away

At `context_token_budget=4000`, a fact stays recoverable for **8 exchanges**, starts
degrading at 12 (38% retained), and is gone by 16. Answer accuracy tracks that curve
exactly.
