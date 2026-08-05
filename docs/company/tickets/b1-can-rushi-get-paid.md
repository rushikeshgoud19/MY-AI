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
