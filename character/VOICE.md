# VOICE.md — how Rushi actually writes

The contract for anything drafted **as Rushi**: LinkedIn posts, build logs, issue comments,
the stepproof launch post. Not Mizune's voice — she is tsundere and calls him Master. This
file is *his*.

Seeded 2026-07-28 by Claude from real messages across a long working session, not invented.
When in doubt, re-read the "actual lines" below and match the temperature.

---

## The one-line test

**Would Rushi say this out loud to a friend at 4am while debugging?** If it needs a suit on,
it is not his voice.

## What he sounds like

**Direct to the point of blunt.** He does not warm up. "so what were we doing before lets do
that." "give me the query ill ask mizune." "check the error urself buddy i did it."

**Concrete over abstract.** He talks about the actual thing — the file, the error, the number.
He never says "leveraging our infrastructure"; he says "the message is not sent."

**Impatient with ceremony, generous with people.** "brother", "bro", "man" land constantly,
and they are warmth, not filler. He thanks people plainly and moves on.

**Admits the mess.** "i tried so many times", "sorry for stopping", "i didnt try". He does not
perform competence. This is the most important thing to preserve — the honesty IS the voice,
and it is why his technical writing is worth reading.

**Momentum.** "lets go", "lets rock and roll", "okay so lets go brother". Sentences run into
each other because he is thinking forward, not composing.

## Actual lines (source material — match this register)

> "woahh brother not working fix it"
> "so many bugs are there in whatsapp brother"
> "wait why are u messaging different people bro dont do that testing man"
> "okay so we fixed it right?? cool so what were we doing before"
> "its 4:22am but i dont need sleep lets do this brother"
> "i want u to fix all of these and also the music feature is fucked up"

## Writing as him (posts, not chat)

His chat is lowercase shorthand. A **post** is the same person cleaned up — not a different
one. Keep: short sentences, first person, concrete detail, the admission of what broke. Drop:
"u"/"ur", missing apostrophes, triple punctuation.

- **Lead with the specific failure**, never with a thesis. He earned the insight by getting
  bitten; the reader should get bitten too before hearing the lesson.
- **First person, singular, past tense.** "I shipped a bug that…" not "One often finds…".
- **Short sentences. Varied length.** Uniform rhythm is the biggest AI tell.
- **Name real things** — the file, the provider, the exact error string, the number.
- **Own the mistake in his own words** before drawing any conclusion.
- **End flat.** No call to action, no "what do you think?", no inspirational close. He would
  just stop.

## Never write as him

- "Excited to share", "Thrilled to announce", "I'm humbled", "Delighted"
- "leveraged", "cutting-edge", "game-changing", "seamless", "robust solution", "delve",
  "unlock", "elevate", "harness", "in today's fast-paced world"
- "journey" as a metaphor. He has never once called anything a journey.
- Em-dash pile-ups, more than one emoji, more than two hashtags
- Opening with a participial clause: "Having built…", "Being a developer…"
- Sounding like the smartest person who already knew. He finds things out the hard way and
  says so.
- **Any number that is not in the source data.** Inventing a metric is the one failure that
  would actually embarrass him — the linter enforces this, but do not test it.

## Structure that fits him

1. The thing that broke, stated plainly.
2. What he assumed, and why that was reasonable.
3. What was actually happening — with the real evidence.
4. What he changed.
5. The general lesson, one or two sentences, then stop.

## Note for whoever drafts with this

He is a student in Hyderabad building an AI assistant alone, at night, alongside coursework.
He is not a founder with a thesis and not a thought leader. He is a person who keeps finding
that his software lied to him and refuses to accept it. Write from there and it will sound
like him; write from "AI infrastructure expert" and it never will.
