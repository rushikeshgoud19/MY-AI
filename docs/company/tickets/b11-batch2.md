# Outreach batch 2 — six messages, individually written

`wayfinder:task` (HITL) · **DRAFTED 2026-08-06** · child of [B11](b11-direct-outreach.md)

## Rushi's call, and he was right

*"10 companies these week who genuinely pay attention... then we can play the
waiting game."*

**Conceded.** My "one send, change one variable" rule was A/B logic borrowed from
high-volume testing. At cold-email reply rates a single message teaches nothing — no
reply is indistinguishable from noise. Ten individually-researched messages is what
the map's Notes actually sanction ("ten researched messages beat a hundred generic
ones"), and it produces a readable signal: **six well-targeted messages returning
nothing says something about the offer; one returning nothing says nothing at all.**

## Six, not ten — and why padding would be the failure

Of 178 postings in the [August 2026 HN thread](https://news.ycombinator.com/item?id=49156683),
**25 are AI-related with a real email and not US-only.** Of those, **six** have the
problem this offer solves. The rest were rejected rather than padded:

| Rejected | Why |
|---|---|
| Snout | Pet insurance; Remote US/Ontario only; not an agent-reliability problem |
| DeepSight | GPU algorithms, C++, medical imaging. No LLM agents |
| Klutch AI | Mobile engineer, Seattle onsite. Wrong discipline |
| Radical Numerics | Genomics research lab, onsite SF/Tokyo, senior research hires |

Hitting ten would have meant writing to four companies with no reason to care. That
is the line between "ten researched messages" and spam, and it is the whole reason
the map permits the former.

**Named-person addresses are prioritised.** `andrew@`, `lukasz@`, `tarek@`, `ivanc@`
reach a human. `recruiting@` and `jobs@` often do not.

## A shared angle that is true for five of the six

Most are hiring **ONSITE** — SF, NYC, Stockholm. That is not an obstacle, it is the
opening: **they cannot fill a remote role, and this is not a job application.** A
scoped remote contract is a different transaction from the one they are advertising,
and saying so removes the "he is in India" objection before it forms.

---

## 1. FurtherAI — `sg+hn@furtherai.com` — best fit on the board

Their posting: *"The hard problems: keeping an agent reliable across dozens of tool
calls; orchestration + **evals** + reliability on top of frontier models."* In
production at top-10 carriers, a16z and YC backed. Insurance documents, so an
invented figure has a direct cost.

> Subject: evals across dozens of tool calls — one specific idea
>
> Hi — your HN post names the hard problem as keeping an agent reliable across dozens
> of tool calls, plus orchestration, evals and reliability. That middle one is what I
> have spent my time on.
>
> The trap I hit, in case it is useful whether or not you reply: I started by having a
> model grade the agent's output. That puts the failure mode inside the measuring
> instrument — the grader hallucinates the grade. I rebuilt it as deterministic
> grading, regex and substring only, which forces you to write cases with checkable
> answers. It also made me score two things separately, because they fail
> independently: was the answer right, and did the pipeline actually do the work —
> did grounding fire, did the citation check fire. One score cannot tell "right" from
> "right by luck", and I had a run that was directionally right with every figure
> wrong.
>
> Writeup, with the numbers and what they do not prove:
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> Not applying — you are hiring onsite in SF and I am in India. What I am offering is
> **$400 fixed, one week: an eval set for one agent workflow you already run in
> production**, with the failure modes documented. If it is not useful when you read
> it, do not pay.
>
> If this is not a fit, no reply needed.
>
> Rushikesh

## 2. Tasklet — `andrew@tasklet.ai`

*"The AI platform companies use to run their business on agents... agents do the work
across your SaaS tools, APIs, browser, files, and internal systems."* Team of 12,
founded by Andrew Lee (Firebase).

> Subject: when a Tasklet agent is wrong, how do you find out?
>
> Hi Andrew — Tasklet describes agents doing real work across a company's SaaS tools,
> APIs and internal systems, on a schedule and in response to events. That is the
> setting where a wrong action is expensive, because nobody is watching at the moment
> it happens.
>
> The question I would want answered in your position: when the agent cannot verify
> something, what does it do? Most systems produce a plausible sentence and continue.
> I build the layer that makes it stop instead — grounding in sources actually
> fetched, arithmetic re-derived in code rather than trusted from the model, and every
> citation checked against the source text.
>
> Measured rather than asserted: a scored eval, graded by regex rather than by a
> model, because a model grader can hallucinate the grade.
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> You are hiring onsite in SF, so this is not an application. **$400 fixed, one week:
> an eval set for one agent path you already ship**, with the failure modes written
> down. If it is not useful when you read it, do not pay.
>
> No reply needed if this is not a fit.
>
> Rushikesh

## 3. River — `tarek@rivergtm.com`

*"Voice AI agents... talks with prospects in real time, answers hard questions, and
demos the product by actually controlling a browser while it speaks."* Sub-second
loop, several LLMs, live browser agent, in front of real buyers.

> Subject: the agent is wrong in front of a buyer — then what?
>
> Hi Tarek — your agent answers hard questions live, in front of real prospects, while
> driving a browser. Of all the places an LLM can be confidently wrong, that is the
> one with the shortest distance to a lost deal.
>
> I work on the part that decides what happens when it does not know: grounding in
> what was actually retrieved, arithmetic re-derived in code, citations checked
> against source text, and a scored eval graded deterministically rather than by
> another model, since a model grader can hallucinate the grade.
>
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> You are hiring founding engineers on-site in NYC and I am in India, so this is not
> an application. **$400 fixed, one week: a failure-case eval for one part of the live
> call path** — the questions where being wrong costs you the meeting. If it is not
> useful when you read it, do not pay.
>
> If not a fit, no reply needed.
>
> Rushikesh

## 4. DualEntry — `ivanc@dualentry.com` — REMOTE, and it is about numbers

*"The first AI-native ERP software... Day-One data migration."* $90M Series A,
Google/Lightspeed/Khosla. **REMOTE.** An AI-native ERP is arithmetic; a hallucinated
figure in accounting software is not a UX problem.

> Subject: an AI-native ERP is arithmetic — how is it checked?
>
> Hi Ivan — an AI-native ERP is the one product category where a hallucinated number
> is not a rough edge. Accounting output either reconciles or it does not.
>
> That is the specific thing I build: arithmetic re-derived deterministically in code
> instead of trusted from the model, every figure checked, and an answer whose sums do
> not add up capped regardless of how confident the prose is. Plus grounding and
> citation verification against source text, and a scored eval graded by regex rather
> than by a model — a model grader can hallucinate the grade.
>
> The concrete before and after: it used to invent "$0.25 per million tokens" and do
> arithmetic on that figure. Now it returns "could not verify a current figure".
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> **$400 fixed, one week: an arithmetic and grounding check harness for one workflow
> you already ship**, with failure cases documented. If it is not useful when you read
> it, do not pay. I am in India, and I saw you hire remote.
>
> No reply needed if this is not a fit.
>
> Rushikesh

## 5. Pango — `lukasz@pango.ai`

*"The world's first Agentic Operating System for e-commerce logistics."* Stockholm,
"cannot keep up with demand".

> Subject: agentic logistics — what happens on the uncertain calls?
>
> Hi Lukasz — an agentic OS for e-commerce logistics means agents making decisions
> about real shipments. Wrong there is not a bad answer, it is a parcel in the wrong
> country.
>
> I build the checking layer: grounding in sources actually fetched, arithmetic
> re-derived in code, citations verified against source text, and a scored eval graded
> deterministically rather than by another model, because a model grader can
> hallucinate the grade.
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> You are building the core team on-site in Stockholm, so this is not an application —
> I am in India, roughly 3.5 hours ahead of you. **$400 fixed, one week: an eval set
> for one agent decision path you already run**, with the failure modes written down.
> If it is not useful when you read it, do not pay.
>
> If this is not a fit, no reply needed.
>
> Rushikesh

## 6. Phonely — `recruiting@phonely.ai`

*"AI voice agents that automate phone calls for businesses."* YC S24, Series A.
Weaker address (`recruiting@`), so lowest priority of the six.

> Subject: what does a Phonely agent say when it does not know?
>
> Hi — Phonely's agents talk to a business's actual customers on the phone. A voice
> agent that invents an answer does it out loud, in real time, with no chance for
> anyone to catch it first.
>
> I work on what a system does at exactly that moment: grounding in retrieved sources,
> arithmetic re-derived in code, citations checked against source text, and a scored
> eval graded by regex rather than by a model — a model grader can hallucinate the
> grade. Baseline 15/16, then 15/15 after closing a hole that let volatile facts
> through ungrounded.
> https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> You are hiring onsite in SF and I am in India, so this is not an application.
> **$400 fixed, one week: an eval set for one call flow you already run**, focused on
> the questions where a confident wrong answer costs a customer. If it is not useful
> when you read it, do not pay.
>
> No reply needed if this is not a fit.
>
> Rushikesh

---

## What is deliberately consistent, and what is not

**Consistent:** the price ($400 fixed), the guarantee (do not pay if useless), the
explicit exit, the link, and the fact that it is not a job application. Those are the
offer, and the offer should not vary by target.

**Different in every message:** the opening, the specific failure named, and why it
costs *that* company something. **No message would make sense sent to a different
company** — which is the test of whether this is research or spam.

## After sending

**Seven messages out** including Atria. Then stop and wait. **No follow-ups before
2026-08-13.** If all seven go unanswered, that is a readable result about the offer
or the message — not about the volume, and the answer will not be to send seventy.
