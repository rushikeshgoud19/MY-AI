# Can Rushi actually receive money?

`wayfinder:task` (HITL) · **RESOLVED 2026-08-05 — yes, domestic** · one action left for Rushi

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

---

## Resolution — 2026-08-05

**Known inputs (from Rushi, 2026-08-05):** age 19, PAN card yes, savings bank
account **no** — "waiting for the right time". No credit card. No business
registration. FamPay only, which is ruled out above.

### Answer: yes, and the rail is boring on purpose

**Chosen rail: UPI / IMPS straight into a savings account in Rushi's own name,
against an individual invoice carrying his PAN. No gateway, no GST, no company.**
Fee: zero. Onboarding: none. Settlement: instant.

Everything below is why the fancier options lose.

### Can he legally invoice today? Yes — nothing needs registering.

An Indian freelancer is a sole proprietor by default; the proprietorship exists the
moment he takes on a client and needs no registration to issue a valid invoice
([Riffit](https://www.riffit.in/blog/do-freelancers-need-to-register-a-business-india)).
An invoice with no GSTIN is valid: legal name, address (city + state minimum),
sequential invoice number (INV-001…), client name and address, description of
services, and PAN. No CGST/SGST/IGST breakdown, no HSN/SAC, no GSTIN field
([Riffit](https://www.riffit.in/blog/invoice-without-gst-number-india),
[JetInvoice](https://jetinvoice.in/blog/how-to-create-an-invoice-without-gst-in-india)).

**GST: not required.** The registration threshold for *services* is ₹20 lakh of
aggregate annual turnover, uniform and unconditional — the ₹40 lakh figure applies
to goods only ([Tally](https://tallysolutions.com/gst/gst-limit-registration-threshold-india/),
[CalcGuru](https://calcguru.in/gst-registration-threshold-20-40-lakh/)). Telangana
is not a special-category state, so ₹20 lakh applies, not ₹10 lakh. Customer #1 is
nowhere near this. **Note for later:** aggregate turnover includes exports, so
going international does not dodge the threshold, it fills it faster.

**TDS will bite, and it is not a loss.** An Indian *corporate* client must deduct
10% TDS under s.194J on professional fees above ₹30,000 per contract or ₹1 lakh per
year ([myhq](https://myhq.in/guides/gst-for-freelancers)). On a ₹10,000 invoice from
a company, ₹9,000 arrives and ₹1,000 is credited against his tax, reclaimed at ITR.
Individual and small unregistered clients generally do not deduct. This is a
pricing and cashflow fact, not a blocker — noted into B3.

### Why domestic, and it is not close

| | Domestic (UPI → savings a/c) | International (Skydo / Wise / Payoneer) |
|---|---|---|
| Fee on a $1,000-equivalent | **₹0** | Skydo $19 (1.9%), Wise $19–21.50, Payoneer $20–30 (2–3%) |
| Compliance surface | none | FIRA per payment, purpose codes, 15-month realisation window |
| Needs a bank account | yes | yes — *also* yes |
| Speed | instant | days |
| Buyer pool | smaller | larger |

Fee figures from [Skydo](https://www.skydo.com/blog/payoneer-vs-wise%E2%80%8B);
FEMA obligations from [Wisemonk](https://www.wisemonk.io/blogs/rbi-rules-for-indian-freelancers).
Note Skydo is a competitor to Wise and Payoneer and is the source for their fees —
directionally consistent with [xFlow](https://www.xflowpay.com/blog/skydo-vs-wise)
but treat the exact cents as indicative, not audited.

The decisive column is the third one: **every international rail still requires the
savings account he does not have.** International is strictly domestic plus fees
plus FEMA paperwork. There is no version of "start international because it is
easier". Combined with B8 having closed the crypto shortcut, the sequencing is
forced: **domestic first, international only once there is a repeatable offer.**

If and when international does happen, the shortlist is Skydo or Winvesta (flat fee,
free FIRA auto-issued) over Payoneer (2–3%, FIRA is documentation not automatic) and
PayPal (most expensive). Wise caps India invoice payments at $10,000 and supports
sole proprietors but not registered companies. Not decided here; revisit at that time.

### Payment gateway: not needed for customer #1

Razorpay does onboard individuals and unregistered freelancers, unlike Stripe India
which requires a registered business
([Razorpay](https://razorpay.com/freelancer-individual-business/)). Worth having
later for payment links and cards. For one customer paying one invoice, a gateway
adds ~2% and an onboarding step to solve a problem UPI already solves for free.
**Ruled out for now, not ruled out forever.**

### The one real constraint: savings account, not current account

Banks' standard position — and the consensus of the freelancer-banking write-ups — is
that savings accounts are for personal transactions and business receipts belong in
a current account, with practical guidance to switch above roughly ₹50,000/month of
inflow, or on GST registration, to avoid freeze risk
([MoneyMattr](https://moneymattr.com/current-account-vs-savings-account-for-indian-freelancers/),
[Karbon](https://www.karboncard.com/blog/best-banks-for-indian-freelancers)).
**Not verified against the RBI KYC Master Direction itself** — this is blog
consensus and bank T&Cs, not primary law read in the original. For customer #1 at
a few thousand rupees it is a non-issue; it becomes real at scale, and the trigger
to revisit is ₹50,000/month.

### What Rushi has to do — the whole list

1. **Open a savings account in his own name.** This is the only blocking item and
   the only one nobody can do for him. Banks now open accounts online with Aadhaar
   + PAN and a 5–10 minute video KYC, issuing account number and virtual debit card
   immediately; several offer zero-balance variants
   ([Lemonn](https://lemonn.co.in/blog/banking/online-account-opening-step-by-step-guide-in-india-2026/),
   [GoodReturns](https://www.goodreturns.in/classroom/how-to-open-a-savings-bank-account-in-india-in-2026-documents-eligibility-full-process-step-by-step-1491269.html)).
   Prerequisite: **Aadhaar linked to his mobile number**, or the OTP step fails.
   Which bank is his call — it is a personal financial decision with fee and
   minimum-balance consequences, and choosing one for him is not this ticket's job.
2. **Link a UPI ID to that account.** This is the thing that goes on the invoice.
3. **Do not route client money through FamPay.** Clause 22.2 prohibits commercial
   use; the wallet can be frozen for it, and it cannot pay out to a bank in the
   Small PPI form anyway.
4. **Nothing else.** No registration, no GST, no gateway, no accountant, until
   ₹20 lakh turnover or ₹50,000/month inflow.

### Not verified

- No primary law read: GST Act, RBI KYC Master Direction and s.194J were taken from
  tax and fintech write-ups that agree with each other, not from bare statute. Given
  four independent sources concur on the ₹20 lakh services threshold, the risk is
  low, but it is stated rather than hidden.
- Razorpay's individual-onboarding requirements come from Razorpay's own marketing
  page, not their KYC documentation. Irrelevant unless a gateway is adopted.
- **None of this is tested.** No account exists, no invoice has been issued, no
  rupee has moved. The first genuine test is customer #1 paying.

### Addendum: "can a wallet hold the money in the meantime?" — no, and here is why

Asked 2026-08-05. Checked across the wallet market rather than assuming from the
FamPay result, because the objection deserved a real answer.

**Every wallet's exit door is a bank account.** That is not a quirk of one product,
it is how PPIs are built:

- **Paytm Wallet no longer exists.** Wallet operations wound up on 15 March 2024
  with the Paytm Payments Bank action; after that date users could not top up or
  receive any credit other than cashbacks and refunds
  ([Business Today](https://www.businesstoday.in/personal-finance/news/story/rbi-faqs-on-paytm-know-bill-settlement-wallet-usage-rules-linked-to-paytm-payments-bank-after-march-15-417927-2024-02-17)).
  Paytm's own help page now states that money received via UPI or QR is credited
  **directly to your designated bank account**, not to a wallet
  ([Paytm](https://paytm.com/blog/paytm-help/how-to-receive-money-using-paytm/)).
- **PhonePe wallet → bank requires adding a bank account.** KYC alone is not enough
  ([ClearTax](https://cleartax.in/s/how-to-transfer-money-from-phonepe-wallet-to-bank-account)).
- **Minimum-KYC wallets are merchant-payment-only** — spend at shops, no withdrawal.
- **Merchant settlement is defined as bank settlement.** A PPI issuer moves collected
  funds from its escrow account to the *merchant's bank account*
  ([Razorpay](https://razorpay.com/learn/prepaid-payment-instruments-ppis/)).

So the best case a wallet offers is money he can *spend at merchants* and never move
out. Against the destination in the map — "money is in Rushi's account" — that is
not revenue, it is store credit. It also does not dodge the commercial-use clause;
consumer wallet terms restrict personal use generally, as FamPay's 22.2 does.

**The useful finding: what he is describing is a bank account.** The friction he is
avoiding — a branch, forms, a queue — is not what opening an account looks like now.
Jupiter, for example, is a **Federal Bank savings account** opened in-app with video
KYC, reported at around ten minutes, zero balance, DICGC-insured to ₹5 lakh,
requiring 18+, Indian resident, Aadhaar and PAN
([Jupiter](https://jupiter.money/savings-account/),
[BankKaro review](https://bankkaro.com/blog/jupiter-money-review/4653/)).
He is 19 with a PAN. HDFC InstaAccount, Kotak 811 and IDFC First advertise
comparable flows. **Not a recommendation of Jupiter specifically** — that is his
choice and the review mentions a credit assessment step I have not verified against
Jupiter's own terms — but it is proof that "app-based wallet-feeling thing" and
"savings account" are now the same ten minutes. There is no faster intermediate
step to take.

**Correction to what I wrote earlier today.** I put this at the top of the log as
*Blocked on Rushi* and called it the gate. That overstates it. B2, B3 and B5 —
research, offer, demo — need no bank account at all. The account is needed at
exactly one moment: when the first invoice goes out. "I'll get to it later" is
therefore fine, provided later is before that invoice. Downgrading from blocker to
prerequisite, and dropping it from the top of the log.

### Consequence for the rest of the map

The customer is now defined as **Indian and domestic**. That is an input to B2 (what
people pay for) and B3 (pick the offer), and it narrows both usefully — the question
is no longer "what will businesses pay for" but "what will an Indian SMB pay for, in
rupees, over UPI."
