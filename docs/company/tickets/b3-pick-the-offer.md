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
*(Approved by Rushi 2026-08-05.)*

---

## Challenge to this offer — 2026-08-06. The UK half is much weaker than claimed.

Went looking for real people asking about supplier verification, to unblock Route C
without waiting on Rushi for a name. **Found no live prospects** — the search
returned supplier-vetting SEO content and old Quora threads, not identifiable people
with a current problem. That failed.

**But it surfaced the strongest objection to this offer, stated by the market itself:**

> *"It is incredibly easy to register a new company... very cheap and easy to set up
> a UK limited company and sadly is often done so in order to commit scams."*
> *"Registration tells you nothing about the company's current finances, its
> complaints record or what it actually does."*
> — [Quora, on Companies House](https://www.quora.com/If-a-company-is-registered-at-Companies-House-does-it-mean-the-company-is-100-legit)

### Then I checked our own UK sample against the free public page. It does not survive.

The headline finding in [sample 3](../demo/sample-report-3-uk.md) — "Active, but a
proposal to strike off, accounts overdue five years" — is **printed on the free
Companies House page in plain sight.** Verified in the raw HTML: the string `Warning`
appears twice, `overdue` four times, `strike off` once. A visitor sees:

> `Company status Active - Active proposal to strike off ... Warning Accounts
> overdue First accounts made up to 31 May 2020 due by 16 May 2021 Warning
> Confirmation statement...`

**We were not revealing hidden data. We were reading a public page aloud.** Anyone
can do it in thirty seconds, free, without knowing anything.

Against B2's own price evidence — *checking sold as checking clears $5* — that makes
the UK version of this offer a **$5 service being priced at $60**. Australia has the
same problem: ABN Lookup is free, public and equally legible.

### Where the friction — and therefore the willingness to pay — actually is

**India.** And it is the one place the earlier reasoning got right before it was
widened:

- `mca.gov.in` returns **HTTP 403** and is genuinely hard to use.
- The usable data sits on third-party mirrors a foreign buyer has no reason to know
  exist, and those mirrors **paywall** filing history and financials.
- CIN format, ROC structure and AGM conventions are unfamiliar to a non-Indian buyer.
- Nothing on the Indian side prints "Warning: accounts overdue" for you. In
  [sample 2](../demo/sample-report-2.md) the stale-filings finding had to be
  **derived** from an AGM date. That derivation is the product.
- The mirrors' own arithmetic was **wrong on 3 of 3 companies tested**, so a buyer
  reading them unaided is actively misled.

A foreign buyer genuinely cannot do this themselves. A foreign buyer checking a UK
company absolutely can.

### Consequence — the expansion should be reversed, but only in the pitch

Rushi asked on 2026-08-05 to cover companies outside India, and that widening was
executed. **On this evidence it pointed at the weakest part of the offer.**

Proposed correction, which is a re-narrowing to where this started:

- **The pitch is Indian companies, for foreign buyers.** Embarrassingly specific, and
  the only version where the buyer cannot trivially self-serve.
- **UK and Australia stay supported, not promoted.** `scripts/company_check.py`
  already handles them, they cost nothing to keep, and a buyer who asks gets them —
  possibly cheaply, as an add-on. **Capability is not dropped; positioning is.**

This partially reverses a decision Rushi made, so it is **proposed, not applied.**
The listing and profile copy in [B6](b6-outreach-rushi-runs.md) currently lead with
all three jurisdictions and would need reverting to the India-led version.

---

## Competitor pricing — 2026-08-06. Demand is real, and the offer needs re-framing.

Searching for communities where importers ask about supplier verification returned
almost no buyers — but it returned **vendors**, repeatedly: Tetra Inspection,
Panoramic Sourcing, Small World India, Globalising, Netyex. An established industry
sells exactly this.

**[Tetra Inspection](https://tetrainspection.com/supplier-verification-audit/)
publishes its rates:**

| Service | Price |
|---|---|
| Supplier verification | **from $240 per man-day** |
| Factory audit | **from $440 per man-day** (Asia/Africa) |
| Subscription | down to $158–189 per man-day |

Their standard supplier verification is **1–3 days of desk research plus a 0.5–1 day
on-site visit**, delivered in 5–7 business days.

### Two things follow, and they pull in opposite directions

**Good: demand is validated at a real price.** This is the first hard evidence all
week that anyone pays for this, and it is not $5 — it is **$240 to $1,000+** per
engagement, from a company confident enough to publish rate cards. B2 could never
establish this because Fiverr and Upwork are blocked.

**Sobering: what they sell is not what we have.** Their offer includes **a human
walking into the building.** Our entire product is the *desk research* component —
which is 1–3 of their 1.5–4 man-days, and the part that does not require being in
the country.

### The re-framing this forces, and it is better than what we had

Stop positioning this as "supplier verification". It is not, and a buyer who has
seen Tetra's offer will know it. Position it as what it actually is:

> **The cheap desk check you run before deciding whether a supplier is worth a
> $500 on-site audit.**

- Honest about what it is not: no site visit, no factory, no one physically confirms
  anything exists.
- Has a clear job: **triage.** Most suppliers can be eliminated — or cleared enough
  to proceed — from the filing record alone, and paying $240/day to discover a
  company is struck off is absurd.
- Explains the price gap instead of hiding it. $50 against $240+ is not "cheaper
  than the competition", it is **a different step in the process**.
- The "could not verify" section becomes the *handoff*: it is precisely the list of
  things that would need a site visit to settle.

This also survives the UK problem above, because triage value is highest where
self-serving is hardest — India.

**Proposed, not applied.** Feeds the listing copy in
[B6](b6-outreach-rushi-runs.md).

---

## WITHDRAWN — 2026-08-06. The re-narrowing to India is dropped.

Rushi: *"i told u look out of india."* He has now said this twice. **Decision stands:
the offer covers UK, Australia and India, and all three are promoted.** Not
re-litigated further.

**The evidence behind the challenge does not go away**, and it is logged as a risk
rather than argued: the UK finding is visible on the free Companies House page, and
a UK or Australian buyer *can* self-serve. That remains true.

**But the triage re-framing above resolves most of it, and multi-jurisdiction is
what makes triage work.** The two findings landed in the same session and fit
together better than either did alone:

- The value was never "we surface hidden data". It is **"someone runs the check
  properly, cheaply, and tells you what is missing"** — which holds whether or not
  the underlying page is public. Tetra charges $240/man-day for desk research on
  public records; the records being public has never been the point.
- **Covering three countries is a genuine feature for the buyer who actually exists.**
  Someone sourcing internationally does not want to learn Companies House, then ABN
  Lookup, then CIN formats and which Indian mirror is trustworthy. One service, one
  format, one "could not verify" section, whichever country the supplier is in. A
  single-jurisdiction service is worth *less* to that buyer, not more.
- India remains the strongest individual case (MCA 403, paywalled mirrors, arithmetic
  wrong 3-of-3), so it can lead **within** a multi-jurisdiction offer without the
  offer shrinking to it.

**Applied position:** all three jurisdictions promoted, pitched as cheap pre-audit
triage rather than as supplier verification. The B6 listing copy already leads with
all three and does **not** need reverting.

**Risk carried forward, stated once:** a UK/AU buyer who realises Companies House is
free may not convert, and the honest counter is the price gap — $50 triage against
$240+ for the real thing. If UK and Australian orders never materialise while Indian
ones do, that is the signal to revisit, and it will be evidence rather than argument.
