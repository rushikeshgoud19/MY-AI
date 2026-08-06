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
- **2026-08-06 — the UK half of the offer is much weaker than claimed (challenge to
  [B3](tickets/b3-pick-the-offer.md)).** Our UK sample's headline finding is **printed
  on the free Companies House page in plain sight** — verified in the raw HTML. We
  were reading a public page aloud, not revealing hidden data, and against B2's own
  evidence that is a $5 service priced at $60. Australia has the same problem.
  **India does not:** MCA is 403, the usable mirrors are obscure and paywalled, the
  stale-filing finding must be *derived*, and those mirrors' arithmetic was wrong on
  3 of 3 companies. **Proposed: re-narrow the pitch to Indian companies for foreign
  buyers; keep UK/AU supported but unpromoted.** **WITHDRAWN same day** — Rushi has
  said twice to look outside India; decision stands, all three promoted. Risk logged,
  not argued.
- **2026-08-06 — demand is validated at a real price, and the offer is re-framed
  (B3).** [Tetra Inspection](https://tetrainspection.com/supplier-verification-audit/)
  publishes **supplier verification from $240/man-day** and factory audits from
  $440/man-day — but their product includes **a human walking into the building**.
  Ours is the desk-research component only. So the pitch becomes **"the cheap desk
  check you run before deciding whether a supplier is worth a $500 on-site audit"** —
  triage, not verification. This is the first hard evidence anyone pays for this, and
  it is not $5. **Covering three countries is what makes triage valuable**: a buyer
  sourcing internationally does not want to learn three registries.
- **2026-08-06 — marketplace survey done on Rushi's instruction; Fiverr excluded and
  not re-argued (B6).** Checked for demand in *this category*, not fee pages.
  **PeoplePerHour is dead** — its Due Diligence board had 3 results and none were due
  diligence. **Contra is dead** — 0% fee but "no feed of active job posts", the
  Clustly failure mode. **Upwork is the only real alternative**: a genuine
  due-diligence job board, budgets $75+, ~10% fee, and an apply-to-jobs model that
  suits a zero-review seller better than waiting to be found.
- **2026-08-06 — the no-card constraint is now the binding constraint on the whole
  business.** Upwork abolished free sign-up Connects: a new freelancer must buy 100
  for **$15** or pay **$19.99/mo**, and buying **requires a billing method**. Rushi
  has no card — the same wall that killed every cloud free tier. So the route is
  **bank account -> debit card -> Upwork**, which makes the outstanding bank-account
  action concretely valuable rather than abstractly prudent. Also: ~30% of new Upwork
  applications were rejected in 2025 and ID verification is mandatory, which sits
  badly with the "Shadow" pseudonym.
- **2026-08-06 — the card wall is NOT binding after all: Freelancer.com needs neither
  a card nor a bank account to start (B6).** Free to join, **6 free bids/month**, and
  the platform shifts its fee to the client at 3%. Verified demand by fetching its
  due-diligence board directly: **2 live jobs, $1,076 (24 bids) and $154 (15 bids)** —
  thin, but real budgets and real bidding, unlike PeoplePerHour's three mislabelled
  listings. **The bank account is needed when money lands, not to begin.** Upwork
  stays the better platform for later, once a card exists.
- **2026-08-06 — CORRECTION, and it changes the plan: Rushi placed bids on
  Freelancer.com and they were REJECTED on criteria.** I had inferred from a
  screenshot that he had not bid; that was wrong and stated as fact. The zero-review
  problem is no longer a risk, it is a **measured outcome**. With Fiverr abandoned
  and Upwork rejecting ~30% of new applicants, **the marketplace route is closed for
  now — not by choice.** The channel requirement is therefore concrete: **no
  gatekeeper.**
- **2026-08-06 — [B10](tickets/b10-build-what-rushi-builds.md): the offer pivots to
  what Rushi can actually build. Decided by him.** India dropped as the buyer market
  (no contacts), so **B9 is shelved, not deleted**. Every prior offer was research
  work he has no background in — an offer the principal cannot personally deliver is
  fragile. **But "web development" is refused as an offer**: most commoditised
  category there is, and the opposite of narrowing. **Proposed instead: "AI features
  that refuse to make things up, with a scored eval that proves it"** — built on the
  1,670 lines of tribunal and deterministic eval already in this repo. Keeps the
  differentiator, moves it onto work he can deliver.
- **2026-08-06 — [B11](tickets/b11-direct-outreach.md): direct outreach, first batch
  drafted.** Targeting rule that needs no scraping: **a live job posting is a public
  statement of need from an organisation with budget, published to attract contact.**
  Source: HN "Who is hiring?" (August 2026, 178 postings). Filtered for AI/LLM/eval
  **and** not US-only: **10 survive.** Two messages drafted — Railway (REMOTE
  worldwide) and Atria (Global Remote, Staff SWE Agentic AI). **Two, not twenty.**
- **2026-08-06 — most internationally-open AI roles are employment, not contract.**
  The angle that keeps it a customer relationship: a company advertising a senior AI
  role for weeks has the problem *now* and a hire who starts in three months, so a
  small scoped paid piece beats another CV. The messages are explicitly **not**
  applications, and state the India/timezone fact up front rather than hiding it.
- **2026-08-06 — one sendable target, not two.** **Railway has no email** — every
  role routes to an Ashby form, and hunting an address would be scraping by another
  name, so it is dropped. **Atria published `hackernewshiring@atria.org`** with
  "every resume sent here will be reviewed by a human". They asked for resumes, so
  the message opens by saying it is not one rather than ignoring their process.
  **Final message written; one send, then wait.**
- **2026-08-06 — FIRST PUBLIC ARTEFACT. The case study is live**, as a public gist on
  Rushi's own GitHub, on his explicit authorisation:
  [gist.github.com/rushikeshgoud19/8c2dd…](https://gist.github.com/rushikeshgoud19/8c2dd391d5545b4030d10f382d7ec0de).
  Verified readable logged-out. **Gist, not the repo** — `my Ai` holds `config.json`
  with API keys and must never be published. This unblocks
  [B11](tickets/b11-direct-outreach.md): both messages now carry a real link.
  **Outstanding: Rushi has not confirmed the technical claims are accurate**, and
  they are published under his name.
- ~~**2026-08-06 — B11 is blocked by the B10 publishing decision.**~~ The messages need
  two links, and the case study is not public anywhere Rushi controls. Publishing is
  now on the critical path rather than optional.
- **2026-08-06 — the portfolio piece already existed and was buried.**
  `docs/wayfinder/orchestra-accuracy.md` holds measured results — eval **15/16 ->
  15/15**, settled path ~2 calls/500 tokens vs contested ~11/6k, and the invented
  **"$0.25 per million tokens"** becoming **"could not verify a current figure"**.
  Written up as [`case-study-refusal.md`](demo/case-study-refusal.md). **This is the
  "criteria" evidence Freelancer said was missing** — a demonstration with a number,
  not a claim. Drafted, **unpublished**, awaiting Rushi.
- **2026-08-06 — dev boards have real volume but thin low-competition supply.**
  Freelancer: python 201 jobs, ML 36, AI 22 — versus 2 mislabelled under
  due-diligence. But 16 AI/dev candidates filtered for open + <=15 bids yielded
  **one**, and it was a teaching gig. Contract genAI rates are **$75-200+/hr** with
  evaluation expertise driving the top end — **but for demonstrated production
  experience**, which a repo is not.
- **2026-08-06 — the marketplace rejection may be category-specific, not general.**
  His bids were rejected for research and data jobs where he had no portfolio. **For
  development work he has a repo.** Worth retesting rather than generalising from one
  category. Flagged, not asserted.
- **2026-08-06 — [B9](tickets/b9-gst-vendor-checks.md) resolved: the GST filing data
  is public and usable, but NOT automatable by us — so it gets delivered by hand.**
  Official portal is CAPTCHA'd (not bypassed); knowyourgst's API carries registration
  details only, no filing history, and costs ₹2,500+; gstsearch is CAPTCHA'd; taxadda
  is rate-limited; legaldev exposes no endpoint. **But a CAPTCHA blocks automation,
  not the work** — a person reads the filing table in about a minute. For ONE customer
  that is the right shape, and manual effort is the input Rushi actually has. **Ceiling
  recorded: ~1 min/GSTIN, so small batches only**; scaling means a paid GSP API on his
  own account, never captcha evasion.
- **2026-08-06 — new frontier ticket, [B9](tickets/b9-gst-vendor-checks.md): GST
  vendor-compliance checks for Indian SMBs.** An Indian GSTIN can read **"Active"**
  while the vendor has not filed GSTR-1/3B for months — and the buyer silently loses
  input tax credit, plus interest and penalties. **That is the same product as
  [sample 3](demo/sample-report-3-uk.md)** ("Active" is the most misleading word on
  the record), with a domestic buyer, a rupee-denominated loss, no forex, no FEMA and
  **no gatekeeper**. **Not yet a pivot** — gated on whether the filing history is
  retrievable without bypassing a captcha.
- **2026-08-06 — the Freelancer.com account exists and the card wall was skippable.**
  Rushi is live at `@rushikeshg64`, balance ₹0.00. The "Add Verified Payment Method"
  step feeds the credibility badge, not bidding, and was bypassed via
  `/dashboard`. **First channel is open with no card and no bank account.**
- **2026-08-06 — GSTIN is not required (B7 gap closed).** The platform's TCS banner
  reads as compulsory and is not: **Notification 65/2017-Central Tax** exempts
  suppliers of *services* through an e-commerce operator from compulsory registration
  below ₹20 lakh. Decline the field; do not register.
- **2026-08-06 — a live buyer independently priced this offer at $30–250.**
  Freelancer.com carries "Business Ownership Verification Needed" — *"confirm that an
  individual truly operates the business they claim to run"* — at **$30–250 USD**,
  the exact band B2 and B3 reached separately. **Volume is in the general boards, not
  the category tag:** research 252 jobs, business-analysis 81, web-search 78, versus
  2 mislabelled jobs under due-diligence.
- **2026-08-06 — but a real share of verification jobs want a LOCAL human.** That
  Belgian job says "we need freelancer of belgium" — the site-visit component again.
  **Not our offer; do not bid.** Our slice is the remote desk portion for buyers who
  need triage. Belgium's official register responds, and was **deliberately not
  added** to the script — no customer has asked, and adding registers pre-demand is
  building ahead of the evidence.
- **2026-08-06 — the play is to bid with the work already done.** 24 bids per job is
  the real obstacle, not the fee, and a zero-review seller loses any credentials
  contest. `scripts/company_check.py` makes a real check cost about a minute, so the
  proposal can carry **an actual sourced finding about the buyer's actual company**.
  That converts "trust me" into "here is what I already found, free." Strongest use
  found for the automation.
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
