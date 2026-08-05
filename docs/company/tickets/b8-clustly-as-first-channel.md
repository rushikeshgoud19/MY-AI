# Is Clustly a viable first channel?

`wayfinder:research` · **RESOLVED 2026-08-05 — NO** · related to: B1 (payment), B6 (outreach)

## Question

`clustly.ai/operator` is a marketplace for hiring AI agents: work is escrowed,
released on approval, 4% flat fee, paid in **USDC on Solana**, with an Agent API,
SDK/CLI and an MCP server for listing an agent.

It is attractive for one specific reason: **it removes outreach entirely.** Buyers
arrive, escrow protects both sides, and receiving USDC needs no credit card — the
exact constraint that killed every cloud free tier.

Two things decide whether it is usable, and both are checkable:

**1. Does it have real demand?** A marketplace with no buyers is worse than no
channel, because it costs a week to find that out. Look for: number of live
listings, evidence of completed jobs, how old the platform is, who is behind it,
whether the changelog and status page show an active product or an abandoned one.
Do not accept the landing page's own framing as evidence of liquidity.

**2. Can Rushi legally convert USDC to INR without a tax problem?** India taxes
Virtual Digital Asset gains at a flat 30% with a 1% TDS on transfers, and the
reporting is not optional. Confirm the current rules, what a receipt in USDC counts
as for income tax when it is payment for services rather than an investment, and
whether that makes the effective take-home materially worse than a plain UPI
invoice.

## Why it matters beyond itself

If the answer is yes, the outreach ticket may shrink to nothing and the payment
ticket has an answer that needs no registered entity. If the answer is no, it is
one afternoon spent and the map is unchanged. Either outcome is cheap, which is why
this is worth doing early.

Sources named for every claim, per the map's Notes — the whole point of Groundtruth
is not repeating the thing we spent a week eliminating from the tribunal.

---

## Resolution — 2026-08-05: NO, on two independent grounds

Either one is sufficient to rule it out. Both are true.

### 1. There is no demand. The platform publishes the number itself.

Clustly's own homepage carries a live counter reading:

> `147 services live · $1,950 settled on-chain`

Verified by fetching the raw HTML of `https://www.clustly.ai/` on 2026-08-05 and
grepping for the string, not by reading a summary of the page. It appears twice —
once in the rendered banner (`class="tabular-nums"`) and once in the page's
`<meta>` description.

That is **$1,950 total, lifetime, across the whole marketplace**, against 147 live
listings. Average lifetime revenue per listed service is **$13.27** (1950 ÷ 147 —
arithmetic checked). Capturing 5% of every dollar the platform has ever settled
would pay Rushi about $97, before the 4% fee.

Context for how young that number is: Clustly was built for the Colosseum Solana
Frontier hackathon, which ran **6 Apr – 11 May 2026**, with winners announced
**26 June 2026** ([Colosseum](https://blog.colosseum.com/announcing-the-winners-of-the-solana-frontier-hackathon/)).
It won the Singapore championship, reported 29 May 2026
([KuCoin](https://www.kucoin.com/news/insight/SOL/6a195a7fea4a6c0007f90ba8)).
So $1,950 is roughly four months of trading. This is a promising infrastructure
project with a real on-chain escrow program — it is not a place where buyers are
currently arriving with money.

The ticket asked us not to accept the landing page's framing as evidence of
liquidity. In the end the landing page's own number is the evidence against it.

**Unknown / not verified:** whether the $1,950 counter is lifetime or a rolling
window (the docs do not say), and whether it counts gross or net of the 4% fee.
Neither reading changes the conclusion — a rolling-window reading would make it
worse, not better. The `clustly-escrow` Solana program ID is not published in the
docs, so the figure could not be checked independently on-chain. That is the one
audit we would have wanted and could not run.

### 2. Being paid in USDC for exported services appears to violate FEMA.

This is the harder blocker, and it is **not the problem the map predicted.**

The map assumed the risk was tax: "India taxes virtual digital assets at a flat 30%
plus 1% TDS," framed as a take-home-pay problem. That framing is wrong in both
directions.

- **The 30% is smaller than assumed.** USDC received as payment for services is
  business income at INR fair market value on the day of receipt, taxed at normal
  slab rates. The 30% under s.115BBH applies to the *gain* on the later conversion
  to INR — and for a stablecoin converted promptly, that gain is approximately
  zero. ([Karbon](https://www.karboncard.com/blog/blockchain-stablecoins-legal-india-freelancers):
  "the INR fair market value upon receipt is business income, and later conversion
  gains or losses are taxed at 30% under VDA rules"; 1% TDS under s.194S applies to
  transfers above ₹50,000 / ₹10,000 depending on payer class —
  [CoinDCX](https://coindcx.com/blog/cryptocurrency/crypto-tax-guide-india/).)

- **But the real blocker is foreign exchange law, not income tax.** Export of
  services out of India must be paid for in convertible foreign currency through an
  authorised dealer bank. Crypto is not currency under FEMA, so a USDC receipt from
  a foreign buyer does not satisfy that condition and generates no FIRC / e-FIRA —
  the mandatory proof of export proceeds. Karbon states it flatly: *"No e-FIRA or
  FIRC is issued... Crypto transfers are outside the banking system, so no e-FIRA
  will be generated."*
  [SolvLegal](https://solvlegal.com/blogs/accepting-crypto-payments-from-foreign-clients-what-fema-allows/)
  puts the exposure at FEMA s.13: penalties up to **3x the transaction amount**,
  minimum ₹2,00,000 where unquantifiable, ₹5,000/day continuing, Enforcement
  Directorate action, plus loss of GST export zero-rating and possible bank account
  freezing. It grounds the "not currency" point in the RBI's position that virtual
  currencies "as a medium for payment, are not authorized," and cites
  [Lakshmikumaran & Sridharan](https://www.lakshmisri.com/insights/articles/trading-in-virtual-currencies-an-analysis-under-foreign-exchange-laws-of-india/)
  for VDAs not being currencies under FEMA.

**Confidence, stated honestly.** These are law-firm and fintech blogs, not RBI
circulars or FEMA notifications read in the original. Three independent sources
agree, and none dissent, but this has **not** been confirmed against primary law or
a chartered accountant. That is enough to stop: the downside is a 3x penalty and a
frozen bank account on a first sale worth perhaps ₹10,000, against an upside of
being listing #148 on a marketplace that has settled $1,950. Asymmetric, so we do
not proceed. To overturn this you would need a CA's written opinion on FEMA s.7/s.8
for a resident individual receiving stablecoin consideration for exported services.

### What this changes elsewhere

It does **not** open a new ticket. B1 already asks the right question — "international
vs domestic changes everything... Which is pursued FIRST changes the offer itself" —
and B8 has now pre-loaded it with an answer: **the crypto-rail route to international
customers is closed, so B1's international leg means real banking rails
(FIRC-generating inward remittance) or it means nothing.** A domestic Indian
customer paying by UPI avoids FEMA entirely and is the cheaper first target.

Cost: one session, no money, no accounts opened.
