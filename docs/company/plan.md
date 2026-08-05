# The plan — from here to one paid customer

Written 2026-08-05. Everything in it is decided; nothing in it is done.

**State: revenue ₹0. Nothing published. Zero customers.** The plan is short on
purpose — most of it is one person doing about forty minutes of work.

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

## Phase 1 — get listed

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

## Phase 2 — the things Claude does while waiting

**No dependency on Rushi. Can start immediately.**

1. **A UK sample report.** UK Companies House is the primary source, the data is
   richer, and the "confirmation statement overdue" check is directly available
   rather than derived. This is likely to become the lead sample.
2. **Wire the report to `orchestra.py`** so a run produces it rather than a person
   assembling it by hand. **Needs Rushi's decision on API keys** — the `config.json`
   permission prompt was declined and has not been retried.
3. **A delivery template** — one file, fill in the company, so an order that arrives
   at 2am is fulfilled the same way every time.
4. **Turnaround measurement.** How long a report actually takes end to end, so the
   gig promises a delivery time that can be met rather than one that sounds good.

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

## The honest summary

There is an offer, tested data access in three countries, two sample reports,
listing copy and profile copy. There is **no listing, no buyer, and no money.**

Everything in Phase 2 is Claude's and starts now. Everything that turns this into
revenue is in Phase 1, and it is forty minutes of one person's time.
