# Changelog

## 0.1.8 — 2026-09-15

- `--reset-usage` could not redeem a banked reset credit at all. codex renamed the
  app-server's redeem call from `account/rateLimits/resetCredit/consume` to
  `account/rateLimitResetCredit/consume`, and the app-server rejects the old spelling as an
  unknown variant — so the flag read the bank, asked for the typed word RESET, and then
  sent a method the provider no longer knows. Control 24's fake app-server answered the old
  name too, which is why the source fix sat uncommitted until both halves could land: it
  now answers the new name only, so a build that reverts fails 24.3 instead of passing
  against a stub that would answer to either. Not exercised against the live app-server —
  redeeming is not undoable and the bank is finite.
- `action.yml`, from the panel's own review of PR #3 (or-kimi): the diff is written to a
  file before it is cut, since `git diff | head -c` under `pipefail` failed the step with
  SIGPIPE on exactly the oversized diffs the cut was for; and the comment step ends the
  "## Question" strip at the first judge heading, not at a bare `---`, which a unified
  diff prints for every removed line reading `--` and which then leaked the rest of the
  prompt into the comment.
- `panel-report`: a CSS comment described a background-attachment scroll-shadow trick that
  was never shipped; the `.more` class set by script is the mechanism.

## 0.1.7 — 2026-09-06

- `action.yml`: description under the GitHub Marketplace's 125-character cap, so the action
  can be listed there.
- **README rewritten for a first visitor**, from an independent critique: what the tool is
  for in one line, install and a one-judge first run at the top, the rebuttal screenshot as
  the hero, a cited table beside CodeRabbit, PR-Agent and Copilot code review, and the
  benchmark sections cut to their two tables — the reading of them moved to
  `recall/README.md` (new, the planted corpus) and `recall/benchmarks/README.md`.
- `panel-report`: the bench subtitle said "one judge per vendor is the point", the
  opposite of the README's evidence (Kohli 2026); it now says family is display metadata,
  not policy (control 43.1). `docs/report.png` re-rendered from the same cline run.

## 0.1.6 — 2026-09-06

- **A GitHub Action.** `uses: musharna/llm-panel@v0.1.6` with an OpenRouter key builds a
  prompt from the pull request's diff, runs the panel in the checked-out tree and posts
  every answer in full as one comment, edited on each push. Exit 9 (the PR's tree carries
  configuration the judges would run) fails the job; 0 and 4 post. This repository runs it
  on its own pull requests, installed from source.
- **The README puts the paper's baselines next to ours.** AACR-Bench's Table 3, "No
  context", all 200 PRs: single frontier models score 27–47% recall at 6–11% precision.
  The `defect` panel's 9.8% / 9.5% on 18 PRs is at the low-recall end of that spread and
  `broad` is inside it; the rows are not directly comparable and the paragraph says
  exactly how they differ.
- **A first run with none of the author's tools is one sentence, not three warnings and
  a refusal about an opencode agent.** When no selected judge has its CLI installed the
  panel exits 14, names each missing binary with its install hint, and says where
  `roster.json` goes and that `llm-panel --check` pings whoever is in it.
- `panel-report`: a review taller than its box now says "scrolls ↓" at the fold until the
  reader reaches the end — with overlay scrollbars a review cut mid-sentence under a
  footer promising "reproduced in full" read as truncation; and "no positions" in the
  round-two column is grey, not the red of a failure. Both from an independent look at
  the rendered page. Three lint leftovers gone.

## 0.1.5 — 2026-09-06

The release that was going to be documentation only became a defect release the same
afternoon. An audit by the new `astra` judge (one turn, 13 minutes, over the tree at `98db692`)
found 18 defects that three earlier audits had not. Every one below was verified against
the source, given a control that failed on the old code for the stated reason, and fixed
at the mechanism. 91 new controls, 1082 across the seven suites.

- **Two ways past the trust gates.** `--check` launched every judge before either gate
  ran, so `--check` in a tree carrying an opencode plugin or claude hooks ran them; and the
  claude gate consulted the judges alone where the opencode gate already included the
  synthesizer, so `--synthesize claude-opus` ran a hostile tree's hooks. Both gates now
  live in one `enforce_trust()` that anything launching a judge calls first.
- **A codex child no longer inherits `ANTHROPIC_API_KEY`.** 0.1.2 promised each child
  sees only its own transport's keys; this one was stripped for claude alone.
- **A codex judge's tokens are recorded.** `codex exec --json` ends every turn with a
  `turn.completed` usage event the transport never read, so every codex row in every
  run.json — the AACR benchmarks included — said 0 in / 0 out, and Astra's own audit run
  printed UNMEASURED for the judge that had just spent 13 minutes of plan quota.
- `--thread` turn files are 0600 under a 0700 directory; they took the umask before, so
  every attached diff sat 0644 for other local users. And `--thread` refuses, naming
  `XDG_CACHE_HOME`, when the only cache outside the reviewed tree is a per-run temp dir
  (`--cwd $HOME`), instead of starting a fresh conversation every turn.
- `--diff` never lists `.llm-panel-material/` as a new file, so a concurrent panel's
  spilled prompt is not sent to this panel's providers.
- `--stream` echoes are stripped of terminal escapes like the final review is, and
  `strip_ansi` now removes OSC sequences (OSC 52 writes the clipboard) as well as CSI.
- A dribbling ollama or OpenRouter peer cannot outlive `--timeout`: the deadline was
  checked between lines, and a socket timeout resets per byte, so a peer sending one byte
  at a time held the judge indefinitely. Reads are now one buffered chunk at a time, each
  bounded by what is left of the deadline.
- `--usage` gives up at its deadline even when the `codex` launcher has exited and its
  child still holds the pipes; the watchdog used to stand down the moment the launcher
  was gone.
- `panel-report`: a harness error is no longer counted as an answer ("5 of 5 answered"
  above "5 did not answer"); billed, quota and token totals include the rebuttal and
  synthesis phases the label already claimed; the synthesis shown is the LAST heading in
  panel.md, so a review containing that heading cannot spoof it; the default report name
  keeps the run directory's PID, so two runs in one second no longer overwrite; two-letter
  reviewer tags (`AA1`) past 26 judges parse.
- `panel-triage` reports a rebuttal or synthesis that FAILED, not only one whose file is
  missing.
- `recall/aacr-upstream` no longer merges a fragment across a judge boundary: judge B's
  first observation with an unresolvable path was glued onto judge A's last finding and
  took A's location. Fixing that exposed a second: a judge's opening bare header with no
  location carried its empty location over the body's real one, so the finding was
  withheld. Offline re-conversion of the committed runs: 4 of 54 instances each recover
  one located finding (`results-0.1.4-3judge` positives 126 → 129,
  `results-clean-3judge` negatives 46 → 47). **The committed scores were produced by the
  old bridge and are not re-scored**; the recovered findings are inside the stated noise
  floor, and a re-score needs the paid evaluator.
- `recall/aacr-score` resolves its three path arguments before it changes directory into
  the upstream evaluator, so relative arguments mean the caller's directory.
- **An opencode judge's token line now counts what the provider billed.** opencode reports
  `tokens: {input, output, reasoning, cache: {write, read}}` per step and the panel summed
  only the first two, so a `gpt-6-astra` call that wrote 8,890 tokens of opencode's own
  system prompt and tool schemas to the cache printed "3 in / 7 out, $0.1115" — the token
  line and the dollar line disagreed by 3000x. Cached prompt tokens are input, reasoning
  tokens are output. Measured live before and after; control `kimi.7`.
- Two opt-in GPT-6 Astra judges, neither in the default roster: `astra` on the ChatGPT
  plan (codex-cli ≥ 0.153.0; one turn is a large share of a Plus weekly window, so keep
  it for a single hard question) and `or-astra` metered through OpenRouter ($10/M in,
  $50/M out, plus the ~$0.11 of cached opencode prompt every call pays first).

Also in this release, from before the audit. The PyPI page renders the README it was
uploaded with, and the 0.1.4 README quoted benchmark numbers from a prompt that was
already gone:

- **The README's default-prompt numbers were measured with a prompt that no longer
  exists.** The `defect` row quoted 12.2% recall / 16.5% precision from a run that started
  three and a half hours before the prompt was rewritten (`06f6f0d`). The shipped prompt,
  re-measured on the same 18 PRs at `e2ad666`, reads **9.8% recall / 9.5% precision, 10.5
  findings per validated hit** (`recall/benchmarks/results-0.1.4-3judge/`). Recall itself
  did not move — paired on the same 123 references, McNemar p = 0.51 — the rewrite bought
  volume (91 → 126 findings) and precision paid for it. README table, the location-vs-
  semantic figures, and `docs/bench_chart.R` all corrected; the `broad` and `volume` rows
  were already post-rewrite and are unchanged.
- `recall/aacr-run.sh` takes an optional third argument, the number of instances per leg,
  so a one-instance dry run exists. Measured 2026-09-05 with live judges: both legs wrote
  their result files, and a failing leg aborts the script instead of printing ALL PANELS
  DONE.
- `--usage` and `--reset-usage` re-verified against codex-cli 0.153.4 (the version that
  first serves `gpt-6-astra` on a ChatGPT plan): same JSON-RPC methods, same output. A
  third audit of the tree at `b2ac8c3` found nothing to fix; all 988 controls green.

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
- Captured artifacts use generic paths, and a new `privacy-controls` suite (with a
  planted-hit positive control) scans every git-tracked file in CI.
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
