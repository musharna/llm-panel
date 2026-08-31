# Cost-efficiency cut — what the recall results mean for the default prompt

Declared before computation (`DECLARED.md`); all numbers from existing scores and run
records, no new panels or evaluator passes. Raw n=35 table in `table.txt`. 20-PR arm
identities were verified against each rundir's recorded prompt text, not the score
filename; the broad arm's 243 findings @ 13.2% reproduces the root README as a positive
control.

## The question

`volume` is the shipped `defect` prompt word-for-word plus an exhaustiveness clause, and
volume > broad on all references is the one recall effect that clears the variance floor
(95 vs 66 of 446, p=0.002). So: should the default become `volume`?

## Precision and attention cost, both benchmarks

Attention = findings a reviewer reads per benchmark-validated hit — the product's scarce
resource, since 2 of 3 roster slots are free models and the gpt slot is cents per PR.

| arm              | 20-PR: findings, prec, attn | n=35 codex-run   | n=35 or-gpt-run  |
| ---------------- | --------------------------- | ---------------- | ---------------- |
| defect (default) | 91, **16.5%**, 6.1          | not run          | not run          |
| broad            | 243, 13.2%, 7.6             | 738, 9.6%, 10.4  | 671, 9.8%, 10.2  |
| volume           | 392, **7.9%**, 12.6         | 1466, 5.5%, 18.1 | 1562, 6.1%, 16.4 |

Same ordering on every dataset and both transports: defect > broad > volume on precision,
reversed on reading load. The n=35 billed run also puts volume at ~35% more gpt-slot spend
($6.25 vs $4.61 for 35 panels) and ~1.5x the panel wall time (4.5 h vs 3.0 h summed).

## Read (per the declared rule)

**The default stays `defect`.** Volume's recall gain arrives at proportionally more
findings — precision roughly halves against broad and falls to ~half-to-a-third of the
house style — which is the definition of pure verbosity, and verbosity is the cost the
default was chosen to avoid. `--prompt-style volume` remains the right tool when recall is
worth any reading load (an audit before a release), and that is a per-run choice, not a
default.

The interesting margin is not volume but **broad**: on the 20-PR benchmark it doubles
recall (12.2% -> 26.0%) for a 25% rise in per-hit reading (6.1 -> 7.6) and a modest
precision dip (16.5% -> 13.2%). If the default ever changes, the candidate is
defect -> broad; it was outside this cut's declared question and would deserve its own
pre-registered comparison against defect at n >= 35 — sized against the variance floor
(`../results-human-2arm-orgpt/perjudge35/`), which puts panel-level all-refs effects under
~15 matches inside re-run noise.
