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

## Not yet specified

- ~~Whether Clustly settles both the payment question and the outreach question at
  once.~~ **Answered 2026-08-05: no, on both counts — see B8.** Note the assumption
  that failed: the worry recorded here was the 30% VDA rate hurting take-home. That
  was the wrong worry. The 30% applies to the *gain* on converting a stablecoin,
  which is near zero; the receipt itself is ordinary business income at slab rates.
  The thing that actually kills it is FEMA — export proceeds must arrive through an
  authorised dealer bank in convertible currency, and crypto does not.
- Whether the first customer should be **domestic (UPI, no FEMA exposure)** or
  international (real banking rails, FIRC). B8 closed the crypto shortcut, so this
  is now a live fork inside B1 rather than a hypothetical.
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
