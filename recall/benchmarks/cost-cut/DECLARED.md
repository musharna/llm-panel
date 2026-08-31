# Cost-efficiency cut — declared 2026-08-31 before computation

Descriptive; no hypothesis test. Decides what the recall results mean for the product
default (`--prompt-style defect`), given that `volume` is the defect prompt word-for-word
plus an exhaustiveness clause — so "switch the default to volume" is the live question.

## Data (all pre-existing; no new panels, no new evaluator passes)

The two n=35 runs (`results-human-2arm`, codex transport in the gpt slot;
`results-human-2arm-orgpt`, all-OpenRouter) x two arms. Scores:
`scores/human-{broad,volume}-pos.json`, `scores/human-orgpt-{broad,volume}-pos.json`.
Costs and wall: each result's `rundir`/run.json (judges[].cost, judges[].secs).

## Declared quantities per run x arm

1. findings, all-ref matches (of 446), human-ref matches (of 150); recall %.
2. **precision** = all-ref matches / findings.
3. **attention cost** = findings per all-ref match (the number a reviewer reads per
   benchmark-validated hit). The roster is 2/3 free models, so reviewer attention — not
   dollars — is the product's scarce resource.
4. gpt-slot dollars: sum of judges[].cost over the panels behind the result files
   (success-panel spend; the orgpt run's attempt-inclusive total $8.02 is already in its
   README). codex-run gpt-slot cost is subscription quota, reported separately, never
   summed with billed.
5. panel wall = per-panel max judge secs, summed per arm.

## Declared read (before numbers)

- Switching the default defect -> volume is supportable only if volume's precision is NOT
  materially below defect-style broad-arm precision AND its attention cost per validated
  hit is no worse. If volume's extra recall arrives at proportionally more findings
  (precision flat or lower), the recall gain is pure verbosity and the house default
  stands — nitpick noise is the cost the default was chosen to avoid.
- Context, not recomputed: on the 20-PR benchmark the volume arm ran 235 findings at 15.3%
  precision vs broad 243 at 13.2% (root README); defect house style 10.6% recall.
- Variance floor from perjudge35 applies: per-run human-ref differences under ~5 matches
  are re-run noise; the all-refs volume>broad effect (p=.002) is the load-bearing recall
  input to this decision.
