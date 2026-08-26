# Broad prompt vs defect prompt — the same panel, asked a wider question

Everything is held equal except the prompt: same seed-42 sample, same three judges at
**full roster** (54/54 positive, 27/27 negative, zero degraded), same 900s timeout, same
extractor, same upstream evaluator, same judge model. `judge failures during scoring: 0` on
every arm. Binaries md5-pinned in `BINARIES.txt`.

`defect` = the house style: "REAL DEFECTS... a concrete failure scenario... do not propose
refactors". `broad` = what a careful maintainer would actually raise, defects plus dead
code, misleading names, missing validation, duplicated state, unclear logic, preventive
refactors.

|                  | refs | findings | line recall | **semantic recall** | precision |
|------------------|-----:|---------:|------------:|--------------------:|----------:|
| positive, defect |  123 |       79 |       21.1% |           **10.6%** |     16.5% |
| positive, broad  |  123 |      236 |       48.0% |           **26.0%** |     13.6% |
| negative, defect |   36 |       30 |       11.1% |                2.8% |      3.3% |
| negative, broad  |   36 |      155 |       44.4% |               16.7% |      3.9% |

## Recall by what the reference asks for

|             | refs | defect | broad | Fisher p |
|-------------|-----:|-------:|------:|---------:|
| DEFECT      |   65 |  18.5% | 35.4% |   0.047  |
| IMPROVEMENT |   58 |   1.7% | 15.5% |   0.016  |
| POOLED      |  123 |  10.6% | 26.0% |   0.0027 |

Broadening nearly doubled DEFECT recall as well, which was not the expectation -- the panel
got better at its own stated job, not only at the class it had been forbidden. Three tests
on one dataset: Bonferroni-adjusted the pooled effect holds (p=0.008), IMPROVEMENT is
marginal (0.049) and DEFECT alone does not clear (0.14). Treat pooled as established and the
split as suggestive.

## The cost, stated honestly

Signal-to-noise falls from **13:1** to **5.3:1** (valid matches against rejected-comment
matches). But that is a VOLUME effect, not a quality one: per finding, broad is no more
likely to repeat a comment human reviewers rejected -- negative-arm precision is 3.3% for
defect and 3.9% for broad, and the difference on the negative arm is not significant
(p = 0.107).

Upstream matches one-to-one, so 3x the findings mechanically permits more references to
claim a matcher. The volume-independent measure is precision, and it falls only slightly
(16.5% -> 13.6%). So the real statement is: **broad surfaces 2.45x more of what reviewers
actually flagged, at a slightly lower hit rate, and asks a human to triage 3x the output.**

## Which to use

This is a product decision, not a benchmark decision, and the benchmark cannot make it:

* A reviewer who will read everything gets materially more real findings from `broad`.
* A gate that must not cry wolf keeps `defect`, whose 13:1 ratio is much cleaner.

Both prompts ship (`--prompt-style`). The default stays `defect`, because refusing to emit
nitpicks is a deliberate choice with real value and this is one benchmark on 18 PRs.
