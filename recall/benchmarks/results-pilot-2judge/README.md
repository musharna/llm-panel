# Pilot run — 2-judge, DEGRADED. Not a headline result.

Scored with the UPSTREAM AACR-Bench evaluator (`alibaba/aacr-bench`), real LLM judge
(`anthropic/claude-opus-4.5` via OpenRouter, outside the panel's own model families).
`judge failures during scoring: 0` on both arms — asserted by `aacr-score`, not assumed.
Per-reference verdicts: `../scores/pilot-pos.json`, `../scores/pilot-neg.json`.

|                      | positive (valid refs) | negative (REJECTED refs) |
| -------------------- | --------------------: | -----------------------: |
| instances            |                 18/20 |                     9/10 |
| expected / generated |              123 / 59 |                  36 / 26 |
| line matches         |            16 (13.0%) |                4 (11.1%) |
| **semantic matches** |          **7 (5.7%)** |             **0 (0.0%)** |
| semantic match rate  |                 11.9% |                     0.0% |

## Corrected 2026-08-26 — this file carried withdrawn numbers for a day

The first version of this table read 107 generated / 50 line matches (40.7%) / 11 semantic
(8.9%). Those came from the scoring that handed unlocated findings to upstream with an empty
path, which upstream treats as a WILDCARD, not a non-match (see `../results-clean-3judge`).
The re-score with wildcards withheld — the numbers above — was on disk the same afternoon
and quoted by the clean README, but this file was never updated. Found by codex in the
2026-08-26 audit as "the pilot README no longer matches its shipped metrics". A ledger that
stops describing its own directory is the same defect class recorded twice already in this
project (the 107-vs-65 log, the 18-vs-8 manifest).

## Read the gap, not the 5.7%

Of the 16 findings that landed on the correct file AND line, 7 expressed the same concern.
Location agreement overstates semantic agreement about 2x here, as it does on the clean run
(21.1% vs 10.6%). A location-based matcher cannot detect that about itself, which is why
scoring is delegated upstream.

## Do NOT report the valid-vs-rejected ratio

5.7% vs 0.0% reads like discrimination. Fisher exact two-sided **p = 0.352**; the line-match
arm gives p = 1.000. The negative arm has zero events. Power estimates from this run are
unstable for the same reason — the clean run's estimate (~35 negative PRs) supersedes the
"~919 per arm" figure that an earlier version of this file derived from the inflated
numbers.

## Why this is a floor

- 39/54 judge slots answered; codex quota died mid-batch (12 of 18 positive instances and
  9 of 9 negative instances ran degraded).
- 2 instances returned 0 findings purely by hitting the 300s cap, and they carry 20 of the
  123 positive references.
- Binaries were edited mid-run, so this batch is mixed-version. The clean run pins md5s.

Regenerate metrics from these result files without re-running any panel:

    ~/aacr-bench/.venv/bin/python recall/aacr-score \
      recall/benchmarks/results-pilot-2judge/pos \
      recall/benchmarks/upstream/pos-seed42-n20.jsonl <out-dir> 1
