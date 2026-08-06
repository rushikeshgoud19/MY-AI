# Pivot the buyer: GST vendor-compliance checks for Indian SMBs

`wayfinder:research` · **RESOLVED + CONFIRMED 2026-08-06 — tool built and tested**

## Why this ticket exists

Two facts arrived on 2026-08-06 that the earlier plan did not have.

**1. Marketplaces reject Rushi at the gate — empirically, not theoretically.** He
placed bids on Freelancer.com and they were rejected because he does not meet the
criteria. Earlier sessions recorded the zero-review problem as a *risk*; it is now a
measured outcome. Combined with Fiverr and Upwork's ~30% new-applicant rejection,
**the marketplace route is closed for now, and not by choice.**

That makes the channel requirement concrete: **it must have no gatekeeper.**

**2. A gate-free Indian market exists whose pain is the exact product we already
built.**

## The finding

> *"A taxpayer can show **'Active'** registration status while consistently failing
> to file GSTR-1 or GSTR-3B. If a supplier shows six or more months of non-filing,
> their invoices won't appear in your GSTR-2B, and **you won't be able to claim
> ITC**."*
> — [myhq](https://myhq.in/blog/virtual-office/gst-verification-guide/)

Compare the headline of [sample report 3](../demo/sample-report-3-uk.md):

> *"The register says 'Active'. That is the most misleading word on this record."*

**It is the same product.** A register that reports a reassuring status while the
filing history says otherwise, and a buyer who loses real money by trusting the
status field.

The difference is that the Indian version has a **quantifiable rupee consequence**:
an invalid, cancelled or suspended GSTIN means losing input tax credit already
claimed, plus interest and penalties
([myhq](https://myhq.in/blog/virtual-office/gst-verification-guide/),
[TaxGuru](https://taxguru.in/goods-and-service-tax/input-tax-credit-registration-cancelled-vendors-invoices-impact.html)).
GSTR-2B reconciliation flags it automatically, so the buyer finds out from a demand
notice rather than from the vendor.

## Why this fits every constraint that has bitten us

| Constraint | How it fits |
|---|---|
| Marketplaces reject him | **No gatekeeper.** Indian businesses are approached directly |
| No credit card | Not needed |
| No bank account yet | UPI at first sale; needed at payment, not now |
| FEMA / forex | **Gone.** Domestic buyer, domestic supplier, rupees |
| GST registration | Still not needed below ₹20 lakh (B7) |
| No track record | The pitch is a free first check, not a credential |
| Differentiator | Identical: "Active" is not an answer; sources on every line; explicit could-not-verify |

## What must be verified before anything is built

**This ticket is research, not a decision to pivot.** The offer changes only if these
answers hold.

1. **Is the filing history actually retrievable?** `services.gst.gov.in/services/searchtp`
   returns HTTP 200, **but a 200 on a search page is not data access** — the same
   trap flagged for Delaware and Singapore. The official portal likely has a
   captcha, which is not to be bypassed. Third-party mirrors (`knowyourgst.com`,
   `cleartax.in/gst-number-search`) respond and need testing for whether they expose
   the **GSTR-1 / GSTR-3B filing table**, which is the whole product.
2. **Is the "Active but not filing" gap real and common enough** to be worth paying
   to detect?
3. **Would an Indian SMB pay for it, and how much?** B2 found no evidence Indian SMBs
   buy automation *services*. This is not automation — it is a compliance check with
   a computable loss attached — but that gap is unproven and must not be assumed away.
4. **Legal positioning.** This sits near tax advice. It must be framed as *reporting
   what the public GST record shows*, never as a tax opinion or a filing
   recommendation. Feeds B7.

## What is NOT proposed

- **Not** scraped lead lists. The Isenberg/Schneider video's cold-outbound agent runs
  on scraped LinkedIn engagers waterfall-enriched through Apify/Apollo/LeadMagic.
  **That engine is prohibited by the map's Notes** and is not adopted.
- **The targeting insight from that video IS adopted**, because it needs no scraping:
  *"engagement is a hand raise."* Someone publicly complaining about a vendor's GST
  compliance is signalling the problem. One person, one message, manually.
- **Not** abandoning the UK/AU/India company checks. `scripts/company_check.py` and
  the three samples stay. This adds a domestic buyer the existing work can reach.

## Done when

The map records whether the GST filing history is retrievable without bypassing a
captcha, and therefore whether this becomes the primary offer or is dropped.


---

## Resolution — 2026-08-06

**The filing history is public and usable. It is not automatable by us. That is
survivable, and the distinction is the whole answer.**

### What was tested

| Route | Result |
|---|---|
| Official portal `services.gst.gov.in/services/searchtp` | **CAPTCHA.** Not bypassed — out of bounds, and this is the last business that should start there |
| `knowyourgst.com` GSTIN API | **Registration details only** — trade name, legal name, address, status, registration date, PAN. **No filing history.** Trial is 2 days / 50 calls, then plans "start with Rs. 2500", signup required |
| `gstsearch.in` return-status tool | **CAPTCHA** |
| `taxadda.com` return-status tool | Free tier exists but returned *"Sorry! your limit is over"* — rate-limited |
| `legaldev.in` return-status tool | Renders "Fetching filing status… month by month" via JS; **no endpoint exposed in the static HTML.** Reverse-engineering someone's private endpoint is not a foundation for a business and was not attempted |

### The distinction that resolves the ticket

**A CAPTCHA blocks automation. It does not block the work.**

A person can open the official portal, enter a GSTIN, solve the CAPTCHA and read the
filing table — every return, its status, its date — in about a minute. The data is
public and the government publishes it precisely so counterparties can check.

So the product is not blocked. **Delivery is manual.** For a first customer that is
not merely acceptable, it is the correct shape:

- Customer #1 needs **one buyer**, not throughput. Twenty vendors is twenty minutes.
- Rushi has time and no money. Manual effort is the input he actually has.
- The value was never the automation. The value is that **someone does it properly,
  records the source, and states what could not be confirmed** — which is exactly
  what a competitor's "Active ✓" does not do.

### The ceiling, stated now rather than discovered later

This does not scale on Rushi's hands. Roughly a minute per GSTIN means a
200-vendor ledger is a multi-hour job. The honest ceiling is small batches — a
business checking its top 20–50 vendors, not its entire supplier master.

If it ever needs to scale, the route is a **paid GSP/commercial API on Rushi's own
account**, not captcha evasion. That is a decision for after money exists, and it
is deliberately not taken now.

### What changes in the offer

- `scripts/company_check.py` stays for UK/AU/India company checks and is unaffected.
- The GST check is a **separate, manual** deliverable using the same report format:
  sources on every line, durations recomputed, explicit "could not verify".
- **Positioning is unchanged and now sharper:** *"Your vendor's GSTIN says Active.
  That is not the same as your input tax credit being safe."*

### The one thing Rushi should confirm

Open `https://services.gst.gov.in/services/searchtp`, enter any GSTIN, solve the
CAPTCHA, and check that the **return-filing table** (GSTR-1 / GSTR-3B, month by
month) actually appears. Two minutes. **Everything above rests on that table being
visible to a logged-out member of the public** — sourced from tax write-ups, not
witnessed directly, because the CAPTCHA stopped me at the door.

If the table is behind a login, this ticket reopens.


---

## CONFIRMED by Rushi — 2026-08-06

He ran it. The portal returns, to a logged-out member of the public, after one
CAPTCHA:

**Registration block:** legal name, trade name, effective date of registration,
constitution, **GSTIN status**, taxpayer type, jurisdiction (centre and state),
principal place of business, nature of business activities, and HSN/SAC codes.

**Two fields not anticipated, and both are real risk signals:**
**"Whether Aadhaar Authenticated?"** and **"Whether e-KYC Verified?"** — on the
sample both read **No**. On a licensed bank that means little; on an unknown small
vendor, *registered but never Aadhaar-authenticated* is worth a line in a report and
nobody looks at it.

**And the button that matters: `SHOW FILING TABLE`**, plus
`SHOW RETURN FILING FREQUENCY`. The table gives, per return type, with a
financial-year selector:

| | Tax Period | Date of filing | Status |
|---|---|---|---|
| GSTR-3B | June | 20/07/2026 | Filed |
| GSTR-1/IFF | June | 10/07/2026 | Filed |

**Tax period + filing date + status.** That makes three things computable rather
than asserted: **gaps**, **days late**, and **consecutive non-filing streak**.

The ticket's premise is no longer sourced-from-blogs. It is witnessed.

## Built — `scripts/gst_check.py`

Rushi solves the CAPTCHA and pastes the table; the tool does the arithmetic. That is
the correct division: the CAPTCHA blocks automation, not the work.

Statutory due dates, verified rather than assumed
([SoftwareSuggest](https://www.softwaresuggest.com/blog/gst-filing-due-dates/),
[ClearTax](https://cleartax.in/s/gstr-3b)): monthly **GSTR-1 11th**, **GSTR-3B
20th** of the following month; QRMP **GSTR-1 13th**, **GSTR-3B 22nd or 24th by
state**. The script uses the 22nd and **prints the caveat rather than guessing the
state**.

Tested on the real Ujjivan data (clean — every return on time, reported as *"a
result, not an absence of one"*) and on synthetic data with gaps and late filings
(correctly found +2, +8, +19, +46 days late and the missing periods).

### The bug worth recording

The first version extrapolated missing periods **into financial years the user never
queried** and reported them as "past due with no filing shown". That is inventing a
finding out of absent data — the precise failure this whole company exists to
eliminate, reproduced in our own tool inside an hour of writing it.

Fixed: gap detection is now bounded to the financial years actually present in the
pasted data, and the report prints **"Financial year(s) queried: X. Nothing outside
these years is reasoned about."**

Verified: 24 possible periods in FY2025-26, 5 filed, 2 not yet due at year end,
**17** genuinely missing — arithmetic checked by hand.

## Next

Positioning line, unchanged and now evidenced:
> **"Your vendor's GSTIN says Active. That is not the same as your input tax credit
> being safe."**

Still open: **who to sell it to, and how they are reached without a gatekeeper.**
That is the channel question B6 left open, now with a domestic buyer.
