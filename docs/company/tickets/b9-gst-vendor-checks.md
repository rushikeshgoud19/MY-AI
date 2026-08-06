# Pivot the buyer: GST vendor-compliance checks for Indian SMBs

`wayfinder:research` · OPEN · **frontier** · supersedes the channel half of B6

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
