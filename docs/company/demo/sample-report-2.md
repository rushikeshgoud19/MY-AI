# Counterparty check — PARAMOUNT PROFESSIONAL SERVICES PRIVATE LIMITED

**Sample report 2 — the company is live.** This is the companion to
[sample 1](sample-report.md), where the company was struck off. A check that only
looks useful when the answer is bad proves half a product.

Checked 2026-08-05 · CIN U72900RJ2016PTC055249

---

## The finding

> **Status is Active — but nothing has been filed since 2023.**
> The register says the company exists. It does not say it is trading.

| | |
|---|---|
| ZaubaCorp | Status: **Active** (data as on 2026-07-13) — [source](https://www.zaubacorp.com/PARAMOUNT-PROFESSIONAL-SERVICES-PRIVATE-LIMITED-U72900RJ2016PTC055249) |
| Tofler | **Active**, updated 15 May 2026; *"is an unlisted private company"* (present tense) — [source](https://www.tofler.in/paramount-professional-services-private-limited/company/U72900RJ2016PTC055249) |

Two sources agree the company is on the register and not struck off. That is a
different statement from "this is a safe counterparty", and the next section is why.

---

## Flag: the filing record stops in 2023

| | |
|---|---|
| Date of last Annual General Meeting | **2023-09-06** (ZaubaCorp) |
| Date of last filed balance sheet | **2023-03-31** (ZaubaCorp) |
| Gap from last AGM to this check | **2 years, 10 months, 30 days** (~35 months, computed) |

Under **section 96 of the Companies Act 2013**, not more than **fifteen months**
may elapse between one AGM and the next, and the Registrar may extend that by a
maximum of **three months** ([CAIRR](https://ca2013.com/annual-general-meeting/),
[AUBSP](https://www.aubsp.com/section-96-annual-general-meeting/)). Fifteen months
from 2023-09-06 is 2024-12-06; with the maximum extension, 2025-03-06. This check is
dated 2026-08-05.

**Stated precisely, because the distinction matters:** the correct claim is *"no AGM
has been recorded since 2023-09-06"*, **not** *"the company has not held an AGM"*.
The source reflects what has been filed and mirrored. A meeting may have been held
and not filed, or filed and not yet mirrored. What can be said is that the public
record shows a gap longer than the statute contemplates, and that is a question to
put to the counterparty rather than a conclusion about them.

---

## What was verified

| Field | Value | Source |
|---|---|---|
| Legal name | PARAMOUNT PROFESSIONAL SERVICES PRIVATE LIMITED | ZaubaCorp, Tofler |
| CIN | U72900RJ2016PTC055249 | ZaubaCorp, Tofler |
| Status | **Active** | ZaubaCorp, Tofler |
| Incorporated | 2016-06-17 | ZaubaCorp; Tofler ("17 June, 2016") |
| ROC / Reg. no. | ROC Jaipur / 55249 | ZaubaCorp |
| Class | Private, limited by shares, non-government | ZaubaCorp |
| Registered address | T-335, 3rd Floor, Unnati Tower, Central Spine, Vidhyadhar Nagar, Jaipur, Rajasthan 302021 | ZaubaCorp |
| Registered activity | NIC 7290 — other computer related activities | ZaubaCorp |
| Authorised capital | INR 100,000.00 | ZaubaCorp |
| Paid-up capital | INR 100,000.00 | ZaubaCorp |
| Number of members | 0 | ZaubaCorp |
| Directors on record | 2 identifiers found — **names withheld from this sample** | ZaubaCorp |

Paid-up capital of INR 100,000 is the statutory minimum shape for a private limited
company and is noted without inference — it is common and means little on its own.

---

## Arithmetic check — and a systematic failure in the source

The page displays:

> Age of Company **10 years, 1 months, 2 days**

Recomputed from incorporation on 2016-06-17 to ZaubaCorp's own "as on" date of
2026-07-13: **10 years, 0 months, 26 days.** The displayed figure is wrong.

That prompted checking whether it was a one-off. **It is not.** Three companies
were tested against the same as-on date of 2026-07-13:

| Company | Incorporated | Page displays | Computed | Match |
|---|---|---|---|---|
| Sabjiwaala (sample 1) | 2011-07-21 | 15y **-1m** 25d | 14y 11m 22d | no |
| Paramount (this one) | 2016-06-17 | 10y 1m 2d | 10y 0m 26d | no |
| Creative Construction | 2021-12-28 | 4y 6m 20d | 4y 6m 15d | no |

**Three out of three wrong.** This is a systematic defect in the source, not a
glitch — and note that only the first is *obviously* broken, because a negative
month is impossible on its face. The other two read as perfectly plausible numbers
that happen to be untrue. Those are the dangerous ones, and they are the reason
arithmetic is recomputed rather than quoted.

Nothing here changes the status finding. It is reported because every number gets
checked whether or not it turns out to matter.

---

## Could not verify

| Item | Why not |
|---|---|
| Email address | Redacted at source — ZaubaCorp displays `[email protected]` |
| Total assets, revenue, any financials | Behind ZaubaCorp's paywall; Tofler gates the same data |
| Whether an AGM was held after 2023-09-06 but not filed or not mirrored | No source consulted that could distinguish these |
| Current trading activity, employees, website, phone | No source found |
| Whether the two directors hold positions in other companies | **Not checked** |
| Any litigation, charges, or defaults | **Not checked — out of scope of this sample** |
| Director names and DINs | Retrieved but deliberately withheld |

**Freshness caveat.** Neither source is live. ZaubaCorp's data is stamped "as on
2026-07-13"; Tofler's page says "Updated: 15 May 2026". The Tofler confirmation of
"Active" is therefore close to three months old at the date of this check. Status
can change between a mirror's refresh and the date you read it.

**The structural limitation, repeated from sample 1.** The MCA portal — the primary
source — returned HTTP 403 and was not reachable. **ZaubaCorp and Tofler are both
mirrors of MCA.** Their agreement is worth something, but two mirrors of one
upstream are not two independent confirmations.

---

## Reading the two samples together

| | Sample 1 — Sabjiwaala | Sample 2 — Paramount |
|---|---|---|
| Register status | Struck off | Active |
| Verdict shape | Stop | Proceed, with a question |
| The useful line | "This company has been struck off" | "No AGM recorded since 2023-09-06" |

Neither report ends in a score or a recommendation. Sample 1 found a fact that
settles the matter. Sample 2 found a live company whose paperwork stops three years
ago — which is not a red flag, not a clean bill, and precisely the sort of thing a
confident one-line answer would flatten into "looks fine".

---

## What these samples are, and are not

**Are:** checks of public filing records, every claim traceable to the page it came
from, every gap stated.

**Are not:** credit opinions, compliance or KYC determinations, fraud accusations,
or advice on whether to transact.

## Honest note on how this was produced

Assembled **by hand** — direct fetch, parse, manual cross-check — **not** by running
`server/orchestra.py`. It demonstrates that the data is reachable and what the
discipline looks like on a real company. It does not demonstrate that the tribunal
produced it. Wiring that up is the next step and is not done.
