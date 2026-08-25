# What each AACR reference comment ASKS FOR

`aacr-classify-refs` labels every reference comment DEFECT (reports something wrong, with a
concrete failure scenario) or IMPROVEMENT (worth raising but not yet incorrect: dead code,
naming, missing validation, duplicated state, clarity, refactors, docs).

Classified by the same judge family used for scoring. A keyword list cannot answer this --
"manualOutputDir is created but never used" contains no defect vocabulary and is a valid
review comment; "Type Safety Improvement" contains "safety" and is a suggestion.

## Why it exists

The pooled recall figure hid a split that turned out to be the whole story:

| reference asks for | refs | semantic recall (clean 3-judge, defect prompt) |
|--------------------|-----:|-----------------------------------------------:|
| DEFECT             |   65 | **18.5%** |
| IMPROVEMENT        |   58 | **1.7%**  |

Fisher exact two-sided **p = 0.0025**.

47% of the benchmark's valid comments are the improvement classes, and the `defect` prompt
tells judges "do not propose refactors" and demands "a concrete failure scenario". So the
pooled 10.6% was measuring the instruction, not the panel.

Quote the scoped number with its scope -- 18.5% on defect-type references -- rather than a
pooled figure whose denominator is half out of scope by construction.

## Regenerate

    JUDGE_BASE_URL=https://openrouter.ai/api/v1 JUDGE_API_KEY=$OPENROUTER_API_KEY \
    JUDGE_MODEL=anthropic/claude-opus-4.5 \
    ~/aacr-bench/.venv/bin/python recall/aacr-classify-refs out.json

It refuses to write if any classification call errors, for the same reason `aacr-score`
refuses a dead judge: a failed call would otherwise land as a silent category.
