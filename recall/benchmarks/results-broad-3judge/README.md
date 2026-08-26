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
| ---------------- | ---: | -------: | ----------: | ------------------: | --------: |
| positive, defect |  123 |       79 |       21.1% |           **10.6%** |     16.5% |
| positive, broad  |  123 |      236 |       48.0% |           **26.0%** |     13.6% |
| negative, defect |   36 |       30 |       11.1% |                2.8% |      3.3% |
| negative, broad  |   36 |      155 |       44.4% |               16.7% |      3.9% |

## Recall by what the reference asks for — RETRACTED, see below

An earlier version of this file split recall using an LLM classifier I wrote
(`aacr-classify-refs`, DEFECT vs IMPROVEMENT) and reported DEFECT 18.5% -> 35.4% against
IMPROVEMENT 1.7% -> 15.5%, concluding that the house prompt was near-blind to the class it
forbade. **That split does not survive AACR's own labels and is withdrawn.**

AACR ships a `category` field on every reference comment. Re-cutting the identical scored
runs on it (`recall/aacr-recut`, no re-run, no new judge calls):

|                                                 | refs | defect | broad | Fisher p |
| ----------------------------------------------- | ---: | -----: | ----: | -------: |
| defect-y (Code Defect + Security + Performance) |   78 |  10.3% | 29.5% |   0.0044 |
| Maintainability and Readability                 |   45 |  11.1% | 20.0% |    0.384 |
| POOLED                                          |  123 |  10.6% | 26.0% |   0.0027 |

Under the shipped labels the defect prompt recalls maintainability references at **11.1%**
and defect references at **10.3%** -- `p = 1.0000`, no difference whatsoever. It was never
selectively blind to the forbidden class. My classifier put those same two classes at 18.5%
and 1.7% (p = 0.0025).

_Corrected 2026-08-26 (audit)._ The first version of this table read 75/48 and 10.7%/10.4%.
It joined scored references to bench rows on (commit, path, line), and that key is not
unique: 202 of the bench's 1,925 keys carry two or more comments at the same file and line,
110 of them differing in `category`, and 26 of these 123 references sat on such a key. The
dict kept whichever row was written last. The join now includes the comment text
(`aacr-recut`, control 6.5); the conclusion is unchanged and the numbers above are the
corrected ones. Found by codex from `scores/clean-pos.json`, in a review that timed out
before it could finish -- the two judges that completed did not see it.

**Why the two disagree: the classifier and the panel prompt share a definition.** Both were
written by me, and the phrase "concrete failure scenario" appears verbatim in each --
`aacr-upstream` tells the panel to report defects "each with a concrete failure scenario",
and `aacr-classify-refs` says to answer DEFECT for "something with a concrete failure
scenario". Both put refactors on the other side. So a reference the panel matched, because
it was hunting exactly that, is also a reference my classifier calls DEFECT. The split
measured the shared definition, not the panel.

The agreement rate hides it: my labels match AACR's on 99/123 = **80%** of references. But
the 24 disagreements are not random with respect to the outcome. Of the 13 references the
defect prompt actually matched, my classifier called **11 of 13** DEFECT; AACR's field calls
**8 of 13** defect-y. A classifier can be 80% accurate and still invert a split, when its
errors correlate with the measured quantity. This is the circular-calibration failure --
a scale derived from the artifact under test.

Pooled is unaffected: it never used any categorization.

## What the gain actually is: volume, not scope

With references fixed, recall = findings x precision, so the recall ratio must decompose
exactly -- and it does:

    findings   79 -> 236          x2.99
    precision  16.5% -> 13.6%     x0.82
    product                       x2.46
    recall     10.6% -> 26.0%     x2.46   (exact)

Per finding, `broad` is slightly **worse** (0.165 matches/finding -> 0.136). The entire
recall gain is accounted for by emitting three times as much. That is a weaker claim than
"broadening unlocked a class the prompt had excluded", and it is the one the data supports:
nothing here shows the prompt's _content_ mattered rather than its _volume_. Distinguishing
those needs an arm that raises volume without widening scope -- not run.

## Who wrote the references

74% of AACR's reference comments are AI-authored (`is_ai_comment`; 1,597 of 2,145
bench-wide, 85 of 123 in this sample), from GPT-5.2, Claude-4.5-Sonnet, Qwen-Coder-480B,
GLM-4.7, Deepseek-V3.2 and Gemini-3-Pro. So "semantic recall against references" is mostly
agreement with other models. That was a live risk to the headline, and it measures null:

|                | refs | defect | broad | Fisher p |
| -------------- | ---: | -----: | ----: | -------: |
| AI-authored    |   85 |   9.4% | 25.9% |   0.0081 |
| human-authored |   38 |  13.2% | 26.3% |    0.249 |

The panel agrees with human reviewers at about the same rate as with AI ones, so the
benchmark's AI-heavy composition is not inflating the number. The human arm is small
(n=38, 95% CI [15.0, 42.0] for broad) -- consistent with no difference, not evidence of none.
(Corrected 2026-08-26 with the unique join; the first version read 90/33.)

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

- A reviewer who will read everything gets materially more real findings from `broad`.
- A gate that must not cry wolf keeps `defect`, whose 13:1 ratio is much cleaner.

Both prompts ship (`--prompt-style`). The default stays `defect`, because refusing to emit
nitpicks is a deliberate choice with real value and this is one benchmark on 18 PRs.

The retraction above strengthens rather than weakens that default. The original case for
switching was that `defect` had a specific blind spot -- a whole class of valid comments it
was instructed not to see. AACR's own labels say that blind spot does not exist: the two
classes are recalled at 10.7% and 10.4%. What `broad` buys is three times the output at a
slightly lower hit rate, which is a throughput/noise trade a user should make deliberately,
not a defect being repaired.

## Reproducing the cuts

    recall/aacr-recut          # joins scores/*.json onto aacr-bench.json; no judge calls

`scores/` holds the upstream evaluator's per-reference verdicts (`semantic_match` per
reference, written in place by `judge.py`) for all four arms. These had been living only in
a job temp directory -- every number in this file depends on them, so they are now in the
repo. `aacr-recut` refuses to report on a partial join and asserts that each arm's totals
reproduce the published figures; both guards were confirmed to fire by breaking the join key
(`FATAL: 123 references did not join`) and by dropping an instance (`joined 122, summary
123`).
