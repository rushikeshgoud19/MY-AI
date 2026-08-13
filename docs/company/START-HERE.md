# Groundtruth — start here

Paste the block at the bottom into a fresh Claude Code session to begin. Everything
above it is context for you, Rushi, not for the agent.

---

## What this is

An attempt to earn money by selling automation whose output can be audited.
Destination, deliberately small: **one customer has paid for one automation and it
works.** Not a company, not an audience, not a pipeline. One completed
money-for-value loop, so every assumption gets tested by somebody willing to pay.

The map is `docs/company/groundtruth.md`. Tickets are in `docs/company/tickets/`.

## Why the offer is not "AI automation"

Everyone sells that, and they all sell it with the same demo: a confident answer.
What exists here that they do not have is in `docs/wayfinder/` — a multi-agent
tribunal that:

- grounds its answers in pages it actually fetched, not search-result blurb;
- checks its own arithmetic deterministically and caps the score of any answer whose
  sums do not add up;
- checks every citation against the material and flags invented ones;
- and says **"could not verify a current figure"** instead of inventing one.

That last behaviour is the product. It is also, measurably, the thing that took a
week to build — the eval went from a panel that invented €0.30 (25x wrong) to one
that refuses to quote a price it cannot source. Anyone can claim it. There is a
scored eval here that demonstrates it.

## The division of labour — read this before anything else

Claude does the work. **You are the principal.**

Claude will: research, build, write every asset, draft every message, track and
report daily.

Claude will not: create accounts, enter payment or personal details, sign anything,
receive money, or send a message to a real person without you approving that
specific batch.

This is not the agent being awkward. It is the line where "my AI did it" stops
being a defence, and it is also the arrangement that keeps the business yours.
Expect to be handed checklists. Doing those is your job and nobody can do it for
you.

## Order of work, and why

1. **Can you actually get paid?** (`b1-can-rushi-get-paid.md`) — everything else is
   wasted if this fails. You have no credit card. Receiving money in India as a
   student is a different problem from spending it, and international vs domestic
   are different compliance paths.
2. **Is Clustly a viable first channel?** (`b8-clustly-as-first-channel.md`) — cheap
   to check, and if it works it removes outreach entirely and answers (1) too.
   If it fails, one afternoon lost.
3. **Build the Company section + daily log + memory** (`b4`) — takeable in parallel,
   depends on nothing. This is where the daily report you asked for lives.
4. **What do people actually pay for** (`b2`) → **pick ONE offer** (`b3`) →
   **build the demo** (`b5`) → **the outreach motion** (`b6`).
5. **Legal and invoicing** (`b7`) — before a customer, not after.

## What only you can do

- Open any account; upload any document; accept any terms.
- Decide how many hours a week this actually gets. Be honest — the offer chosen for
  four hours a week is different from the one chosen for twenty.
- Decide whether you want customers you talk to, or a product that sells without
  you. These lead to completely different businesses.
- Press send on every outbound message.
- Say no when the plan drifts into something you would not put your name on.

## What nobody can promise you

That this earns money, or when. The honest version: most first attempts do not
reach a paying customer, and the ones that do usually get there by narrowing the
offer until it is almost embarrassingly specific. The value of the map is that it
fails cheaply and in the right order — the payment question before the product, the
product before the outreach.

Do not let anyone, including Claude, produce motion that feels like progress. A
landing page, a logo and a brand are not progress. Money in the account is.

---

## Paste this into a new session

The full version is `docs/company/MEGAPROMPT.md` - use that one. The short form
below is a fallback if you want something minimal.

```
Read docs/company/groundtruth.md and docs/company/START-HERE.md in the my Ai repo,
then take the first frontier ticket in docs/company/tickets/.

Rules for this effort, from the map Notes:
- You do the work; I am the principal. You never create accounts, enter payment or
  personal details, sign anything, receive money, or send a message to a real person
  without my approval of that specific batch.
- Every factual claim names its source. No price, market size or statistic without a
  link. This company exists because we spent a week teaching a tribunal not to invent
  numbers - do not start now.
- No earnings promises, in the assets or to me.
- One ticket per session. Record the resolution in the ticket, update the map's
  Decisions-so-far, and write a dated entry in docs/company/log/.
- If a ticket turns out to sit beyond the destination, rule it out of scope rather
  than quietly doing it.

Start by telling me which ticket you are taking and why, then work it.
```
