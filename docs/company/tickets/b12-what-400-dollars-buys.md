# What the $400 actually buys — the reply-ready scope

`wayfinder:task` · **DRAFTED 2026-08-06** · triggered by [B11](b11-direct-outreach.md)

## Why this exists

Seven messages are out promising *"an eval set for one agent workflow you already
run, with the failure modes documented — $400 fixed, one week."* If anyone replies
asking what that means, improvising is how a warm reply goes cold. This is the page
that goes back within hours.

## The constraint that shapes everything

**Assume no production access.** No company hands a stranger access to a live agent,
and asking for it as the first move will end most conversations. **The deliverable
has to work without it**, and access — if offered — is an upgrade rather than a
prerequisite.

That gives three versions, in descending order of what they are willing to share:

| Their access level | What Rushi delivers |
|---|---|
| **A. They share ~30 real input/output pairs** | Full version: case set, runnable grader, **findings doc showing which cases their current system fails, with their own outputs as evidence** |
| **B. Public surface only** (demo, free tier, docs) | Case set + grader, run against the public surface. Findings are real but narrower |
| **C. Nothing shareable** (confidential/regulated) | Case set + grader written from their docs and stated behaviour. **They run it themselves**; he never sees their data. Least proof, lowest friction, and the only option for insurance or healthcare |

**C is not the booby prize.** For FurtherAI (insurance carriers) and Atria
(healthcare) it may be the *only* legally workable option, and a grader they run
in-house is still a thing they do not currently have.

## The deliverable, concretely

Four artefacts. Named, so there is no argument later about what "an eval set" meant.

**1. `cases.yaml` — the case set (20–40 cases)**
Each case: the input, `must_appear`, `must_not_appear`, and *why this case exists* —
which real failure it is hunting. Written for their workflow, not generic.

**2. `grade.py` — a runnable deterministic grader**
Regex and substring matching only. **No model in the grading path**, for the reason
in the writeup: a model grader can hallucinate the grade. Runs offline, no API key
required, prints a score.

**3. Two scores, not one**
- **CORRECTNESS** — was the output right?
- **PROCESS** — did the system do the work, or get there by luck? (did it ground, did
  it cite, did it refuse when it should have)

One number cannot distinguish "right" from "right by accident", which is the failure
that motivated the whole approach.

**4. `findings.md` — what broke**
The cases their system fails, the actual output, and the failure *category*. This is
the part with commercial value: not "your accuracy is 82%" but "here are six inputs
where it states something it cannot support, and here is what it said."

## What is explicitly NOT included at $400

Stated up front, because scope disputes kill first engagements.

- **Not** fixing the failures. This finds and measures them; fixing is separate work.
- **Not** an eval platform, dashboard or CI integration.
- **Not** more than one workflow. One agent path, deliberately.
- **Not** a model-graded eval, at any price.
- **Not** load, latency or cost benchmarking.

## The three scoping questions

Three, not ten. More than three reads as a questionnaire and stalls the reply.

1. **Which single workflow?** Naming one is the whole scoping act — "the agent" is not
   a scope, "the agent path that answers pricing questions on inbound calls" is.
2. **Can you share ~30 real input/output pairs?** If not, is there a public surface I
   can use, or would you rather run the grader in-house and never send me anything?
   *(This is the A/B/C fork, asked without making it sound like a negotiation.)*
3. **What does "wrong" actually cost here?** A bad answer, a wrong action, or a
   compliance problem? Grading for the wrong failure produces a useless score.

## Reply template — ready to send

> Thanks for coming back.
>
> Here is exactly what $400 buys, so there is no ambiguity later.
>
> **You get four things:** a set of 20–40 eval cases written for one of your agent
> paths, each with what must and must not appear in a correct output and a note on
> which real failure it is hunting; a runnable grader that is deterministic — regex
> and substring only, no model in the grading path, because a model grader can
> hallucinate the grade; two separate scores, correctness and process, because
> "right" and "right by luck" are different results and one number cannot tell them
> apart; and a findings document listing the cases your system currently fails, with
> the actual outputs.
>
> **What I need from you is smaller than you might expect.** Ideally about 30 real
> input/output pairs from one workflow. If that is not shareable — and for regulated
> data it often is not — I can work from your public surface, or write the cases and
> grader from your docs and have you run it in-house so nothing leaves your side. All
> three work.
>
> **Not included at this price:** fixing what it finds, any dashboard or CI
> integration, or more than one workflow. This measures; fixing is separate.
>
> **Three questions and I can start:**
> 1. Which single agent path?
> 2. Can you share sample input/output pairs, or should I work from the public
>    surface, or would you rather run it in-house?
> 3. When the agent is wrong there, what does it actually cost you — a bad answer, a
>    wrong action, or a compliance issue?
>
> One week from your answers. If it is not useful when you read it, do not pay.
>
> Rushikesh

## Honest risks, recorded

- **One week is an estimate, not a measured figure.** He has built an eval for his
  own system, never for a third party's. Version C is the fastest; version A depends
  on how messy their data is.
- **The offer says "one week from your answers"**, not from the reply. That distinction
  matters and is deliberate in the wording.
- **Version C means he never sees their outputs**, so `findings.md` becomes something
  *they* generate by running the grader. The reply says so rather than discovering it
  mid-engagement.
- **Payment is still unsolved.** No bank account exists. This spec converts a reply
  into an engagement; it does not convert an engagement into money.
