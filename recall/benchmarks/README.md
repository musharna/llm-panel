# AACR-Bench runs — everything behind the README table

The README's [On real PRs](../../README.md#on-real-prs-aacr-bench) table is the headline;
this page is what stands behind it. Every number comes from running the panel over
[AACR-Bench](https://github.com/alibaba/aacr-bench) PRs and scoring the findings with
**upstream's own evaluator** — `aacr-upstream` runs the panel and hands the findings over,
`aacr-score` invokes the evaluator and refuses to report a number from a judge that isn't
running. The three prompt styles are `aacr-upstream --prompt-style {defect,broad,volume}`.

## What keeps the numbers honest

- **The variance floor is measured.** Re-running the same judge on the same 35 PRs moves
  up to ±3 human-reference matches of 150, with an evaluator replicate at exactly zero —
  so effects under ~5–7 pp of recall are re-run noise at this n, which every subgroup
  claim so far was (`results-human-2arm-orgpt/perjudge35/`).
- **Three earlier readings were withdrawn on re-measurement**: a DEFECT/IMPROVEMENT
  split (the classifier was circular — `reference-categories/`), "broad finds different
  hits" (pre-registered replication on 35 fresh PRs, p = 0.40 — `results-human-2arm/`),
  and a transport/harness effect (its 13-PR foothold did not survive a re-run; a
  same-transport re-run of another judge moved as much — `results-human-2arm-orgpt/`).
  The audit trail is in each directory's README; nothing in the headline table rests on
  a withdrawn claim.
- **Diff-in-prompt review is the measured condition** — each panel runs in an empty
  directory with the diff in the prompt. The paired repo-checkout arm moves recall
  12.2% → 15.4% (p = 0.48) while _losing_ 7 of the diff arm's matches and gaining 11:
  repo access changes what judges attend to more than it strictly adds
  (`results-checkout-3judge/`).
- **Location agreement overstates semantic agreement ~2x** (22.8% of references had a
  finding at the right file and line; 12.2% had one a judge called the same concern) —
  which is why scoring is delegated upstream instead of done by a local matcher.
- **A degraded roster costs about half the recall** (6.5% vs 12.2% with one judge's
  quota spent and a 300s timeout, same extractor — `results-pilot-2judge/`). Check who
  actually answered before reading any number.
- **The panel does not discriminate accepted from rejected reviewer comments**
  (12.2% vs 11.1%, Fisher p = 1.0).
- **Unlocated findings are withheld from upstream, not handed over empty** — upstream's
  filters treat a missing path or line as match-everything, and passing them through
  inflated line matches from 20 to 50 on the first scoring run.

## Run ledgers

Each directory's README is the ledger for that run: what was declared before it, what
was measured, and what was withdrawn.

| directory                   | what it is                                                                               |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| `results-clean-3judge/`     | the headline result — clean 3-judge run                                                  |
| `results-clean-2judge/`     | the roster-matched control, two judges                                                   |
| `results-broad-3judge/`     | broad prompt vs defect prompt, the same panel asked a wider question                     |
| `results-volume-3judge/`    | the volume arm — the defect prompt told not to stop                                      |
| `results-checkout-3judge/`  | the same panel standing in the repository instead of reading a diff                      |
| `results-human-2arm/`       | human-authored references, broad vs volume, pre-registered                               |
| `results-human-2arm-orgpt/` | the transport-controlled replication of the above; `perjudge35/` is the floor            |
| `results-pilot-2judge/`     | the pilot — 2 judges, degraded; not a headline result                                    |
| `cost-cut/`                 | the declared cost-efficiency cut that settled the default prompt                         |
| `reference-categories/`     | what each reference comment asks for — RETRACTED 2026-08-26                              |
| `scores/`, `upstream/`      | the evaluator's outputs and upstream's own scoring inputs                                |
| `diffs/`, `diffs-upstream/` | the PR diffs the panels were shown — see the note below on what is committed             |
| `checkouts/`                | shallow clones for the checkout arm — gitignored; `aacr-upstream checkout` rebuilds them |

What is committed under `diffs-upstream/`: the diffs of the 2026-08-25 samples
(`upstream/pos-seed42-n20.jsonl`, `neg-seed42-n10.jsonl`), fetched once from GitHub's
compare API and kept as the exact bytes the panels saw. Of the 35-PR replication sample
(`upstream/pos-human-n35.jsonl`, 2026-08-28), only the two PRs it shares with the seed-42
sample have a committed diff; the other 33 live in the local cache, which
`aacr-upstream run` refills from the same API. The committed result and score JSONs do
not need them — `aacr-score` works from those alone.

Data licensing: the PR diffs and review-comment text are third-party material under
their upstream terms — see [PROVENANCE.md](PROVENANCE.md).
