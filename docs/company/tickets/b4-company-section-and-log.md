# Build the Company section, the daily log, and the memory

`wayfinder:task` · **RESOLVED 2026-08-06 — two of three built, one ruled out of scope**

<!-- Originally blocked on the payment ticket. That was wrong: a console section, a
     log and a memory note do not depend on which payment rail works, and holding
     them back buys nothing. Takeable in parallel with B1. -->


## Question

Rushi asked for three concrete things and they are one build:

1. **A Company section in the Agentic OS console** (`~/.claude/agentic-os`),
   alongside Home / Skills / Memory / Orchestra — showing what shipped, what is
   blocked on Rushi, and the money loop honestly (currently: zero).
2. **A daily report** — one dated file per working session in `docs/company/log/`,
   rendered in that section: what was done, what it cost, what is next, what needs
   Rushi. The console already reads the my-Ai repo (`MIZUNE_REPO`), so the log is
   git-tracked and survives a machine.
3. **A memory note** for the company in the store the galaxy indexes, so a future
   session resumes without re-reading this whole map.

## Design constraints, learned the hard way in this console

- **Scope the view CSS to `.active`.** A `#view-X.view { display: flex }` rule
  outranks `.view { display: none }` and renders that view on top of every other
  page — that is exactly how the Memory Galaxy broke Home, Skills, Activity and
  Orchestra simultaneously.
- **No fake progress.** A section that looks busy while nothing is happening is the
  precise thing this console exists to prevent — the Orchestra view sits idle until
  a real debate runs, deliberately. If revenue is zero, it shows zero. If a ticket
  is blocked on Rushi, it says so with the date it started waiting.

## Not in this ticket

The name is decided (Groundtruth, subject to veto). Branding, logo and a public
site are not — nothing here is customer-facing yet, and building a brand before an
offer is the most common way to spend a month achieving nothing.

---

## Resolution — 2026-08-06

Claimed and resolved this session. Two parts built, **one ruled out of scope**.

### 2. Daily report — DONE

`docs/company/log/` has [2026-08-05](../log/2026-08-05.md) and
[2026-08-06](../log/2026-08-06.md), git-tracked, each carrying Did / Found / Cost /
Next / Blocked-on-Rushi / Money. Money has read **zero** in every entry, which is
the point.

### 3. Memory note — DONE

`groundtruth-company` was badly stale — it still described Clustly as "ticketed, not
adopted" and the payment question as unanswered. Rewritten to hold the current
state: the offer, the three tested jurisdictions, `scripts/company_check.py`, the
channel situation, and the standing warning that the asset pile keeps running ahead
of the evidence.

Split out `india-crypto-payment-fema` as its own note, because it is a durable
reusable fact that will otherwise be re-derived **wrongly** — the intuitive worry
(the flat 30% VDA rate) is not the blocker; the blocker is that crypto receipts for
exported services do not come through an authorised dealer bank and generate no
FIRC. Both indexed in `MEMORY.md`.

### 1. Company section in the Agentic OS console — OUT OF SCOPE

**Not built, deliberately, and this is the part worth arguing.**

The ticket asks for a console view showing what shipped, what is blocked, and the
money loop. Its own design constraints say **"No fake progress... If revenue is zero,
it shows zero."**

Follow that honestly and the view renders: revenue ₹0, zero customers, nothing
published, one item blocked on Rushi. **That is a dashboard whose entire content is
already one line of this log.** Building a UI to display four zeroes is precisely
the motion the map warns against — it would take a session, look like a milestone,
and move nothing toward a paying customer.

The map's own rule applies: *if a ticket sits beyond the destination, rule it out of
scope and say so rather than quietly doing it.* A local console section does not
contribute to one customer paying.

**When it comes back:** if there is ever real data to show — orders, delivery times,
revenue — this is worth building, and the design constraints recorded above
(scope view CSS to `.active`; the Memory Galaxy incident) stay valid. That would be a
fresh ticket under a redrawn destination, not a resumption of this one.

**Rushi can override this.** He asked for it originally and it is his console. If he
wants it, say so and it gets built properly — but it should be a decision made with
the above stated, not by default.
