# Build the Company section, the daily log, and the memory

`wayfinder:task` · OPEN · **frontier — not blocked**

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
