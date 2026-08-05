# What are people actually paying for, at what price?

`wayfinder:research` · **PARTIAL 2026-08-05 — blocked on data access, not on B1**

## Question

Not what YouTube says the market is — what live listings, marketplaces and job
boards show people actually paying for right now.

Sources that show real transactions rather than claims:

- Upwork / Fiverr: live gigs for automation, n8n / Make / Zapier builds, AI agents.
  What is the median price of a *completed* order, not the headline rate?
- Template and workflow marketplaces — do they sell, at what price, how often?
- Job boards and founder communities: which problem is stated over and over?

Answer specifically:

- Which tasks recur often enough to productise rather than build bespoke?
- What is the realistic price band for a first sale with no track record and no
  reviews?
- Where does "grounded, checked output" command a premium, and where is it
  irrelevant? Nobody pays extra for citations on a Slack notification bot. Somebody
  might pay a lot for it on anything touching numbers, suppliers or compliance.
- What do these buyers already complain about in reviews? That is the wedge.

## The bias to guard against

This ticket is trivially easy to answer with a fluent summary that was never
checked, and that answer would be worse than none. Every claim in the resolution
names the listing or page it came from, and **a price with no source does not go
in**. The entire grounding effort in `docs/wayfinder/` exists because a confident
unsourced number is the failure mode of this exact kind of research.

---

## Partial resolution — 2026-08-05

**This ticket cannot be answered to its own evidence standard with the access I
have.** Recording that plainly instead of producing the fluent summary the section
above warns about.

### What blocked it

Three of the four named sources are unreachable:

| Source | Result |
|---|---|
| Fiverr | HTTP 403 to fetch; the browser got a bot-detection interstitial (`ERRCODE PXCR10002539`). **Not bypassed** — defeating CAPTCHAs is out of bounds, and this is exactly a case where working around the block would be the wrong instinct. |
| Upwork | Cloudflare challenge (`Ray ID a261c8f10b959a96`) on both fetch and browser. |
| Reddit (r/n8n) | Fetch refused; `old.reddit.com` blocked by policy in the browser pane. |

That leaves search-engine snippets and blog content. Blogs are the exact source
class this ticket exists to avoid.

### What IS verified

**Entry prices for n8n/AI-automation gigs on Fiverr cluster at $50–$125.** These
come from Fiverr's own listing-title format ("I will … **for $80** on fiverr.com")
surfaced in search results, across ten distinct sellers: $50, $50, $50, $80, $80,
$80, $90, $110, $125. The band is consistent enough to rely on.

Two important limits on that number:
- These are **starting prices on listings, not completed-order values.** The ticket
  asked for the median price of a *completed* order. That is behind the block.
- Individual seller-to-URL pairings in those results were internally inconsistent
  (a title advertising n8n work pointing at a Flutter gig URL), so the *band* is
  usable and any *single* citation is not.

**Some sellers in this category have 400–500 reviews**, which would indicate real
completed volume — but the review counts came back unattributed to specific
sellers, so this is noted and **not relied on**.

### What is NOT verified, and was wrongly easy to believe

- "$800–$3,500 for a Zapier→n8n migration" ([LearnForge](https://learnforge.dev/blog/sell-n8n-automation-upwork/)),
  "$75–$95/hour after five reviews", "$100–$150/hour for senior specialists"
  ([ai-agentsplus](https://www.ai-agentsplus.com/blog/ai-agent-freelance-rates-2026)).
  These are content marketing for automation courses and agencies. Plausible,
  unverifiable, and **excluded from any pricing decision**.
- Indian enterprise RPA case studies (₹15 lakh implementation, ₹48.5 lakh annual
  benefit — [Pazy](https://www.pazy.io/blogs/invoice-automation-guide)) are vendor
  marketing and describe a buyer three orders of magnitude away from customer #1.

### The finding that matters more than the price band

**I found no evidence of Indian SMBs buying automation *services* at any price.**
Searching the Indian market returned two things and nothing between them: automation
*tool* pricing (n8n Cloud at roughly ₹1,700–₹4,200/month —
[productgrowth.in](https://productgrowth.in/tools/automation/n8n/)), and enterprise
RPA implementations at ₹15 lakh. The ₹5,000–₹50,000 service sale that customer #1
would be is absent from the search record entirely.

That is **absence of evidence, not evidence of absence** — my Indian-market searches
were shallow and the segment may simply not blog about what it buys. But it sits
badly against B1.

### This conflicts with B1, and B1 may be wrong

B1 concluded domestic-first on cost and compliance grounds: zero fees, no FEMA
surface, instant settlement. That reasoning stands on its own terms. But it assumed
a domestic buyer exists, and B2 could not find one, while the demand it *could* see
($50–$125 Fiverr gigs) is dollar-denominated and overwhelmingly not Indian.

If that holds, **B1 optimised the payment rail and ignored the market.** A 2% fee
and a FIRA per invoice is a trivial price for selling into a market that exists,
versus zero fees selling into one that may not. The bank account is required either
way, so nothing about "domestic-first" is actually cheaper in effort.

**Not overturning B1 on this.** The evidence is too thin — three blocked sources and
a shallow Indian search is not grounds to reverse a resolved ticket. Recording it as
a live risk with a stated trigger: **if the Indian-buyer question cannot be answered
by talking to two or three real Indian businesses, B1's domestic-first call should be
reopened rather than defended.**

### What would actually resolve this

Not more searching. The three sources that would settle it are blocked, and the
fourth — asking buyers — is the one that was always going to give the real answer.
"What will you pay for" is a question with exactly one reliable source: someone who
might pay.

This is the point in the map where the work stops being research and starts being
contact with a potential buyer. That needs Rushi, it needs an offer to describe
(B3), and every message needs his approval before it goes anywhere.
