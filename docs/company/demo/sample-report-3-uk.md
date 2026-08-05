# Counterparty check — AA SOLUTIONS TRADING LTD (UK)

**Sample report 3 — the one that shows why "Active" is not an answer.**

Checked 2026-08-05 · Company number 11998471 · Source: Companies House

---

## The finding

> **The register says "Active". That is the most misleading word on this record.**
>
> There is an **active proposal to strike the company off**, it has **never filed
> accounts in seven years**, and its **confirmation statement is four years
> overdue**.

A check that reports "Status: Active ✓" and stops is not wrong. It is worse than
wrong — it is confidently useless, and it is what you get almost everywhere.

---

## What the record actually says

| Field | Value |
|---|---|
| Company name | AA SOLUTIONS TRADING LTD |
| Company number | 11998471 |
| **Status** | **Active — active proposal to strike off** |
| Company type | Private limited company |
| Incorporated | 16 May 2019 (**7 years, 2 months, 20 days** ago) |
| Registered office | 95 Asquith Boulevard, Leicester, England, LE2 6FE |
| Nature of business (SIC) | **80300 — Investigation activities** |

All from [Companies House](https://find-and-update.company-information.service.gov.uk/company/11998471),
the official UK register — **not a mirror, not a data reseller.**

---

## The two overdue filings

Companies House flags both with a warning on the record itself.

| Filing | Due | Overdue by |
|---|---|---|
| **First accounts** (made up to 31 May 2020) | 16 May 2021 | **5 years, 2 months, 20 days** |
| **Confirmation statement** (next statement date 15 May 2022) | 29 May 2022 | **4 years, 2 months, 7 days** |

Last confirmation statement filed: **15 May 2021** — 5 years, 2 months, 21 days ago.

**Read that first row again.** The accounts overdue are the company's *first*
accounts. In seven years of existence it has never filed a set. This is not a
company that fell behind; it is one whose filing record effectively stops at
incorporation.

Every duration above was **recomputed from the dates on the record**, not copied
from any summary.

---

## A note on the SIC code

The registered activity is **80300 — Investigation activities**. Noted without
comment beyond the obvious: the classification is a self-declared field and means
only that this is what was written on a form in 2019.

---

## Independent confirmation

Companies House is the primary source, so there is no better register to check it
against. Cross-checking therefore went sideways rather than up, to
**[The Gazette](https://www.thegazette.co.uk/all-notices/notice?text=AA+SOLUTIONS+TRADING)** —
the UK's official public record of statutory notices.

**Confirmed there:** `AA SOLUTIONS TRADING LTD 11998471 (C1) 16/05/2019`, published
28 May 2019 — an official notice matching the company number and incorporation date
exactly.

**Not confirmed there:** a strike-off notice. One may well exist; the search
retrieved the incorporation notice and did not surface a strike-off entry, and the
absence in what was retrieved is **not** evidence that none was published. Listed
below rather than quietly dropped.

---

## Could not verify

| Item | Why not |
|---|---|
| Whether a strike-off notice has been gazetted | Not located in the search performed — see above. Not the same as "no notice exists" |
| Directors and persons of significant control | **Not retrieved for this sample.** Available on the register; deliberately excluded because they are named individuals |
| Any accounts, turnover, assets or financial position | **None have ever been filed.** Nothing exists to retrieve |
| Whether the company trades, has staff, or has a website | No source consulted |
| Whether the registered office is an operating address or a service address | Not established. A Leicester residential-style address is common for both |
| Any charges, insolvency history or litigation | Out of scope of this sample |

---

## Why this sample is stronger than the Indian ones

Worth stating, because it changes which register this service should lead with.

| | India ([sample 1](sample-report.md), [2](sample-report-2.md)) | UK (this one) |
|---|---|---|
| Source | ZaubaCorp / Tofler — **mirrors** of MCA | Companies House — **the register itself** |
| Primary source reachable? | **No.** MCA returns HTTP 403 | Yes, directly |
| Filing currency | Had to be derived from AGM dates | **Flagged on the record, with due dates** |
| Freshness | Stamped weeks or months old | Live |
| Source arithmetic | **Wrong on 3 of 3 companies tested** | No arithmetic errors found |

The Indian samples had to work around the data. Here the register does the hard part
and the value added is reading it properly — noticing that "Active" and "active
proposal to strike off" appear in the same field, and that the overdue accounts are
the first ones.

---

## What this is, and is not

**Is:** a reading of the official UK register, every claim traceable, every gap
stated.

**Is not:** a credit opinion, a compliance or KYC determination, an accusation of
wrongdoing, or advice on whether to transact. Companies fall behind on filings for
ordinary reasons. What the record supports is a question to put to the counterparty,
not a conclusion about them.

## How this was produced

Assembled **by hand** — direct fetch from Companies House and The Gazette, parsed,
durations recomputed — **not** by running `server/orchestra.py`. It demonstrates
that the data is reachable and what the discipline looks like. It does not
demonstrate that the tribunal produced it.
