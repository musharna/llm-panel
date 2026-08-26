# What each AACR reference comment ASKS FOR — RETRACTED 2026-08-26

**Do not quote the split below.** The classifier shares its definition with the prompt it
was used to evaluate ("concrete failure scenario" appears verbatim in both), so a reference
the panel matched is a reference the classifier calls DEFECT. On AACR's own `category`
field the `defect` prompt recalls defect-type and maintainability references at the same
rate (10.3% vs 11.1%, p = 1.0). The full retraction, with the mechanism and the corrected
numbers, is in `../results-broad-3judge/README.md`. The labels in this directory are kept
as the record of what was measured; the second section (category does not predict
acceptance) rests on the same labels and carries the same caveat.

`aacr-classify-refs` labels every reference comment DEFECT (reports something wrong, with a
concrete failure scenario) or IMPROVEMENT (worth raising but not yet incorrect: dead code,
naming, missing validation, duplicated state, clarity, refactors, docs).

Classified by the same judge family used for scoring. A keyword list cannot answer this --
"manualOutputDir is created but never used" contains no defect vocabulary and is a valid
review comment; "Type Safety Improvement" contains "safety" and is a suggestion.

## Why it exists

The pooled recall figure hid a split that turned out to be the whole story:

| reference asks for | refs | semantic recall (clean 3-judge, defect prompt) |
| ------------------ | ---: | ---------------------------------------------: |
| DEFECT             |   65 |                                      **18.5%** |
| IMPROVEMENT        |   58 |                                       **1.7%** |

Fisher exact two-sided **p = 0.0025**.

47% of the benchmark's valid comments are the improvement classes, and the `defect` prompt
tells judges "do not propose refactors" and demands "a concrete failure scenario". So the
pooled 10.6% was measuring the instruction, not the panel.

Quote the scoped number with its scope -- 18.5% on defect-type references -- rather than a
pooled figure whose denominator is half out of scope by construction.

## Category does NOT predict acceptance

I expected the REJECTED comments to be disproportionately nitpicks, which would have made
"only report defects" a cheap proxy for "only report what reviewers accept". It is not:

| references                 | DEFECT | IMPROVEMENT |
| -------------------------- | -----: | ----------: |
| accepted (positive sample) |    55% |         45% |
| rejected (negative sample) |    49% |         51% |

Human reviewers rejected confident defect claims at about the same rate as improvement
suggestions -- "The code incorrectly attempts to parse the conditions property expression
string as JSON" is a rejected DEFECT. So acceptance turns on whether the specific claim is
right and useful, not on which category it falls in, and narrowing the prompt to defects
buys less precision than it costs recall.

## Regenerate

    JUDGE_BASE_URL=https://openrouter.ai/api/v1 JUDGE_API_KEY=$OPENROUTER_API_KEY \
    JUDGE_MODEL=anthropic/claude-opus-4.5 \
    ~/aacr-bench/.venv/bin/python recall/aacr-classify-refs out.json

It refuses to write if any classification call errors, for the same reason `aacr-score`
refuses a dead judge: a failed call would otherwise land as a silent category.
