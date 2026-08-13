# Grounding reads search snippets, never the page

`wayfinder:task` · **CLOSED** · blocked by: A1 (closed)

## Question

`gather_grounding` built the entire reference block from search-result
DESCRIPTIONS, capped at 900 chars across three hits, while every backend returned
a `url` that nothing ever opened. Four advocates and a judge argued from
search-engine blurb.

## Resolution

`fetch_page(url, terms)` in `orchestra_tools`, obeying the module rule that losing
search must degrade the answer and never break the debate:

- scheme check, `Content-Type` must be html or text/plain (a PDF decodes to noise
  that looks like text to a model), a 400KB read cap and a 6s timeout;
- `<script>/<style>/<svg>` blocks dropped before tag stripping;
- **`_best_window`** picks the `width` characters densest in the question's own
  terms, weighted slightly toward digits. Naive truncation returns a page's
  navigation and cookie banner; the fact wanted is usually in a table halfway down.
  Verified on a synthetic page with a price line buried in 100 nav and 100 footer
  tokens - the window lands on the price line.
- any failure returns "" and the caller keeps the snippet it already had.

`max_chars` 900 -> 1500. That block is read by five advocates and twice by the
judge, so each character is paid for seven times; 1500, not 5000.

**All three hits are fetched, and the budget is filled BEST-FIRST rather than in
search order.** The first cut fetched only the top two, on my assumption that the
third hit never carries the answer. Measured immediately after: for this question
marginalia ranked a company-valuation article first and a vendor directory second,
while the hit actually titled "Pricing" came third - so the fetch got two pages
that could not answer and skipped the one that could. Search rank answers "what is
about this topic", not "what contains this fact". Chunks are now ordered by term
and digit density.

## Verification

Guards: non-http rejected, dead host returns empty, a PDF URL rejected on
content-type, a real page fetched in 0.6s.

**Eval 15/15, triage 7/7, grounded 4/4 — no regressions.** Whole suite in 2m53s.
Page fetching added roughly 3k tokens across 15 questions.

The machinery demonstrably works: the block now contains real pricing tables with
real per-million-token figures, where before it held a sentence about a funding
round.

## What it did NOT fix, and why that is the right outcome

Probe 2 still answers "could not verify a current figure for ministral-8b". The
block after fetching holds three pages of genuine pricing data - and none of it is
Mistral's:

- `[AI Service Providers]` - OpenAI and Pixtral rates
- `[Pricing]` - a DIFFERENT vendor's page (MADLAD400, GPT-J, Llama3, in "credits")
- the valuation article

**mistral.ai is never in the results.** So refusing is correct: the panel had three
pages of plausible per-million-token numbers in front of it and declined to pass
any of them off as Mistral's. Had it answered "0.20 credits per million tokens"
with a citation, that would have been a worse failure than the original
fabrication, because it would have been sourced.

Retrieval, not reading, is now the limit. That is
[Prefer sources that can actually carry the fact](a5-source-authority.md), which
this ticket has now armed with a concrete case: the primary source exists at a
guessable URL and the free backends do not surface it.
