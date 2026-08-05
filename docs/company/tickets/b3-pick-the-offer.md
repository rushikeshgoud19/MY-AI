# Pick ONE offer: one buyer, one problem, one price

`wayfinder:grilling` (HITL) · **RESOLVED 2026-08-05 — approved by Rushi**

## Question

The failure mode of every AI automation agency is being a generalist who can build
anything and is therefore chosen for nothing. Pick:

- ONE buyer, described specifically enough to go and find fifty of them.
- ONE problem they already pay to solve, badly.
- ONE deliverable with a fixed scope and a fixed price.
- The reason THIS is defensible — what does a grounded, self-checking tribunal do
  here that a competitor with n8n templates cannot?

A candidate to argue *against*, not for: research and monitoring work where the
output has to be trustworthy — competitor and price tracking, supplier checks,
inbound lead qualification. It fits the asset (grounding, citation checking,
refusing to invent) and it fits the existing stack. It may also be a market that
does not pay, or one where buyers cannot tell a checked answer from a confident
one. B2 decides that, not enthusiasm.

## Inputs from B1 (2026-08-05)

- **The buyer is Indian and domestic**, paying in rupees over UPI. Not "a business";
  an Indian SMB. Price in ₹, not $.
- **Corporate clients withhold 10% TDS** under s.194J above ₹30,000 per contract or
  ₹1 lakh/year. A ₹10,000 invoice to a company yields ₹9,000 now and ₹1,000 at ITR.
  Individuals and small unregistered clients generally do not deduct. Affects both
  the price point and which kind of client is least friction for #1.
- **Ceiling before this needs restructuring:** ₹20 lakh/year turnover (GST) or
  ~₹50,000/month inflow (current account). Customer #1 is far below both, so the
  offer does not need to be built for scale it will not reach.

## Requires Rushi

Two things Claude cannot decide, because they are his time and his temperament:

- How many hours a week can he actually give this, honestly, alongside everything
  else?
- Does he want customers he has to talk to, or a product that sells without him?

Those lead to completely different offers. A service pays more per unit and needs
conversations; a product needs volume and needs none. Picking wrong here wastes
every ticket after it.

---

## Rushi's answers, 2026-08-05

- **Hours per week: 1.**
- **Service or product: "both."**

### On "1 hour"

This is the most consequential input received so far and it constrains harder than
it looks. The constraint is not the quantity, it is *which* hour. Four things cannot
be delegated under the map's Notes — opening accounts, pressing send, signing, and
talking to a customer. Those are irreducible. So Rushi's hour must be spent almost
entirely on them, and **any offer requiring back-and-forth with a buyer is
eliminated on arithmetic**, not on preference.

### On "both" — not available, but the conflict resolves better than expected

Answering "both" to a ticket whose entire job is to force one choice is the widening
failure mode the map warns about, and it is refused as stated. A product needs
volume, which needs marketing spend or time — neither exists at 1 hr/week. A service
needs conversations — which is the whole hour.

**But there is one shape with properties of each, and it is what 1 hr/week points at
anyway: a fixed-scope, fixed-price listing on a marketplace where buyers already
arrive.** Productised in that scope and price are fixed and no negotiation happens;
a service in that each order is delivered work. This is not a compromise offered to
avoid saying no — it is what the hours constraint independently selects for. It also
removes outreach, which was the other thing 1 hr/week could not fund.

## Recommendation — ONE offer

**A counterparty due-diligence report where every claim is linked to the page it
came from, and the report states plainly what it could NOT verify.**

- **ONE buyer:** someone about to send money or goods to a company they have not met
  — small importers, agencies vetting a subcontractor, anyone doing a first
  transaction with an unfamiliar supplier.
- **ONE problem:** they cannot tell whether the company on the other side is real,
  and the cost of being wrong is the whole transaction.
- **ONE deliverable:** a fixed-scope report on one named company — existence,
  registration, directors, stated address, online footprint — every line carrying
  the source it came from, and an explicit *"could not verify"* section.
- **Price:** the observed band for this category is $10–$120, with the two deepest
  listings at $80 and $120 (B2). Entry near the top of that band is the position to
  argue for, since the differentiator is depth of checking. **Not decided here** —
  pricing without a live listing to test against would be a guess.

### Why this one and not the higher-ceiling option

Market/competitor research showed a better ceiling ($350 vs $120). It is the wrong
choice, for one reason: **"could not verify" is a defect there and an asset here.**
A buyer who ordered a market-size estimate does not want "unknown". A buyer checking
a supplier wants exactly that line, because a confident report that says a
fraudulent company is legitimate is the outcome they are paying to avoid. Due
diligence is the only category found where the tribunal's defining behaviour is the
thing being bought rather than a quirk to be tolerated.

### Why it is defensible against someone with n8n templates

An n8n template can fetch pages and format a report. What it cannot do is decline to
assert. Every competitor's output is fluent and confident whether or not the
underlying page said anything; that is the failure this repo spent a week removing.
The deliverable here is auditable line by line — the buyer can click any claim
through to its source — and the "could not verify" section is proof the checking
actually ran rather than being asserted in the sales copy.

### Risks, stated rather than buried

- **Data access is unproven.** Whether the tribunal can reach the registries this
  needs — Indian MCA is public, other jurisdictions vary — has **not been tested**.
  If it cannot, the offer narrows to Indian companies or collapses. This is the
  first thing B5 must establish.
- **The price band is from listings, not completed orders.** B2's sources are
  blocked; $10–$120 is what sellers ask, not verified revenue.
- **This category sits near KYC and background checks**, which carry real
  obligations depending on jurisdiction and use. The report must be positioned as
  open-source research with sources shown, never as a compliance or credit opinion,
  and never about private individuals. Feeds B7.
- **Marketplace selling needs an account Rushi must create himself**, and payout
  needs the bank account. Neither blocks B5.

### Consequence for B1

This points at a marketplace whose buyers and currency are international, which is
the tension B2 flagged. It does not reopen B1 yet — B1's mechanics hold, and the
bank account is needed either way — but the **domestic-first** conclusion is now
under real pressure and should be revisited once there is a live listing.

**Status: recommended, not decided. Needs Rushi's yes or no.**
