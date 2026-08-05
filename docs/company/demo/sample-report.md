# Counterparty check — SABJIWAALA COM RETAILERS PRIVATE LIMITED

**Sample report.** Every line below carries the source it came from. The section
that matters most is the last one: what could **not** be verified.

Checked 2026-08-05 · CIN U74120MH2011PTC220022

---

## The finding

> **This company has been struck off the register.**
> Confirmed independently by two sources.

| | |
|---|---|
| ZaubaCorp | Status: **Strike Off** (data as on 2026-07-13) — [source](https://www.zaubacorp.com/company/Sabjiwaala-com-Retailers-Private-Limited/U74120MH2011PTC220022) |
| Tofler | **Strike Off**, updated 05 Jul 2026; *"was an unlisted private company"* (past tense) — [source](https://www.tofler.in/sabjiwaala-com-retailers-private-limited/company/U74120MH2011PTC220022) |

If you were about to pay this company, that is the whole report. Everything below
is the supporting detail and the caveats.

---

## What was verified

| Field | Value | Source |
|---|---|---|
| Legal name | SABJIWAALA COM RETAILERS PRIVATE LIMITED | ZaubaCorp, Tofler |
| CIN | U74120MH2011PTC220022 | ZaubaCorp, Tofler |
| Status | **Strike Off** | ZaubaCorp, Tofler |
| Incorporated | 2011-07-21 | ZaubaCorp; Tofler ("21 July, 2011") |
| ROC / Reg. no. | ROC Mumbai / 220022 | ZaubaCorp |
| Class | Private, limited by shares, non-government | ZaubaCorp |
| Registered address | 904, Mirabilis Nahar Amrit Shakti, Chandivali, Andheri (E), Mumbai, Maharashtra 400072 | ZaubaCorp |
| Registered activity | NIC 7412 — *accounting, book-keeping and auditing activities; tax consultancy* | ZaubaCorp |
| Authorised capital | INR 100,000.00 | ZaubaCorp |
| Paid-up capital | INR 100,000.00 | ZaubaCorp |
| Number of members | 0 | ZaubaCorp |
| Directors on record | 3 identifiers found — **names withheld from this sample** | ZaubaCorp |

Two sources agree on name, CIN, status and incorporation date. The remaining rows
rest on ZaubaCorp alone and are marked as single-source by that fact.

---

## Flag: the name and the registered activity do not match

The company is named **"Sabjiwaala.com Retailers"** — *sabjiwaala* meaning a
vegetable seller — but its registered activity code is **NIC 7412: accounting,
book-keeping and auditing activities; tax consultancy** (ZaubaCorp).

This is a discrepancy, not a finding. Companies do change what they do without
updating their NIC code, and a retail name over an accounting code is not evidence
of anything by itself. It is flagged because it is the kind of mismatch worth a
question, and because a report that silently smoothed it over would be less useful
than one that did not.

---

## Arithmetic check

The source page displays:

> Age of Company **15 years, -1 months, 25 days**

A negative month count is malformed on its face. Recomputed from the incorporation
date of 2011-07-21:

| Reference date | Correct age |
|---|---|
| 2026-07-13 (ZaubaCorp's own "as on" date) | **14 years, 11 months, 22 days** |
| 2026-08-05 (date of this check) | **15 years, 0 months, 15 days** |

Neither matches what the page shows. The figure is presentational and changes
nothing about the strike-off finding — it is included because the arithmetic on
every number in a report gets checked whether or not it turns out to matter, and
this one is a live example of a source getting its own sums wrong.

---

## Could not verify

This is the section most reports do not have.

| Item | Why not |
|---|---|
| Email address | Redacted at source — ZaubaCorp displays `[email protected]` |
| Date of last AGM | Behind ZaubaCorp's paywall |
| Date of last filed balance sheet | Behind ZaubaCorp's paywall |
| Total assets / any financials | Behind ZaubaCorp's paywall (Tofler also gates this) |
| Whether the strike-off was appealed or the company restored | **Not checked — no source consulted.** Restoration is possible under Indian company law and would not necessarily show on these mirrors |
| Current trading activity, website, phone | No source found. Absence of a website is not evidence of absence of a business |
| Director names and DINs | Retrieved but deliberately withheld from this sample |

**The most important limitation:** the MCA portal — the primary source — returned
HTTP 403 and was not reachable. **Both sources used are third-party mirrors of MCA
data, not MCA itself.** They agree with each other, which is worth something, but
two mirrors of one upstream are not two independent confirmations. A production
version of this report needs either MCA access or this caveat printed on every copy.

---

## What this sample is, and is not

**Is:** a check of public filing records, with every claim traceable to the page it
came from and every gap stated.

**Is not:** a credit opinion, a compliance or KYC determination, a fraud
accusation, or advice on whether to transact. It reports what the register says and
what it does not say. Struck-off status has specific legal meanings and remedies
that are outside its scope.

---

## Honest note on how this was produced

This report was assembled **by hand** — direct fetch, parse, and manual
cross-check — **not** by running `server/orchestra.py`. What it demonstrates is that
the data is reachable, that the format holds up, and what the discipline looks like
on a real company. Wiring it to the tribunal is the next step and is not done.

Saying so here rather than implying an automated run is the same standard the
report itself is selling.
