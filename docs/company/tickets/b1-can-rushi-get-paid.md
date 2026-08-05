# Can Rushi actually receive money?

`wayfinder:task` (HITL) · OPEN · **frontier — blocks everything**

## Question

There is no point building, pricing or selling anything until money can arrive.
Recorded constraint: Rushi has NO CREDIT CARD, which already ruled out every cloud
free tier requiring card verification (`mizune-free-infra`). Receiving money is a
different problem from spending it, and needs checking rather than assuming.

Establish, concretely:

- What payment rail can a student in Hyderabad actually use to invoice and be paid?
  Razorpay / Cashfree / Stripe India / PayPal / direct UPI + bank transfer. Which
  require a registered business, and which accept an individual with PAN + bank
  account?
- **International vs domestic changes everything.** A foreign customer paying into
  India is a different compliance path (FIRA/FIRC, purpose codes, higher fees) than
  a local business paying by UPI. Which is pursued FIRST changes the offer itself.
- Is a business registration needed to invoice legally, or does an individual
  invoice with PAN suffice at small volumes?
- GST: what turnover threshold triggers registration, and does it differ for
  domestic services versus exports?
- What does Rushi already have — bank account, PAN, UPI, any existing payment app?

## Input from B8 (2026-08-05)

The crypto shortcut is closed. Taking USDC from a foreign buyer for exported
services appears to breach FEMA — no FIRC/e-FIRA is generated and s.13 exposure is
up to 3x the amount. So the "international" leg of this ticket means real inward
remittance through an authorised dealer bank, or it means nothing. A domestic
customer paying by UPI sidesteps FEMA entirely and is the cheaper first target.
Detail and sources in `b8-clustly-as-first-channel.md`.

## Finding 2026-08-05: FamPay is not a rail. Ticket stays OPEN.

Rushi says he has FamPay. It cannot be the destination on an invoice, for three
reasons, from the operator's own Terms of Use
([Triotech, FamPay Terms of Use v3.3, PDF](https://triotech-website.s3.ap-south-1.amazonaws.com/public/FamPay+TT+-+Terms+of+Use.pdf)):

1. **It is a wallet, not a bank account.** "Triotech issues the pre-paid payment
   instruments ("PPI(s)") offered to you through the Platform" under the RBI PPI
   Master Directions. A PPI has no account number and IFSC, so there is nothing to
   put on an invoice for a customer to pay into.
2. **Commercial use is prohibited outright.** Clause 22.2: *"No commercial usage:
   You shall use the Services only for your lawful and personal use."* Taking client
   money for automation work is commercial use. Clause 6.1.3(ii)(b) lets Triotech
   suspend or discontinue the wallet "for any violation of these Terms" — i.e. the
   downside is the account holding the money getting frozen.
3. **The limits do not fit even if it were permitted.** Small PPI wallet: ₹10,000
   balance cap, ₹10,000/month and ₹1,20,000/year load cap, and *"Cash withdrawal or
   funds transfer from the Small PPI Wallet shall not be permitted"* — money in,
   never out to a bank. Full-KYC wallet: ₹2,00,000 cap, and funds can move "to your
   own bank account (after verification)" — which presupposes the bank account the
   wallet was supposed to replace.

**The real open question this surfaced: how old is Rushi.** The FamPay terms treat
under-18s as "Minors" who cannot accept the terms themselves; a Parent accepts and
takes responsibility (cl. 2.3). More importantly, under **s.11 of the Indian
Contract Act, 1872** only persons aged 18+ are competent to contract, and an
agreement with a minor is void *ab initio* per *Mohori Bibee v. Dharmodas Ghose*
(1903) — see [SCC Online](https://www.scconline.com/blog/post/2026/06/06/cases-that-made-law-minor-entering-into-binding-contract-mohori-bibee-dharmodas-ghose-explained/),
[iPleaders](https://blog.ipleaders.in/section-11-of-indian-contract-act-1872/).
If Rushi is under 18, he cannot form a binding service contract in his own name, and
the whole shape of B1 (and of the offer) changes. **Asked; awaiting answer.**

Caveat: s.11 makes the agreement unenforceable, it does not make getting paid
impossible in practice — small prepaid work with no contract is a different risk
profile from an invoiced engagement. But it is not something to discover with a
customer waiting.

## Why this is first

Every other ticket is wasted work if the answer turns out to be "he cannot be paid
without a registered entity, and that takes six weeks". Sequencing this first is
the difference between learning that now and learning it with a customer waiting
and a deadline.

## Claude does / Rushi does

Claude researches the options and produces a comparison with the actual
requirements and fees. **Rushi** does anything requiring identity: opening
accounts, uploading documents, accepting terms. Claude will not create a payment
account or handle personal or financial details, so this ticket resolves with a
checklist for Rushi — not with an account.

## Done when

The map records: the chosen rail, what it requires, what Rushi still has to do
himself, and whether an invoice can legally be issued today.
