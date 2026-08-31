# Changelog

## 0.1.0 — 2026-08-31

First tagged release; everything before this line was built in private.

- `llm-panel`: parallel independent judges over codex / opencode (OpenRouter) / claude /
  ollama transports; two failure classes (`refused` vs `harness`) with ambiguity
  defaulting to `harness`; `--diff`, `--rebut` (anonymized rebuttal round), `--thread`
  (persistent per-judge conversations), `--stream`/`--live`, per-judge cost and token
  accounting with subscription spend marked distinct from billed.
- `panel-report`: one self-contained HTML page per run — scoreboard, citation-overlap
  tables (symbols and file:line), full reviews verbatim, rebuttal round grouped by the
  finding under dispute.
- `panel-triage`: finds the runs that failed across every run root.
- `recall/`: the measurement half — a planted-defect corpus and an
  [AACR-Bench](https://github.com/alibaba/aacr-bench) harness that scores panel output
  with upstream's own evaluator. Headline numbers and their variance floor live in the
  README and `recall/benchmarks/`.
- 810 regression controls across six suites, each tied to a defect that actually
  shipped; run by CI on 3.11 and 3.13.
- Packaged install (`uv tool install llm-panel`) alongside the curl-able single files;
  the wheel ships verbatim copies of the same scripts.
