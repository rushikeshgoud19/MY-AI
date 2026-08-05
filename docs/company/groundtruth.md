# MAP — Groundtruth: first paying customer

`wayfinder:map` · local-markdown tracker · tickets in `./tickets/`

## Destination

ONE customer has paid real money for one automation, and it has been delivered and
works. Not a company, not a pipeline, not an audience - one completed
money-for-value loop, end to end, so every assumption in it has been tested against
someone who was willing to pay.

Reached when: money is in Rushi's account, the customer has the working thing, and
the daily log records what it took.

## Notes

**Division of labour, non-negotiable.** Claude does the work; Rushi is the
principal. Claude researches, builds, writes every asset, drafts every message,
tracks and reports. Claude does NOT create accounts, enter payment details, sign
anything, receive money, or send a message to a real person without Rushi
approving that specific batch. Any ticket implying otherwise is mis-scoped and
gets ruled out of scope, not "worked around".

**What the source material actually says.** The prompt for this effort was a video
about Vending-Bench, where Opus 5 set a record by bribing, threatening and lying to
suppliers, and Project Vend, where Claude ran a real shop into bankruptcy while
hallucinating a human backstory. Neither is a playbook. The lesson worth carrying:
autonomous agents are good at the WORK and bad at judgement, memory and reality
checking - so the human stays on every irreversible action, and the agent's output
is checked, not trusted.

**The asset is not "AI automation".** Everyone sells that. What exists here that
others do not have: a multi-agent tribunal that grounds its answers, checks its own
arithmetic and citations deterministically, and says "could not verify" instead of
inventing. Measured, not claimed - see `docs/wayfinder/`. The offer should sell
THAT, or it is competing on price with people who have n8n templates.

**Execution rides in this map.** Tickets that are buildable get built in the session
that decides them.

**No earnings promises, ever** - not in the assets, not to a customer, not in this
map. "AI will make you money" is the claim every competitor makes and cannot back.

**The daily report is a standing mechanism**, not a ticket: `docs/company/log/`
gets one dated file per working session - what was done, what it cost, what is next,
what is blocked on Rushi.

## Decisions so far

- **2026-08-05 — Clustly is not the first channel (B8).** Its own homepage reads
  "147 services live · $1,950 settled on-chain"; separately, taking USDC from
  foreign buyers for exported services appears to breach FEMA (no FIRC, penalties
  up to 3x). Neither the demand nor the legality holds. Crypto rails to
  international customers are closed.
- **2026-08-05 — FamPay is not a rail (B1).** It is a Triotech PPI wallet, not a
  bank account; its clause 22.2 prohibits commercial use outright and the Small PPI
  form cannot pay out to a bank at all.
- **2026-08-05 — Rushi can be paid, domestically, today-ish (B1 resolved).** He is
  19 with a PAN, so s.11 contract capacity is fine. Rail: UPI/IMPS into a savings
  account in his own name against an individual invoice with PAN. No registration
  needed (sole proprietor by default), no GST below ₹20 lakh services turnover, no
  gateway. Fee zero. **International is strictly domestic plus 2-3% plus FEMA
  paperwork, and needs the same bank account** — so domestic first, not as a
  preference but because there is no cheaper path. **The one blocking action is
  Rushi opening a savings account.**
- **2026-08-05 — the customer is Indian and domestic.** Narrows B2 and B3 from
  "what will businesses pay for" to "what will an Indian SMB pay, in rupees, over
  UPI." **Now under challenge — see B2.**
- **2026-08-05 — B2 is partial, and honestly so.** Fiverr (CAPTCHA, not bypassed),
  Upwork (Cloudflare) and Reddit (policy) are all unreachable, so the median
  *completed-order* price is unknown. Verified: n8n/AI-automation gigs on Fiverr
  start at **$50–$125**. Everything richer than that is course-and-agency content
  marketing and was excluded.
- **2026-08-05 — the offer is decided (B3): counterparty due-diligence reports**,
  every claim linked to source, with an explicit "could not verify" section.
  Approved by Rushi. Correction: his "1" was **not** 1 hour/week — that was my
  misreading, and one of the two supports under the marketplace argument fell away
  with it. His time budget is unstated.
- **2026-08-05 — first demo artefact exists (B5):
  [`docs/company/demo/sample-report.md`](demo/sample-report.md).** Registry access
  risk retired: MCA itself is 403, but ZaubaCorp and Tofler both parse. **Both are
  mirrors of MCA, so they are not two independent sources** — now the largest known
  weakness in the offer.
- **2026-08-06 — [B4](tickets/b4-company-section-and-log.md) resolved.** Daily log
  built and running; memory rewritten (`groundtruth-company` was stale, and
  `india-crypto-payment-fema` split out as a durable fact that would otherwise be
  re-derived wrongly). **The console Company section is ruled out of scope** — see
  Out of scope below.
- **2026-08-06 — [B6](tickets/b6-outreach-rushi-runs.md) resolved: Route C, then B.**
  Give one report away to one real business before choosing any channel, then direct
  outreach. Another marketplace was **not** taken — the Fiverr objection was never
  stated, and if it was the zero-review problem then every marketplace shares it.
  **Blocked on Rushi for one thing: a recipient name.**
- **2026-08-06 — report generation is automated: `scripts/company_check.py`.**
  Tested on UK, AU and IN against the same companies as the hand-built samples. Never
  copies a displayed duration, never retrieves directors, and **refuses to emit a
  report of blanks on fetch failure**. Two silent-failure bugs found and fixed while
  testing. This is *not* the tribunal — `orchestra.py` remains unwired.
- ~~**2026-08-05 — B6 REOPENED. Rushi dropped Fiverr**~~ about an hour after opening the
  account. Channel undecided. **The reason is not known and is being asked**, because
  each possible objection points at a different replacement — and if the objection is
  "zero reviews", **no marketplace fixes it** and the answer is direct outreach.
- **2026-08-05 — third sample, and the best one:
  [`sample-report-3-uk.md`](demo/sample-report-3-uk.md).** A UK company whose status
  reads "Active" while carrying an active proposal to strike off, accounts overdue
  **5y 2m** (never filed in 7 years of existence), and a confirmation statement
  **4y 2m** overdue. Sourced from Companies House directly — the register, not a
  mirror — and cross-checked sideways against The Gazette. **This should lead**, and
  it is the clearest single argument for the whole offer: "Active" is not an answer.
- ~~**2026-08-05 — the motion is a listing, not outreach (B6 resolved).**~~ Channel:
  Fiverr, at a **flat 20% commission** plus FX — about ₹5,000 in hand on an $80
  order. 20% of a marketplace with buyers beats 4% of one without, which is exactly
  why Clustly lost. Listing copy drafted, **nothing published.**
- **2026-08-05 — offer covers three tested jurisdictions: UK, Australia, India.**
  Expanded on Rushi's instruction, but only to registers where **real data was
  actually retrieved** — UK Companies House and the Australian Business Register are
  **primary government sources**, richer than India's, which is mirrors only.
  OpenCorporates is hCaptcha-blocked, California 403, Delaware/Singapore/Germany
  untested. A 200 on a landing page is not access to a register. Everything else is
  declined in the gig text so no undeliverable order can arrive.
- **2026-08-05 — this partly inverts the "India is his edge" reasoning.** India has
  worse data but better defensibility; UK/AU have better data but no moat. Keeping
  India as the differentiator and adding UK/AU for data quality and buyer pool.
- **2026-08-05 — the narrowing that resolves the domestic/international tension:
  the buyer is international, the subject is Indian.** "Verify an Indian company
  from its MCA filing record" — his edge is the Indian registry, the money is
  foreign. Neither side of B1's fork had to win.
- **2026-08-05 — biggest live risk is zero reviews against sellers with 400+.** No
  copy solves it. If no order arrives, the listing failed, not the offer, and the
  next move is a real buyer conversation.
- **2026-08-05 — second demo artefact (B5):
  [`sample-report-2.md`](demo/sample-report-2.md)**, a live company. Ends in
  "proceed, with a question" rather than a score: status Active on both sources, but
  no AGM recorded since 2023-09-06 against a statutory maximum of 15 months (+3).
  The pair now demonstrates both directions.
- **2026-08-05 — the source's arithmetic is systematically wrong.** ZaubaCorp
  displays an incorrect company age on **three of three** companies tested. Only one
  is obviously broken; the other two are plausible numbers that are untrue. Found,
  not constructed, and the strongest argument yet for recomputing rather than
  quoting.
- **2026-08-05 — verification does not sell as a product; it sells as an attribute
  (B2, wide sweep).** Standalone fact-checking clears **$5** on Fiverr, three
  listings, same floor. The identical rigour attached to a deliverable people
  already buy clears **$80–$350**. This amends the map's own premise: the refusal is
  not the product, it is the reason a buyer picks you over the next seller of a
  thing they were already buying.
- **2026-08-05 — "could not verify" is an asset in exactly one category found:
  counterparty due diligence.** Everywhere else it reads as failure; there it is the
  most valuable line in the document.
- **2026-08-05 — Rushi has 1 hour a week, and answered "both" to service-vs-product.**
  "Both" refused as stated. But 1 hr/week independently selects a fixed-scope,
  fixed-price marketplace listing — productised in scope, service in delivery — which
  also removes outreach. Offer recommended in B3, **awaiting his yes/no**.
- **2026-08-05 — no evidence found of Indian SMBs buying automation services.**
  Indian searches surfaced only tool pricing (~₹1,700–4,200/mo) and ₹15 lakh
  enterprise RPA; the ₹5k–₹50k service sale is absent from the record. Absence of
  evidence, not evidence of absence, but it puts the domestic-first call from B1 at
  risk. **Trigger: if two or three real Indian businesses cannot confirm the demand,
  reopen B1 rather than defend it.**

- **2026-08-05 — B7 mostly collapses.** Selling through a marketplace means no
  invoice to write (Fiverr bills the buyer), no scope-of-work contract (the gig
  description plus Fiverr's terms are the agreement), no GST, no registration. What
  remains: FIRA at volume, declaring foreign income at ITR, and any student-specific
  institutional condition — which only Rushi can check.
- **2026-08-05 — the full runbook is [`plan.md`](plan.md), with a tripwire:** if the
  gig is live 30 days with zero orders, the **listing** failed, not the offer, and
  the next move is talking to two or three real buyers rather than editing copy.

## Not yet specified

- ~~Whether Clustly settles both the payment question and the outreach question at
  once.~~ **Answered 2026-08-05: no, on both counts — see B8.** Note the assumption
  that failed: the worry recorded here was the 30% VDA rate hurting take-home. That
  was the wrong worry. The 30% applies to the *gain* on converting a stablecoin,
  which is near zero; the receipt itself is ordinary business income at slab rates.
  The thing that actually kills it is FEMA — export proceeds must arrive through an
  authorised dealer bank in convertible currency, and crypto does not.
- Pricing shape and whether TDS at 10% (s.194J, corporate clients, above ₹30,000
  per contract) changes it. Cashflow fact, not a blocker — feeds B3.
- Pricing shape - one-off build fee, monthly retainer, or per-run. Depends entirely
  on what the market research finds people actually paying, and on whether the
  offer is a service or a product.
- Delivery and support: what happens the first time a customer's workflow breaks at
  2am, and who is on the hook. Sharpens once there is an offer.
- What customer #2 looks like, and whether #1 was a repeatable niche or a fluke.
- Whether any of this should run under Mizune's brand, Groundtruth's, or Rushi's own
  name.

## Out of scope

- Claude sending outbound messages, holding funds, signing, or acting as a company
  officer. Permanent, not a sequencing decision.
- Mass cold outreach, scraped lead lists, and anything that needs a fake identity to
  work. Beyond the ethical line and it poisons the domain and the accounts.
- Selling Mizune herself, or anything that would put Rushi's personal assistant and
  her memory in front of customers.
- **The Company section in the Agentic OS console** — part of
  [B4](tickets/b4-company-section-and-log.md), ruled out 2026-08-06. Built honestly it
  displays ₹0 revenue, zero customers, nothing published: a UI whose entire content is
  one line of the daily log. A session's work that looks like a milestone and moves
  nothing toward a paying customer. Returns only if there is real data to show, as a
  fresh ticket. **Rushi can override — it is his console.**
- **Delivery template and turnaround measurement** (from [`plan.md`](plan.md) Phase 2)
  — parked 2026-08-06. Both optimise a process that has never run once. They become
  urgent the day an order arrives and not before.
