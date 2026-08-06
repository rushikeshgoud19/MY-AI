# The AI invented a price. Here is the engineering that made it stop.

A case study in building an LLM system that says **"I could not verify that"**
instead of guessing — and measuring whether it actually does.

---

## The failure

A multi-agent panel was asked a question involving a current API price. It did not
know the price. It did not say so.

It produced a figure — **"$0.25 per million tokens"** — did arithmetic on that
figure, and then reasoned confidently from the result. Every downstream number was
wrong, and nothing in the output indicated it.

This is the ordinary failure mode of LLM systems, and it is worse than being wrong,
because the output is *fluent*. There is no signal to the reader that anything has
gone bad. A person reading it has no way to tell that step one was invented.

## What did not work

**Reading the output and forming an opinion.** That was the first approach and it
found real bugs — but it could never prove an improvement, and twice a remembered
score turned out to be stale. One component was remembered as scoring "8/9". When
it was actually measured, it was **13/15**. Neither the memory nor the impression
was reliable.

**Having a model grade the model.** This is the obvious design and it is a trap.
The entire problem is that language models assert things confidently and wrongly.
Grading with one puts the failure mode *inside the measuring instrument* — the
grader can hallucinate the grade.

## What worked

### 1. Ground the answer in pages actually fetched

Not search-result snippets. The system retrieves the page, extracts the region
densest in the question's key terms, and answers from that. If it cannot fetch, it
does not substitute memory.

### 2. Check arithmetic deterministically

Every figure in a candidate answer is re-derived in code, not by the model. An
answer whose sums do not add up has its score capped regardless of how confident
the prose is.

### 3. Check every citation against the source material

A citation that does not appear in the fetched text is flagged as invented. This
catches the specific and common failure of attributing a real-sounding claim to a
real source that never said it.

### 4. Route by question type, and ground the volatile ones

Triage splits three ways rather than two. A question that is *settled* answers
cheaply in about 2 calls. A question that is *contested* goes to a full panel at
around 11 calls. The gap that caused the invented price was a third case: a
question that is settled **but volatile** — anything matching "right now", "latest",
"price", "free tier".

Those now ground first and answer in a single call, and that solo answer gets the
same arithmetic and citation checks an adversarial advocate's would. A failed check
falls through to the full panel.

### 5. Measure it with a grader that cannot hallucinate

A scored eval of 15 cases with known answers. Grading is **substring and regex
matching only**. That deliberately limits the eval to questions with a checkable
answer — which is the correct limit. Advice-shaped questions stay qualitative and
are not pretended to be measurable.

**Two scores, because they fail independently:**

- **CORRECTNESS** — is the final verdict text right?
- **PROCESS** — did grounding fire, did the fact-checkers fire, did triage route it
  cheaply?

One score cannot distinguish "right for the right reasons" from "right by luck". An
earlier version produced a run that was *directionally right with every figure
wrong*, and a single score is blind to that.

---

## The result

| | |
|---|---|
| Eval baseline | **15 / 16** |
| After the volatile-routing fix | **15 / 15** |
| Settled path cost | ~2 calls, ~500 tokens |
| Contested path cost | ~11 calls, ~6k tokens |

And the specific behaviour change on the question that started it:

> **Before:** `$0.25 per million tokens` *(invented, then used in arithmetic)*
>
> **After:** `could not verify a current figure, check [Pricing]`

**That refusal is the deliverable.** It is unglamorous, it is what a careful
engineer would say, and it is the difference between a system you can put in front
of a customer and one you cannot.

---

## Why this matters if you ship an AI feature

If you have a support bot, a summariser, or a RAG application in production, you
have this problem. The questions worth asking:

1. **When your system does not know, what does it output?** If the answer is "a
   plausible-sounding guess", you will find out from a customer.
2. **How do you know it is right?** If the answer is "we read the outputs and they
   seem good", that is the approach that produced a stale remembered score here.
3. **Are you grading with a model?** If so, the grader can hallucinate the grade.
4. **Can you tell "right" from "right for the right reasons"?** One score cannot.

## What this case study does not claim

- **Not a benchmark.** 15 cases with checkable answers, on one system. It is not a
  general claim about LLM accuracy.
- **The eval only covers questions with a checkable answer.** That is a real limit
  and it is deliberate — the alternative was model-grading, which is worse.
- **15/15 is the eval score, not a guarantee.** It means the known failure modes are
  caught by a test that runs on demand, which is a much narrower claim than "the
  system is correct".

Stating those limits is the same discipline as the product itself.

---

*Code: `server/orchestra.py`, `server/orchestra_tools.py`,
`scripts/orchestra_eval.py`. Measurement notes: `docs/wayfinder/`.*
