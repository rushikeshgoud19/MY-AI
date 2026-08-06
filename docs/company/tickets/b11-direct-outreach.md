# The direct outreach motion — Claude drafts, Rushi sends

`wayfinder:task` (HITL) · **OPEN — first batch drafted 2026-08-06**

## Why this ticket

All nine marketplaces are closed ([B6](b6-outreach-rushi-runs.md),
[B10](b10-build-what-rushi-builds.md)): the gated ones reject him, the ungated ones
have no buyers. Rushi chose direct outreach and asked whether Claude can handle the
email.

**Answer: everything except two things.** Claude finds targets, researches each,
drafts each message, drafts every reply, and tracks the pipeline. Claude does **not**
hold credentials, press send, or read the inbox. Rushi sends; he pastes replies back
in. That is his own rule and it is right — a cold email that lands badly lands on
*his* name.

## Targeting rule — no scraped lists, ever

**A live job posting is a public, explicit statement of need from an organisation
with budget, published to attract contact.** That is the legitimate version of the
"engagement is a hand raise" insight — no scraping, no data brokers, no enrichment
waterfall, and no invented personas.

**Source: the HN "Who is hiring?" monthly thread**
([August 2026](https://news.ycombinator.com/item?id=49156683), 178 postings).
Public, current, and companies post there specifically to be contacted.

Filtered: mentions LLM / eval / RAG / agentic / AI engineering, **and** does not
restrict to US-only. **10 of 178 survive.**

## The honest problem with these targets

**Most are full-time employment, not contract work.** Applying to them is a job hunt,
which is a different destination from the one this map names.

**But there is a real angle that keeps it a customer relationship, and it is how
contractors actually get in:**

> A company that has been advertising a senior AI role for weeks has a problem *now*
> and a hire who starts in three months. A small, scoped, paid piece of work is worth
> more to them than another CV.

So the message is **not** an application. It is: *here is a specific thing I noticed,
here is a small scoped piece I can do now, here is the work that shows I can.*

## First batch — 2 messages, not 20

Volume discipline is deliberate. Ten researched messages beat a hundred generic ones,
and the map forbids spam volume. **Two, then wait for signal before writing more.**

### Target 1 — Railway (`railway.com/careers`)

Posting: *"Infra Eng-Storage, Product Eng (full-stack), Infra Eng-Observability,
Infra Eng-General | REMOTE (Worldwide)"* — and the pitch itself is agent-shaped:
*"Do you wish you could just tell Claude to manage your infra, and it would just
work?"*

**Angle:** they are building agent-driven infrastructure. Agents acting on infra is
precisely where a confidently-wrong answer is expensive.

> Subject: the failure mode in "just tell Claude to manage your infra"
>
> Hi — your Who Is Hiring post asks whether I dream of telling Claude to manage my
> infra. I have been building the unglamorous half of that: what the agent does when
> it does **not** know.
>
> I built a multi-agent system that grounds answers in pages it actually fetched,
> re-derives every figure in code rather than trusting the model, and checks each
> citation against the source text. It has a scored eval — 15 cases, graded by regex,
> deliberately **not** by a model, because grading with an LLM puts the failure mode
> inside the measuring instrument.
>
> The change that mattered: it used to invent "$0.25 per million tokens" and do
> arithmetic on it. Now it returns "could not verify a current figure."
>
> Writeup: https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> I am not applying for the full-time roles — I am in India and I would guess that is
> a complication. What I am asking is whether a small paid scoped piece is useful:
> an eval harness for one agent path you already ship, with the failure cases written
> down. If it is not useful, no reply needed.
>
> Rushikesh

### Target 2 — Atria (`Global Remote (almost anywhere)`)

Posting: *"Product Engineer roles (across levels) and a **Staff SWE, Agentic AI**"*,
preventative healthcare.

**Angle:** healthcare plus agents is the highest-stakes possible place for an
invented figure. "Could not verify" is not a limitation there — it is a requirement.

> Subject: agentic AI in healthcare — what does yours do when it isn't sure?
>
> Hi — I saw you are hiring a Staff SWE for Agentic AI, and that you are open to
> almost anywhere.
>
> One question, asked as someone who has spent a while on it rather than as a pitch:
> when your agent cannot verify something, what does it output? In most systems the
> honest answer is "a plausible sentence", and in healthcare that is the expensive
> failure.
>
> I have built the checking layer for this — grounding in fetched sources,
> deterministic arithmetic re-derivation, citation verification against source text,
> and a scored eval graded by regex rather than by a model, because an LLM grader can
> hallucinate the grade. Baseline 15/16, 15/15 after fixing a routing hole that let
> volatile facts through ungrounded.
>
> Writeup: https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> I am in India, so I am not a candidate for the staff role. I am asking whether a
> scoped piece of contract work is useful — for example, an eval set for one agent
> workflow you already run, with the failure modes documented. If not, no reply
> needed.
>
> Rushikesh

## REVISED 2026-08-06 — v1 was weak, here is why

Rushi asked for a recheck before sending. Reread both and found three faults, all
real.

**1. Both apologised for existing.** Railway: *"I'd guess that's a complication."*
Atria: *"I'm in India, so I'm not a candidate."* The first invites them to agree he
is a problem. **The second is also factually wrong** — Atria's posting says
*"Global Remote (almost anywhere)"*, so he pre-rejected himself against their own
stated policy. And Railway's careers page says they are **"a team of 39 across 16
countries"**. Distance was never the objection; v1 invented it and then conceded it.

**2. The ask was vague.** *"A small paid scoped piece"* gives nobody anything to say
yes to. Vague asks get vague non-answers. v2 names the deliverable, the timeframe
and the price.

**3. Neither showed he had looked at their product.** v2 cites the **"Railway for
Agents"** section of their docs, and Atria's actual domain.

Also cut roughly a third of the length. Cold emails are skimmed.

### Target 1 — Railway · REMOTE (Worldwide) · `railway.com/careers`

> Subject: what does "Railway for Agents" do when the agent is wrong?
>
> Hi — I read the Railway for Agents section of your docs. Agents acting on infra is
> the place where a confidently wrong answer actually costs something, and that is
> the problem I have spent the last while on.
>
> I built a multi-agent system that grounds answers in pages it actually fetched,
> re-derives every figure in code instead of trusting the model, and checks each
> citation against the source text. It has a scored eval — 15 cases, graded by regex,
> deliberately not by a model, because an LLM grader can hallucinate the grade.
>
> It used to invent "$0.25 per million tokens" and do arithmetic on it. Now it
> returns "could not verify a current figure."
>
> Writeup: https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> Concretely: **$400, one week, for an eval harness on one agent path you already
> ship** — a case set that catches your real failure modes, deterministic grading,
> and the failures written down. If it is not useful when you read it, do not pay.
>
> I am in India; I saw you are 39 people across 16 countries so I assume that is
> workable. If this is not a fit, no reply needed.
>
> Rushikesh

### Target 2 — Atria · Global Remote (almost anywhere)

> Subject: what does your agent output when it cannot verify something?
>
> Hi — I saw you are hiring a Staff SWE for Agentic AI, and that you hire almost
> anywhere.
>
> A genuine question rather than a pitch: when your agent cannot verify something,
> what does it output? In most systems the honest answer is "a plausible sentence".
> In preventative healthcare that is the expensive failure, because the output reads
> exactly as confident as a correct one.
>
> I build the checking layer for this — grounding in fetched sources, deterministic
> arithmetic re-derivation, citation verification against source text, and a scored
> eval graded by regex rather than by a model, because a model grader can hallucinate
> the grade. Baseline 15/16, then 15/15 after closing a routing hole that let volatile
> facts through ungrounded.
>
> Writeup: https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de
>
> Concretely: **$400, one week, for an eval set on one agent workflow you already
> run**, with the failure modes documented. If it is not useful when you read it, do
> not pay.
>
> I am in India and available in your mornings. If this is not a fit, no reply needed.
>
> Rushikesh

### On the price and the guarantee

**$400 fixed**, not hourly. Contract genAI rates run $42-105/hr
([Consultadd](https://consultadd.com/blog/how-to-hire-generative-ai-engineers)), but
those attach to demonstrated production experience. A fixed price on a defined
deliverable is easier to approve than an hourly rate from someone unknown, and it
caps their risk without pretending to a seniority he does not have.

**"If it is not useful, do not pay"** is risk reversal, not free work. It is not an
earnings promise and it promises them nothing about outcomes — only that he will not
invoice for something they judge worthless. For a first customer with no track
record it is the strongest honest lever available.

## Rules held in both drafts

- **No earnings promise**, to them or about them.
- **No invented experience.** Every claim maps to code in this repo.
- **Location stated as a fact, not an apology.**
- **An explicit exit** — "if not a fit, no reply needed."
- **A concrete ask** — named deliverable, timeframe and price.

## Published 2026-08-06

The case study is live as a **public gist** on his own GitHub account
(`rushikeshgoud19`), authorised explicitly by him: *"you have my github access so go
for it man dont worry about it."*

**https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de**

Verified public and rendering (HTTP 200, raw content readable logged-out). Both
messages now carry a real link.

**Deliberately a gist, not the repo.** `my Ai` holds `config.json` with API keys; it
must not be linked or made public.

**One thing he has not done, and it is his to do:** confirm the technical claims are
accurate. The numbers come from his own `docs/wayfinder/orchestra-accuracy.md`, but
they are being published under his name. If anything is overstated, one command
removes it:

```
gh gist delete 8c2dd391d5545b4030d10f382d7ec0de
```

## Blocked on Rushi

1. **Read both messages.** Change anything that does not sound like him — they are
   drafts, not scripts.
2. **Two links needed before sending:** the case study and the code. Neither is
   public yet. **The case study cannot go in an email until it is published
   somewhere he controls** — that is the [B10](b10-build-what-rushi-builds.md)
   publishing decision, and it now blocks this ticket.
3. **He sends them**, from his own address.
4. **He pastes any reply back**, and Claude drafts the response.

## Then stop and wait

Two messages, then nothing until there is signal. If both are ignored, that is
information about the message or the target, and the next batch changes one variable
— not the volume.
