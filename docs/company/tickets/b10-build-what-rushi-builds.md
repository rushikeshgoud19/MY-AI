# Pivot the offer to what Rushi can actually build

`wayfinder:grilling` (HITL) · **DECIDED 2026-08-06 by Rushi** · supersedes B3

## What changed

Rushi, 2026-08-06: *"i think its best for us to leave out india... lets focus on
foreign brands. i can do a lot of stuff like web development platform development
backend setup... lets focus on what we can bring to the table rather than going
somewhere where i dont know shit."*

**Both parts are accepted.**

1. **India is dropped as the buyer market.** He has no Indian business contacts
   ("No one man sorry"), and [B9](b9-gst-vendor-checks.md)'s GST route required
   approaching Indian businesses directly. **B9 is shelved, not deleted** — the
   research holds and `scripts/gst_check.py` works if an Indian buyer ever appears.
2. **The offer moves to what he can build.** Every offer so far — counterparty
   verification, company registers, GST — was research work he has no background in
   and no appetite for. An offer the principal cannot personally deliver or care
   about is fragile, and he is right to say so.

## The correction, stated once

**"Web development" is not an offer.** It is the most commoditised category on the
internet, and the map's own rule is that first customers come from narrowing until
the offer is almost embarrassingly specific. Selling "web development, platform
development, backend setup" competes with millions of people on price, which is the
exact trap [B3](b3-pick-the-offer.md) was written to avoid.

**But he has something most developers do not**, and it is in this repo.

## What is actually demonstrable

| Asset | Size |
|---|---|
| `server/orchestra.py` — multi-agent tribunal | 962 lines |
| `server/orchestra_tools.py` — grounding, fetch, deterministic `calc` | 479 lines |
| `scripts/orchestra_eval.py` — scored, deterministic eval | 229 lines |
| `docs/wayfinder/` | orchestra-accuracy, orchestra-grounding, probes |

And the reasoning behind it, quoted from his own eval script:

> *"GRADING IS DETERMINISTIC ON PURPOSE. The obvious design is to have a model grade
> the answer against a reference, and this map exists precisely because small models
> assert things confidently and wrongly — grading with one would put the failure mode
> inside the measuring instrument."*
>
> *"TWO SCORES, because they fail independently. CORRECTNESS is the verdict text.
> PROCESS is what the pipeline did to get there... The previous effort produced a run
> that was directionally right with every figure wrong, and one score cannot say
> that."*

That is not junior CRUD work. It is someone who understands **why** AI systems fail
and who built the instrumentation to catch it. Very few freelance developers can
write that paragraph, and fewer can show the code under it.

## Proposed offer

> **AI features that refuse to make things up — with a scored eval that proves it.**

- **Buyer:** a foreign company that has shipped, or is shipping, an AI feature that
  hallucinates. A support bot inventing policy, a summariser inventing figures, a
  RAG app citing sources that do not say what it claims.
- **Problem:** they cannot tell whether their AI output is right, and they find out
  from a customer. They have no eval, and the "obvious" fix — having a model grade
  the model — puts the failure inside the instrument.
- **Deliverable:** grounding + deterministic citation and arithmetic checking bolted
  onto their existing feature, plus **a scored eval they keep and can re-run**.
- **Why defensible:** everyone selling "AI automation" demos a confident answer. The
  proof here is a repo where the system says *"could not verify"* and a number that
  says how often it is right. Anyone can claim it; this can be shown.

**This keeps the differentiator the map was built on** — auditable output, refusal
over invention — and moves it onto work Rushi can personally deliver. The three
company-check samples and `company_check.py` become *evidence of method*, not the
product.

## What this changes about the channel

**The marketplace rejection may not apply here.** His Freelancer.com bids were
rejected on criteria for research and data jobs where he had no profile, no
portfolio and no credential. **For development work he has a repo.** That is a
different application with different evidence, and the rejection should not be
generalised from one category to another without testing.

Not asserted — flagged as worth retesting.

## Risks, not buried

- **"AI eval" buyers may be scarcer than they look.** Companies that know they have a
  hallucination problem are often large enough to hire staff. The buyer who is small,
  burned, and paying is unproven — the same gap [B2](b2-what-people-pay-for.md) never
  closed.
- **The orchestra is built for Rushi's assistant, not as a product.** Bolting it onto
  someone else's stack is unscoped work. The first sale should be small.
- **Nothing here has been shown to a buyer either.** The pivot does not reset that
  count; it stays at zero.

## Open — the same question as always

**Who is shown this, and how are they reached?** The channel question survives every
pivot, and it is the only one that has never been answered.


---

## Progress 2026-08-06 — the evidence already existed and was buried

Went looking for the channel and found something better first: **the portfolio piece
already exists, in `docs/wayfinder/orchestra-accuracy.md`, where no client will ever
see it.**

Measured, dated, and specific:

| | |
|---|---|
| Eval baseline | **15 / 16** |
| After the volatile-routing fix | **15 / 15** |
| Settled path | ~2 calls, ~500 tokens |
| Contested path | ~11 calls, ~6k tokens |
| Concrete change | invented **"$0.25 per million tokens"** became **"could not verify a current figure, check [Pricing]"** |

Plus a documented instance of the exact problem the product solves, found in his own
process: a component *remembered* as scoring "8/9" measured **13/15** when actually
tested.

**This is the "criteria" evidence Freelancer said he lacked.** The bids were rejected
because nothing demonstrated capability. This demonstrates it with a number.

**Written up as [`case-study-refusal.md`](../demo/case-study-refusal.md)** — a
technical case study, not marketing. It leads with the failure, explains why model-
grading is a trap, gives the fix, gives the score, and ends with a section stating
what it does **not** claim (15 cases is not a benchmark; the eval only covers
checkable answers; 15/15 is a test result, not a guarantee).

### Why this is not the branding trap the map warns about

The map rules out landing pages, logos and audiences as fake progress. This is
different and the distinction is load-bearing:

- A landing page **claims** capability. This **demonstrates** it with a reproducible
  score.
- It addresses the **documented** reason the bids were rejected — no evidence of
  capability — rather than a hypothetical one.
- It costs nothing, needs no card, no account and no gatekeeper.
- Every future application, on any channel, can point at it.

It is not an audience play. One artefact, once, because there is currently nothing
a client can look at.

### Channel scan, recorded so it is not repeated

Freelancer.com dev boards carry far more volume than the research boards ever did —
**python 201 jobs, machine-learning 36, artificial-intelligence 22, chatbot 8**,
against 2 mislabelled jobs under due-diligence. But filtering 16 AI/dev candidates
for *open* (not select-only) **and** ≤15 bids returned **one** match, and it was an
AI *trainer* teaching sessions rather than building.

**Contract rates for the work itself are real:** $75–$200+/hour for generative-AI
contract work, with evaluation expertise named as what drives the top end
([Consultadd](https://consultadd.com/blog/how-to-hire-generative-ai-engineers)).
**Caveat that matters:** those rates are for *demonstrated production experience*.
Rushi has a repo, not production. The case study narrows that gap; it does not close
it.

## Next

**Rushi's approval to publish the case study**, and where. It is drafted and
unpublished. Nothing goes public without him reading it.
