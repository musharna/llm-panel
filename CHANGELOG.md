# Changelog

## Unreleased

- The README's precision/recall chart is drawn by `docs/bench_chart.R` (ggplot2) from
  `docs/theme.R`, the one house style every figure in the repository sources; the
  matplotlib script it replaces is gone. Same numbers, same canvas, both colour schemes.
- `opencode.jsonc`'s comment on `edit: deny` is corrected. Re-measured on opencode 1.18.26:
  a primary agent with only that deny has no write tool and creates no file, so the
  2026-08-20 "judge wrote a file under `edit: deny`" observation was the subagent
  fallback, not a permission failure. The fallback itself is confirmed upstream on
  1.18.26 with a write demonstration (anomalyco/opencode#36764).
- `recall/benchmarks/README.md` no longer lists `checkouts/` as browsable (it is
  gitignored and rebuilt by `aacr-upstream checkout`) and says which `diffs-upstream/`
  diffs are committed. The 35-PR replication sample's 31 committable diffs are now in
  (58 of 63 sampled PRs; n8n and timescaledb stay out per PROVENANCE, three seed-42
  fetches never succeeded).

## 0.1.3 — 2026-09-01

A documentation release: the only code change is one word of `--rebut` help text
("anonymised", matching the README) and the version line. It exists because PyPI
renders the README it was uploaded with, and that was the 0.1.2 one.

- README: the "What's here" diagram is a pre-rendered SVG (light and dark) instead of a
  mermaid block, and every link is absolute, so the PyPI page renders it — PyPI has no
  mermaid and treated the relative links as dead. The `orvision` vision transport,
  `--image`/`--vision-check`, and the `--live`/`--stream`/`--runs`/`--show`/`--effort`/
  `--timeout` flags are documented; the platform requirement (Linux, macOS or WSL) is
  stated; the exit-code summary matches `--help`. The AACR-Bench detail moved to
  `recall/benchmarks/README.md`, which now indexes every run ledger.
- Every controls suite ends with `all N controls green`, so the counts the README quotes
  have a source.

## 0.1.2 — 2026-09-01

The first outside review after the repository went public. Its findings share one shape:
the boundary between `llm-panel` and a judge's process was drawn by default.

- **Reviewing a repository means trusting its `.opencode/` and `opencode.json[c]`.**
  opencode loads plugins, tools and agent definitions from the tree it is pointed at, and
  the read-only guard only ever read `opencode.json[c] -> agent`. A repository shipping
  `.opencode/agents/panelist.md` with bash allowed passed the guard and ran as you, with
  your keys. `llm-panel` now refuses (exit 9) when the tree carries any of that;
  `--unsafe-agent` overrides. A claude judge gets a note about project hooks/`.mcp.json`.
- **A judge child sees only its own transport's keys.** The OpenRouter/HF keys loaded for
  opencode were inherited by codex and claude.
- **A timeout kills the judge's whole process group.** `codex` on PATH is a Node launcher;
  killing it left the native binary running the turn on plan quota after the panel had
  reported `harness`. The claude deadline does the same, which also unblocks its read loop.
- **The reviewed tree is cleaned on every exit, and Ctrl-C keeps what landed.** A Ctrl-C
  used to block for the full `--timeout` and then write nothing, leaving the prompt --
  `--diff` untracked-file contents included -- in `<repo>/.llm-panel-material/`, where the
  next `--diff` panel sent it to every judge. Exit 130 now writes a panel marked
  INTERRUPTED with every answer that arrived.
- The host credential copy follows the host file's absence (`opencode auth logout`
  revoked nothing for the judges); copies are 0600; a per-run temp state dir is removed.
- The rebuttal-round self-identification warning matches whole words, so `big-pickle` no
  longer warns on "bigger".
- "no prompt given" comes before the transport warnings and the agent guard; `--diff`
  outside a git repository, an unreadable `--file`, an unwritable cache directory and
  undecodable argv bytes are sentences instead of tracebacks; `--diff` refuses a diff over
  400 KB; judge text is stripped of terminal escape sequences before it is printed or
  written; `limits.json` writes are locked; run directories are owner-only; `--help` lists
  the exit codes; `panel-report --list` with no runs says so and exits 1; `--list` names
  the file a key was read from; CI runs 3.12 as well.

## 0.1.1 — 2026-09-01

- Ship `opencode.jsonc`, the read-only `panelist` agent every opencode judge runs as.
  0.1.0 refused to start opencode judges on a machine that had not defined it (exit 9)
  and never said where to get it; the refusal now points at the file.
- The controls suites run on a clean machine: the two real run directories they replay
  ship as `fixtures/runs/`, and the "shipped config" controls read the shipped file, not
  `~/.config`. Found by the first CI run after the repository went public -- every
  earlier green run was on the author's laptop.

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
