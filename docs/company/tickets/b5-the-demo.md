# Build the demo that proves it works

`wayfinder:task` · **FIRST ARTEFACT BUILT 2026-08-05** · not yet wired to the tribunal

## Question

The offer needs one artefact a stranger can look at for ninety seconds and
understand. Not a description of a capability — a run.

The natural candidate: the tribunal answering a real question in the buyer's
domain, showing its sources, its arithmetic check, and — critically — **a case
where it refuses**. "Could not verify a current figure, check [Pricing]" is a
better sales asset than a confident answer, because every competitor's demo is a
confident answer and the buyer has already been burned by one of those.

To decide when this is taken:

- A recorded run, a live link, or a one-page writeup with real output pasted in?
- Which question? It has to be one where the audit trail visibly matters, and where
  the honest refusal reads as strength rather than as the tool failing.
- What is shown versus what stays private. Rushi's own infrastructure, memory notes
  and Mizune are not demo material.

Blocked on the offer, because a demo without a named buyer is a tech showcase, and
tech showcases do not sell.

---

## Progress — 2026-08-05

Offer approved by Rushi ("go for it"), so this unblocked. **Artefact:
[`docs/company/demo/sample-report.md`](../demo/sample-report.md).**

### The risk B3 flagged is retired: registry data is reachable

Tested before building anything, because if this failed the offer collapsed.

| Source | Result |
|---|---|
| `mca.gov.in` — the primary source | **HTTP 403.** Not reachable. |
| `zaubacorp.com` | 200; full company master data parses cleanly |
| `tofler.in` | 200; status and incorporation date parse cleanly |
| `indiafilings.com` | 200 (not used) |

**Important caveat carried into the report:** ZaubaCorp and Tofler are both mirrors
of MCA data. They agreeing with each other is worth something, but **two mirrors of
one upstream are not two independent confirmations**, and the report says so. A
production version needs MCA access or that caveat on every copy. This is now the
largest known weakness in the offer.

### The demo subject, and why it is better than anything designable

`SABJIWAALA COM RETAILERS PRIVATE LIMITED` (CIN U74120MH2011PTC220022), found by
searching for any real company. It turned out to carry, genuinely and without
arrangement, every property the demo needed:

1. **A decisive finding.** Status is **Strike Off** — confirmed on ZaubaCorp
   ("Status Strike Off", as on 2026-07-13) and Tofler ("Strike Off", updated
   05 Jul 2026, and describing it in the past tense). A buyer about to pay this
   company wants exactly this sentence and nothing else.
2. **A real discrepancy.** Named "Sabjiwaala.com Retailers" — a vegetable seller —
   while its registered activity is **NIC 7412, accounting and tax consultancy**.
   Flagged as a question, explicitly *not* as a finding, because companies change
   activity without updating the code.
3. **A live arithmetic failure in the source.** ZaubaCorp displays
   *"Age of Company 15 years, -1 months, 25 days"*. A negative month is malformed.
   Recomputed: **14y 11m 22d** as at their own as-on date, **15y 0m 15d** as at
   2026-08-05. The source got its own sums wrong, which is a better demonstration of
   why arithmetic gets checked than any constructed example.
4. **Genuine unverifiables.** Email redacted at source; last AGM, last balance sheet
   and all financials paywalled; whether the strike-off was appealed **not checked
   and said to be not checked**.

### What was deliberately withheld

Three director identifiers were retrieved. **Names are withheld from the sample.**
They are public record, but naming private individuals in a sales artefact is
unnecessary to prove the point and is not done.

### Honesty carried on the face of the artefact

The report states that it was assembled **by hand** — fetch, parse, manual
cross-check — and **not** by running `server/orchestra.py`. It proves the data is
reachable, the format holds, and the discipline is real. It does not prove the
tribunal produced it, and claiming otherwise would fail the standard the report
exists to sell.

### Not done

- **Not wired to `orchestra.py`.** Checking `config.json` for API keys was declined
  at the permission prompt and **not retried** — that file holds secrets and is
  Rushi's to open. Wiring needs his decision on keys.
- **Not published anywhere.** Requires Rushi's approval, and before public use there
  is a judgement call: this is a real company with a negative finding. Options are
  his approval as-is, or swapping to a company where the finding is neutral. Flagged,
  not decided.
- No pricing attached, no listing written.

### Next inside this ticket

1. Wire the report to `orchestra.py` so a run produces it (needs keys).
2. Decide the public-use question above.
3. Second sample on a company that is **live and clean**, since a report that only
   looks impressive when the answer is bad proves half the product.
