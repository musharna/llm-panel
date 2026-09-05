# Changelog

## Unreleased

- `recall/aacr-run.sh` takes an optional third argument, the number of instances per leg,
  so a one-instance dry run exists. Measured 2026-09-05 with live judges: both legs wrote
  their result files, and a failing leg aborts the script instead of printing ALL PANELS
  DONE.

## 0.1.4 — 2026-09-04

Two audits and a privacy scrub. The one behaviour change to plan for: a **claude judge is
now refused (exit 9)** when the reviewed tree declares hooks in `.claude/settings*.json`
or ships `.mcp.json`, exactly as an opencode judge already was for `.opencode/`;
`--unsafe-agent` overrides. New: `--usage` and `--reset-usage`.

- A second audit, every finding verified by execution before it was fixed:
  - `SIGTERM` and `SIGHUP` now take the Ctrl-C path. Cleanup was atexit-only, and atexit
    does not run on a signal's default action, so a `kill`, a `timeout` wrapper or a
    cancelled job left the prompt material in the reviewed tree and every judge child
    running on quota. Exit 130, what landed is kept.
  - A claude judge is refused (exit 9) when the reviewed tree declares hooks in
    `.claude/settings*.json` or ships `.mcp.json`, as an opencode judge already was for
    `.opencode/`. Measured on this laptop: `claude -p` runs a never-trusted tree's
    SessionStart and UserPromptSubmit hooks with no prompt. `--unsafe-agent` overrides.
  - `panel-report` and `panel-triage` survive a run cut off mid-write: a file truncated
    inside a multi-byte character raised `UnicodeDecodeError` through both (no html
    written; triage exit 1 against its own "always 0"), and `--list` crashed on
    `"judges": null`. Judge files go through one tolerant reader.
  - `--diff` stops reading at its 400 KB ceiling instead of holding the whole diff first.
  - `claimlib` no longer reads "the L2 cache" or "L1 regularization" as line 2 / line 1;
    the `L42` shorthand needs a path, `at`, or the start of a bullet beside it.
  - A refused `codex app-server` call is blamed on the method that was refused; the old
    index landed on the id-less `initialized` notification. A server that exits between
    poll and kill is no longer a traceback.
  - Exit codes 3, 10 and 13 are listed; a malformed roster config exits 1 (config), not 2
    (`--file`). Every option has a help string. `.gitignore` covers `.ruff_cache/`,
    `.llm-panel-material/` and the two license-restricted upstream diffs PROVENANCE says
    are never committed. `recall/aacr-run.sh` finds the repository from its own location
    and runs under `set -euo pipefail`. 52 new controls (988 across the seven suites).
- `llm-panel --usage` shows the ChatGPT plan the `codex` judge spends: both rate-limit
  windows with local reset times, the plan type, and the banked "Full reset (Weekly +
  5 hr)" credits. `--reset-usage` redeems one credit after the word `RESET` is typed;
  anything else on stdin sends no consume request, and the controls prove that against a
  fake `codex` that logs every JSON-RPC method it receives. Both go through
  `codex app-server` (`account/rateLimits/read`, `account/rateLimits/resetCredit/consume`),
  which is where this data lives — `codex exec --json` never emits it. Verified on codex-cli
  0.148.0 against a live Plus account.
- The captured artifacts no longer name the author's machine. Benchmark `rundir` fields,
  `BINARIES.txt` ledgers, the replayed fixture runs (whose prompts embed the tool's own
  source), the demo recording and `docs/demo.sh` carried the private home path and Windows
  profile verbatim; every copy now reads `/home/user` / `C:\Users\user`, and the fixture
  run captured from the home directory itself is `fixtures/runs/user-5de41d3c2d5a`. A new
  `privacy-controls` suite scans every git-tracked file (binaries included) for the
  identifiers that leaked and runs in CI beside the other six, with a planted-hit
  positive control so a scanner that reads nothing cannot go green.
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
