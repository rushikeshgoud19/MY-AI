# The plan — from here to one paid customer

Written 2026-08-05. **Revised 2026-08-06 — Fiverr dropped, so Phase 1 is void and
the plan now has a hole where its channel used to be.**

**State: revenue ₹0. Nothing published. Zero customers. No channel.**

## Read this before the phases

Assets are not the problem. There is an offer, three sample reports, tested register
access in three countries, listing copy, profile copy, and payment mechanics.

**Not one of them has been seen by a single person who might pay.**

That is the whole situation. Every hour spent making the samples better is an hour
not spent putting one in front of a buyer, and the map's own failure-mode list names
this exactly: *"if a week passes with no contact with a real potential buyer,
something is wrong."* One day in, so not yet a failure — but the shape of it is
visible, and the next move has to be contact, not craft.

**The bottleneck is the channel, and the channel is undecided.** Everything below
Phase 1 is polish until that is fixed.

---

## What exists already

| Asset | Where |
|---|---|
| The offer | [b3](tickets/b3-pick-the-offer.md) — company verification, sources on every line, explicit "could not verify" |
| Two sample reports | [sample 1](demo/sample-report.md) (struck off), [sample 2](demo/sample-report-2.md) (live, filings stale) |
| Listing copy | [b6](tickets/b6-outreach-rushi-runs.md) — title, description, FAQ, three tiers |
| Profile copy | [b6](tickets/b6-outreach-rushi-runs.md) |
| Tested register access | UK Companies House, Australian ABR — both primary. India via mirrors |
| Payment mechanics | [b1](tickets/b1-can-rushi-get-paid.md) |
| Fiverr seller account | Created by Rushi — handle `shadow_kuro` |

---

## Phase 1 — VOID. Pick a channel.

Fiverr was dropped on 2026-08-06. The checklist below is kept only because it
becomes valid again the moment a marketplace is chosen — the copy is about the
offer, not about Fiverr, so it ports.

**The live question is which of three routes to take.** They are genuinely
different, and the right one depends on why Fiverr was rejected — which is
[asked and unanswered](tickets/b6-outreach-rushi-runs.md).

| Route | What it costs | What it needs from Rushi | Honest read |
|---|---|---|---|
| **A. Another marketplace** (Upwork, PeoplePerHour, Freelancer) | A cut of every sale; all of them KYC sellers before payout | Account, ID, publish | Only sensible if the Fiverr objection was the *platform*. **If it was the zero-review problem, this changes nothing** — every marketplace ranks on reputation |
| **B. Direct outreach** | No cut. Costs his time and mine | He sends every message, having read it | The only route that works with no reviews. Slowest to first rupee, and constrained by the no-spam rules — ten researched messages, not a hundred |
| **C. Give one report away first** | One session | He picks the recipient and sends it | Not really a channel — a way to get the first real reaction. Strongest signal per unit effort, and it feeds [B2](tickets/b2-what-people-pay-for.md), which desk research could never finish |

**Recommendation: C, then B.** Not because A is bad, but because nobody has ever
reacted to this offer, and a channel decision made before a single buyer reaction is
a guess dressed as a plan. One free report to one real business — someone who
actually deals with overseas suppliers — answers more than another week of research.

If he wants A, that is fine and I will do it properly; the copy is ready and it is
the fastest route to *listed*. It is just not the fastest route to *learning*.

## Phase 1 (kept, for whenever a marketplace is chosen)

**Rushi. About forty minutes. Nothing else in this plan can start until it is done.**

| # | Action | Why it is his |
|---|---|---|
| 1 | **Read Fiverr's prohibited-services list.** Confirm company due-diligence research is permitted and note any wording about investigations or personal data | Claude has attempted this five times — WebFetch, browser, help centre — and gets HTTP 403 every time. **Publishing a gig in a sensitive category on a secondhand summary of the rules is not acceptable.** He can read it in two minutes |
| 2 | **Fix the profession field** — currently "Agentic workflows", which does not match the offer | His account |
| 3 | **Paste the About and Skills copy.** Leave work experience, education and certifications empty | An empty field beats a false one |
| 4 | **Create the gig** from the listing copy. Title, description, FAQ, three tiers at $25 / $60 / $110 | Publishing |
| 5 | **Attach the two sample reports** as gig gallery items — after deciding the public-use question below | Publishing |
| 6 | **Complete ID verification** — government ID plus a live selfie, required of sellers | His identity |
| 7 | **Open the savings account** (see [b1](tickets/b1-can-rushi-get-paid.md)) and connect payout | His identity and money |

### The one decision blocking step 5

Both sample reports name real companies with real findings — one struck off, one
with filings three years stale. Three options:

1. **Publish as-is.** The facts are public register data and the reports are careful.
   Reputational risk to the named companies is real but small.
2. **Redact the names**, keeping the structure and findings. Weaker as proof.
3. **Rebuild both on companies where the finding is neutral.** Safest, costs a
   session, and loses the two best demonstrations produced so far.

**Recommendation: option 1 for the UK sample, option 3 for India.** UK Companies
House data is published by the government for exactly this purpose. The Indian
reports rest on third-party mirrors, which is a weaker footing for a public claim
about a specific company. *Note: the UK sample does not exist yet — see Phase 2.*

---

## Phase 2 — Claude's work

1. ~~A UK sample report.~~ **Done** — [sample 3](demo/sample-report-3-uk.md), and it
   is the strongest asset produced. "Active" on a company that has never filed
   accounts in seven years.
2. **Wire the report to `orchestra.py`.** **Blocked on Rushi's decision about API
   keys** — the `config.json` permission prompt was declined and has not been
   retried. Worth saying plainly: **all three samples were assembled by hand, so the
   engine that is supposed to be the product has not yet produced a deliverable.**
   Until that changes, what is being sold is a method, not a machine.
3. **A delivery template.** Real, but it optimises a process that has never run once.
   Deliberately deferred until there is an order to deliver.
4. **Turnaround measurement.** Same — cannot honestly measure a process with no
   customer.

**Items 3 and 4 are parked on purpose.** Both are the kind of tidy preparation that
feels productive and moves nothing. They become urgent the day an order arrives and
not before.

Which leaves item 2 as the only genuinely useful thing Claude can do without a
decision — and it needs one.

---

## Phase 3 — an order arrives

1. Buyer orders and states a company. **Fiverr holds the money.**
2. Claude runs the check and drafts the report and any buyer messages.
3. **Rushi reads and sends. Every time, without exception.** Claude never holds
   Fiverr credentials and never messages a buyer.
4. Deliver inside the stated turnaround.
5. **If the register cannot be reached — say so and refund.** A report of blanks
   destroys the one thing being sold.

**Target: reply to any buyer message inside 12 hours.** Fiverr shows response time
to buyers, and a slow first reply costs the order.

---

## Phase 4 — getting paid, and the paperwork

Selling through a marketplace **collapses most of** [b7](tickets/b7-legal-and-invoicing.md):

- **No invoice to write.** Fiverr bills the buyer and reports earnings to the seller.
  The invoice format researched in B1 matters only for direct clients, which this
  is not.
- **No contract to draft.** The gig description plus Fiverr's terms are the scope of
  work.
- **No GST.** Threshold is ₹20 lakh of services turnover; this is nowhere near it.
- **No business registration.** Sole proprietor by default.

What genuinely remains:

| Item | Status |
|---|---|
| Money must arrive through banking channels, not crypto | Satisfied — Payoneer or bank transfer. This is what made Clustly illegal and Fiverr fine |
| Export-of-services documentation (FIRA) | **Open.** Payoneer provides documentation but does not auto-issue FIRA; Skydo and Winvesta do. Matters at volume, not for order #1 |
| Foreign income declared on the ITR | **Open.** Rushi's, at filing time |
| Anything student-specific — scholarship or institutional conditions on earning | **Unknown, and only he can check** |

---

## The tripwire

Set now, because a plan without a stopping rule is a plan to keep going forever.

> **If the gig is live for 30 days with zero orders, the listing failed — not the
> offer.**

At that point stop editing copy and do the thing desk research could never replace:
**talk to two or three real buyers.** [B2](tickets/b2-what-people-pay-for.md) is
still only partially answered — Fiverr, Upwork and Reddit were all blocked — and the
whole price band rests on *listed* competitor prices, not verified completed orders.
That gap gets closed by a person, not by more searching.

Secondary tripwire: **if orders arrive but buyers dispute the "could not verify"
sections**, the premise is wrong and B3 reopens.

---

## What could still kill this

Stated plainly rather than buried.

1. **Zero reviews against sellers with 400–500.** The largest risk and no copy fixes
   it. The sample reports are the only counterweight.
2. **Fiverr's policy may prohibit the category.** Unverified — see Phase 1, step 1.
3. **The Indian data is mirrors, not the primary source.** MCA returns 403. UK and
   Australia do not have this problem, which is a reason to lead with them.
4. **The price band is unverified.** $10–$120 is what competitors *list*, not what
   buyers *paid*.
5. **Nothing has run through the tribunal yet.** Both samples were assembled by hand.
   The engine that is supposed to be the product has not produced a deliverable.

---

## The honest summary — revised 2026-08-06

There is an offer, tested register access in three countries, **three** sample
reports, listing copy, profile copy and payment mechanics. There is **no channel, no
listing, no buyer, and no money.**

Two things are true at once and both need saying:

1. **A day of work produced real assets**, and the UK sample is genuinely good — it
   demonstrates the product's whole argument on a live company in one line.
2. **The asset pile is now ahead of the evidence.** Nobody outside this repo has
   seen any of it. Building a fourth sample, a delivery template or a turnaround
   metric would all *feel* like progress and would all be the failure mode.

**The next real step is a decision, not a document**, and there are only two open:

- **Which channel** — A, B or C above.
- **The API keys**, if `orchestra.py` is to produce a report rather than a person.

Until one of those moves, the correct amount of further building is close to zero.
