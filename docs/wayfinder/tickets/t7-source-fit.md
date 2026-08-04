# Judge the fit between a claim and the source it cites

`wayfinder:grilling` · OPEN · graduated from fog by T4 · frontier

## Question

Fabricated citations are now caught deterministically, and real sources are
correctly attributed. What is NOT caught is a real, correctly-cited source that
cannot support the claim resting on it.

Two observed cases, both post-fix:

- Probe 2 grounded on a Mistral **funding/valuation article** and a generic "AI
  Service Providers" directory, and the panel read current per-token API prices
  off them.
- Probe 7 grounded on **7900XTX consumer-GPU local-inference forum notes** and
  Vanitas used them to argue about an API-based orchestra, concluding "cut costs
  by 80%". Correctly cited, entirely inapplicable. **The judge scored it 8.**

The prompt rule added in T4 ("judge the source, not just the number — a price from
a funding story is the defect even when the figure looks reasonable") did not fire
on that. So the question is not whether to add the instruction; it is there and it
failed.

Options to weigh:
- Sharpen the judge's rule with the worked examples above, rather than the
  abstract statement. The triage prompt only became stable once it had few-shot
  examples — same model family, same lesson.
- Score attribution as its own axis instead of folding it into one 0-10, so a
  well-argued answer on a bad source cannot score 8 on the strength of its prose.
- Put the source titles in front of the JUDGE explicitly. It currently sees the
  advocates' answers but is never shown the reference block, so it has no way to
  tell whether `[7900xtx LLM inference notes]` is a pricing page or a forum thread.
  **Check this first — if true, the judge was asked to assess fit while blind to
  the sources, and the other two options are premature.**
- Filter at fetch time: reject hits whose extract carries none of the fact-shape
  the query asked for. Cheapest to state, easiest to get wrong, and it would have
  discarded the good pricing hit in probe 2 as readily as the bad one.

Constraint: must not add a model call per advocate, and must not fire on the
settled path.
