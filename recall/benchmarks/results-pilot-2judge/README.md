# Pilot run — 2-judge, DEGRADED. Not a headline result.

Scored with the UPSTREAM AACR-Bench evaluator (`alibaba/aacr-bench`), real LLM judge
(`anthropic/claude-opus-4.5` via OpenRouter, outside the panel's own model families).
`judge failures during scoring: 0` on both arms — asserted by `aacr-score`, not assumed.

|                          | positive (valid refs) | negative (REJECTED refs) |
|--------------------------|----------------------:|-------------------------:|
| instances                | 18/20                 | 9/10                     |
| expected / generated     | 123 / 107             | 36 / 33                  |
| line matches             | 50 (40.7%)            | 10 (27.8%)               |
| **semantic matches**     | **11 (8.9%)**         | **2 (5.6%)**             |
| semantic match rate      | 10.3%                 | 6.1%                     |

## Read the gap, not the 8.9%

Of the 50 findings that landed on the correct file AND line, only 11 expressed the same
concern. A location-based matcher scored 44/53 = 83% "recall" on this same benchmark; the
semantic judge says 8.9%. That ~4.6x is the overcounting a location matcher is structurally
incapable of detecting about itself, and it is why scoring moved to upstream's evaluator.

## Do NOT report the valid-vs-rejected ratio

8.9% vs 5.6% looks like 1.61x discrimination. Fisher exact two-sided **p = 0.734**; the 95%
CIs overlap almost entirely (0.051–0.153 vs 0.015–0.181). The line-match arm is also NS
(p = 0.177). Detecting this effect at 80% power needs ~919 references per arm and the
benchmark's ENTIRE negative pool is 639 — so more spend cannot settle it.

## Why this is a floor

* 39/54 judge slots answered; codex quota died mid-batch (12 of 18 positive instances and
  9 of 9 negative instances ran degraded).
* 2 instances returned 0 findings purely by hitting the 300s cap, and they carry 20 of the
  123 positive references.
* Binaries were edited mid-run, so this batch is mixed-version. The clean run pins md5s.

Regenerate metrics from these result files without re-running any panel:

    ~/aacr-bench/.venv/bin/python recall/aacr-score \
      recall/benchmarks/results-pilot-2judge/pos \
      ~/panel-recall/benchmarks/upstream/pos-seed42-n20.jsonl /tmp/out 1
