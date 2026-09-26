# llm-panel

[![controls](https://github.com/musharna/llm-panel/actions/workflows/controls.yml/badge.svg)](https://github.com/musharna/llm-panel/actions/workflows/controls.yml)
[![pypi](https://img.shields.io/pypi/v/llm-panel.svg)](https://pypi.org/project/llm-panel/)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/musharna/llm-panel/blob/main/LICENSE)
[![python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://github.com/musharna/llm-panel/blob/main/pyproject.toml)

Several independent LLM code reviews of one diff, on one page, with a measured miss rate.

```sh
uv tool install llm-panel            # or: pipx install llm-panel
llm-panel --judges codex --diff "What is wrong with this change?"   # one judge you already have
panel-report --open                  # the run as one HTML page
```

Any one of `codex`, `claude`, `opencode` or `ollama` on your PATH is enough to start; the
[roster](#configure-your-roster) is where you add the rest. Unlike a single-reviewer bot,
the panel is N readers who cannot see each other, a rebuttal round in which they defend or
withdraw, and a [recall benchmark](#on-real-prs-aacr-bench) that says what they miss.

Judges run in parallel, never see each other's work, and answer from their own reading of
your repo. An optional second round (`--rebut`) shows each of them the others' findings,
relabelled as Reviewer A/B/C rather than by model name, and asks them to defend or
withdraw. The relabelling is best-effort: a review that names its own model or vendor
triggers a warning, not redaction. The output is a single self-contained HTML page where
that second round is grouped **by the finding being argued about**, so comparing what five
models said about one line of code doesn't mean holding five documents in your head.

It is not a voting machine. A panel _generates candidate defects_; it does not establish
truth by counting agreements. Every finding still has to be checked against the code — and
the tool's other half, [`recall/`](#what-it-actually-catches), exists to measure what the
panel misses rather than assert what it catches.

```
llm-panel --diff "Which of these changes is most likely to be wrong?"
panel-report --open          # render the newest run and open it
panel-triage --bad           # which runs went wrong, across every run root
```

A real run, with the waiting compressed: three judges asked in parallel (two free-tier,
one on a ChatGPT plan) landing as they finish, the scoreboard from `panel.md`, and
`panel-report` rendering it ([recording](https://github.com/musharna/llm-panel/blob/main/docs/demo.cast)):

![terminal: llm-panel asks three judges in parallel, reports each as it lands, then head -n 12 panel.md shows the scoreboard and panel-report writes the HTML page](https://raw.githubusercontent.com/musharna/llm-panel/main/docs/demo.gif)

The rebuttal round as rendered — every position each judge took on each finding, grouped
by the finding under dispute, disagreements marked CONTESTED. This run: four free-tier
judges asked to review llm-panel's own failure-classification code; one failed and is
reported as `harness`:

![rebuttal round: positions grouped by the finding being argued about](https://raw.githubusercontent.com/musharna/llm-panel/main/docs/rebuttal.png)

**Contents:** [What's here](#whats-here) · [Beside the review bots](#beside-the-review-bots) ·
[Install](#install) ·
[Configure your roster](#configure-your-roster) · [Using it](#using-it) ·
[What it actually catches](#what-it-actually-catches) ·
[On real PRs](#on-real-prs-aacr-bench) · [Tests](#tests) ·
[Known limitations](#known-limitations)

## What's here

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/whats-here-dark.svg">
  <img alt="flow: a question (plus --diff or stdin) goes to llm-panel, which asks judges A, B and C in parallel, blind to each other and reading your repo; their answers land in a run directory (one .md and one .prompt.md per judge, panel.md, run.json); with --rebut a second round shows each judge the others' findings anonymised as Reviewer A/B/C and asks it to defend or withdraw; panel-report renders the run as one self-contained HTML page and panel-triage finds the runs that failed" src="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/whats-here-light.svg" width="560">
</picture>

| tool                   | what it does                                                                           |
| ---------------------- | -------------------------------------------------------------------------------------- |
| `llm-panel`            | asks the judges, in parallel, and writes the run to disk                               |
| `panel-report`         | renders a run as one self-contained HTML page, grouped by claim                        |
| `panel-triage`         | finds the runs that _failed_, which a listing shows as ordinary rows                   |
| `recall/panel-recall`  | measures what the panel **misses**, against a corpus of planted defects                |
| `recall/aacr-upstream` | runs the panel over AACR-Bench PRs and hands the findings to **upstream's** evaluator  |
| `recall/aacr-score`    | invokes that evaluator, and refuses to report a number from a judge that isn't running |
| `claimlib.py`          | the one measurement boundary: reviews → span-grounded observations                     |
| `*-controls`           | the regression suites — 1091 controls, most of them tied to a defect that shipped      |

## Beside the review bots

| | models per review | what you read | published accuracy | runs as | keys |
| --- | --- | --- | --- | --- | --- |
| **llm-panel** | N, independent, blind to each other; rebuttal round | every answer verbatim, grouped by finding | measured on AACR-Bench, low and [reproducible](#on-real-prs-aacr-bench) | CLI, GitHub Action | yours (subscriptions or API keys) |
| [CodeRabbit](https://www.coderabbit.ai/pricing) | several, in a [pipeline by stage](https://www.coderabbit.ai/blog/behind-the-curtain-what-it-really-takes-to-bring-a-new-model-online-at-coderabbit) | filtered by a verification agent | [vendor-reported](https://www.coderabbit.ai/blog/coderabbit-tops-martian-code-review-benchmark) on Martian's bench | GitHub/GitLab app, CLI, IDE | hosted, [no model choice](https://www.coderabbit.ai/blog/why-users-shouldnt-choose-their-own-llm-models-choice-is-not-always-good) |
| [PR-Agent](https://github.com/The-PR-Agent/pr-agent) (MIT; formerly Qodo's) | one model per call, fallback on failure | structured summary, [3 findings by default](https://raw.githubusercontent.com/The-PR-Agent/pr-agent/main/pr_agent/settings/configuration.toml) | none for the OSS tool | GitHub Action, CLI, Docker | yours |
| [Copilot code review](https://docs.github.com/en/copilot/concepts/code-review/code-review) | "a mix of models", not switchable | filtered, severity-labelled | none stated | github.com, `gh`, IDE | hosted |

The difference is not that the panel is better — on the numbers above it is not — but that
it shows you everything the models said and tells you how much they miss. A filter that
"validates each suggestion" is one more opinion, and the one most likely to drop a minority
finding. Verified 2026-09-06 from each vendor's own pages.

## Install

Pure Python 3.11+ standard library on Linux/WSL (CI: Ubuntu); macOS untested. It needs
POSIX file locks and process groups, and says so on Windows instead of tracing back. No dependencies, no build
step. Each tool is one readable file, so either install route runs identical code:

```sh
# as a package (entry points: llm-panel, panel-report, panel-triage)
uv tool install llm-panel        # or: pipx install llm-panel

# or as the files themselves
git clone https://github.com/musharna/llm-panel ~/llm-panel
ln -s ~/llm-panel/{llm-panel,panel-report,panel-triage} ~/.local/bin/
```

3.11 is a hard floor (the link renderer uses atomic groups, added to `re` in 3.11);
`panel-report` says so at startup rather than failing part-way through a render.

Judges reach models through command-line tools you install separately — none are bundled,
and you need at most one to start:

| tool       | who it is                                    | billing                                                                       |
| ---------- | -------------------------------------------- | ----------------------------------------------------------------------------- |
| `codex`    | OpenAI's CLI                                 | a ChatGPT plan, not metered API                                               |
| `opencode` | multi-provider CLI most judges route through | your OpenRouter / HuggingFace keys                                            |
| `claude`   | Anthropic's CLI                              | a claude.ai subscription (setting `ANTHROPIC_API_KEY` switches it to metered) |
| `ollama`   | local models                                 | free, and no tool loop — see the caveat below                                 |

A judge whose tool is missing is reported as `harness` and the panel exits 4 — one judge's
problem, never the whole panel's. If no selected judge has its tool, the panel exits 14
and names each one with its install hint.

Two transports skip the CLI: `ollama` uses its local HTTP API, and `orvision` calls
OpenRouter's HTTP API directly with your OpenRouter key so that the `vis-*` judges (grok,
kimi, gemini, gpt) can look at an `--image`.

### The read-only agent for `opencode` judges

`opencode` judges run as an agent named `panelist` that can read the repo but not write
to it, and `llm-panel` refuses to start an opencode judge until that agent is defined and
verified read-only (exit 9) — opencode's default `build` agent will happily edit the tree
it is reviewing. The definition ships as
[`opencode.jsonc`](https://github.com/musharna/llm-panel/blob/main/opencode.jsonc): merge its
`agent.panelist` block into `~/.config/opencode/opencode.jsonc`, or keep the file at the
root of a repo you review with it — opencode reads project-local config too.

## Configure your roster

**The built-in judge list is a default, not a fixture — it names the author's accounts.**
Yours will be different. Point the roster at models you actually have:

Copy [`roster.example.json`](https://github.com/musharna/llm-panel/blob/main/roster.example.json) to
`~/.config/llm-panel/roster.json` (`$XDG_CONFIG_HOME` honoured; `$LLM_PANEL_CONFIG` wins).
It is strict JSON — no comments, no trailing commas — and a malformed config is **fatal**
and names the offending key, because quietly falling back to the built-in roster would run
a panel you didn't ask for, and bill you for it:

```json
{
  "default": ["codex", "nemotron", "glm", "kimi", "or-deepseek", "or-grok"],
  "judges": {
    "my-gpt": {
      "transport": "opencode",
      "model": "openrouter/openai/gpt-5.6",
      "family": "OpenAI"
    },
    "big-pickle": null
  }
}
```

`null` drops a shipped judge. `default` is the panel run when `--judges` is absent.
`llm-panel --list` shows the roster offline and marks config-defined judges.
`llm-panel --check` actually pings each one. `llm-panel --help-config` prints this schema.

### Picking judges

**"One per vendor" is _not_ the answer.** It is tempting to
treat vendor labels as a proxy for independent opinions. The evidence says they aren't:
[Kohli 2026](https://arxiv.org/html/2605.29800) measured cross-family judge correlation at
φ̄=0.389 against same-family 0.437 — barely different — with the three _most_ correlated pairs
being cross-family, and found that restricting to one judge per family made effective
independence **worse** (n_eff 1.93 vs 2.18). Family is display metadata here, not policy.

The six-judge set above did score 6/6 against the planted-defect corpus described under
[What it actually catches](#what-it-actually-catches), where a two-vendor panel scored
4/6, but **treat that as debugging evidence, not as a result**: the roster was repaired
_because_ of what happened on those very fixtures, so the comparison is in-sample, and the
six defects live in only two files (effective n≈2, 95% CI 61–100%).

What to actually do: pick judges by what they find on _your_ code, and use `panel-recall` to
measure it. The quantity worth maximising is each judge's **marginal rescue rate** — how
often it catches something every other judge on the roster missed — not how many logos are
represented.

Two practical constraints: wall-clock is the **slowest** judge, not the sum, so one slow
model sets the pace for every run; and `claude-*` are deliberately absent from the default,
because when Claude wrote the code under review a Claude judge shares the author's blind
spots. Add it explicitly when that isn't the case — it is strong.

## Using it

- `--diff` attaches the working-tree diff, so nobody has to describe the change —
  including you, who would describe it favourably.
- `--rebut` adds the optional second round, in which judges see each other's findings
  under Reviewer A/B/C labels instead of model names. The relabelling is best-effort: a
  review that names its own model or vendor makes `llm-panel` print a warning; the text
  is not redacted. Worth running whenever a finding would trigger real work. To be precise about the report's grouping of that round: it keys on the rebuttal letter
  each finding is given (A1, B2 …), so it collects the _discussion_ around one judge's
  finding. It is **not** semantic clustering — two judges independently raising the same
  underlying defect stay two findings, and without `--rebut` there is no grouping at all.
- `--judges a,b,c` overrides the default panel. `codex~2` runs the same model a second
  time as a **full, separate judge** — its own file, its own letter, its own row.
  Collapsing repeats would hide exactly the disagreement that makes them worth running.
- `--thread NAME` keeps a persistent conversation per judge. For design questions, not review.
- `--image PATH` (repeatable) attaches an image. Only the `vis-*` and `claude-*` judges can
  look at it; every other judge reports `unavailable` rather than answering blind, and
  `--vision-check TEXT` makes each judge quote something visible before it is believed.
- `--live` prints each answer the moment it lands instead of waiting for the slowest judge;
  `--stream` echoes tokens as they arrive, which only ollama and claude judges can honour.
  Without either, a heartbeat still names who is still working.
- `--runs` lists past panels for this repo (`--all-repos` for every repo) and `--show`
  prints the latest report. `--effort {low,…,max}` sets reasoning effort where a judge has
  the setting; `--timeout SECONDS` caps each judge, and a judge over the deadline is killed
  as a whole process group and reported `harness`. `-f FILE` reads the prompt from a file.
- Long questions go via stdin: `llm-panel - <<'ASK' … ASK`.
- `--synthesize JUDGE` asks one judge to fold every answer into a single synthesis after
  the round; `--cwd DIR` reviews a repository other than the current one; `--save-here`
  writes the panel into the reviewed repo as well as the cache; `--agent NAME` picks the
  opencode agent (default `panelist`) and `--keep-alive` the ollama model residency.
  `panel-report` takes `--repo SUBSTR` to pick a run root, `--out FILE`, `--webfonts` and
  `--max-image-kb`; `panel-triage` takes `--since HOURS`, `--repo`, `--limit` and `--json`.
- `--usage` / `--reset-usage` show, and redeem one of, the `codex` judge's plan limits as
  `codex app-server` reports them; see
  [`docs/codex-usage.md`](https://github.com/musharna/llm-panel/blob/main/docs/codex-usage.md).

### On pull requests

The repository doubles as a GitHub Action. It builds a prompt from the PR's diff, runs the
panel in the checked-out tree, and posts every judge's answer in full as one comment,
edited in place on each push rather than added to:

```yaml
# .github/workflows/panel.yml
on: pull_request
permissions: { contents: read, pull-requests: write }
jobs:
  panel:
    if: github.event.pull_request.head.repo.full_name == github.repository # forks have no secrets
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: musharna/llm-panel@v0.1.9
        with:
          openrouter-api-key: ${{ secrets.OPENROUTER_API_KEY }}
          # judges: or-glm,or-kimi,or-deepseek   timeout: "600"   extra-args: --rebut
```

The default judges are the three OpenRouter ones, so one key is the whole setup. They
read the checked-out tree, not just the diff: on this repository's own 8-file
[PR #3](https://github.com/musharna/llm-panel/pull/3#issuecomment-5561530052) the three
read 282k–1.13M input tokens each and the panel billed **$0.9733** in total, kimi-k3 the
largest share ($0.55); the slowest judge took 266 s. That is one run, measured
2026-09-06. The job fails on
exit 9 — the PR's tree carries `.opencode/` or claude hooks the judges would run — and
posts the panel on 0 or 4. This repository runs it on its own pull requests
(`.github/workflows/panel.yml`, installing from source).

Judges reading through `codex`/`opencode`/`claude` can **read your repo**. `ollama` judges
answer from the prompt alone with no tool loop, so they cannot verify a claim against code.
Treat their findings accordingly.

Exit codes are deliberate and `llm-panel --help` lists them: 0 every judge answered ·
1 usage, config, or a failure of this program · 2 `--file` could not be read · 3 `--check`
found a judge that could not answer at all · 4 degraded panel (a judge never ran — our
failure, reported as such) · 7/8 `--diff` could not produce a diff / had nothing to review ·
9 the opencode agent or the reviewed tree is not verified safe · 10 `--thread` is locked by
another run · 11/12 `--repeat` out of range / a repeat suffix typed by hand · 13 illegal
judge name · 14 none of the selected judges has its CLI installed, with the roster path in
the message · 130 interrupted (Ctrl-C or SIGTERM), with whatever landed kept in the run
directory.

The rendered report — the scoreboard counts spend and names who answered; the
citation-overlap tables show where the panel's attention landed (three judges reviewing a
[cline](https://github.com/cline/cline) PR, converging on one line of `TerminalProcess.ts`):

![panel report: scoreboard, bench, and citation-overlap tables](https://raw.githubusercontent.com/musharna/llm-panel/main/docs/report.png)

## What it actually catches

`recall/panel-recall` is the part most tools like this don't have: a corpus of defects
planted in real code, each one **proven to misbehave by execution**, so "the panel missed
it" is a measurement rather than an impression.

> **At least one of four independent passes (codex ×2 + claude-opus ×2) matched 25 of 27
> known targets in this controlled, single-file Python corpus** (grading inputs not
> published). That is a keyword-matched lower bound on an easy corpus — not an estimate of
> real-world code-review capability.
> 95% CI 76.6–97.9%, and that is before accounting for defects clustering within fixtures.

Hand-planted single-mechanism defects in ~40-line files are far easier than real defects
in mature codebases ([CR-Bench](https://arxiv.org/html/2603.11078v1) reports GPT-5.2 +
Reflexion at 32.8% recall on `git blame`d real bugs), so this corpus is a **development
instrument** for controlled A/Bs, not evidence of capability. Three things it did settle —
the two misses were the roster's fault, not the models' (a six-vendor panel found both);
running the same model twice recovered nothing where adding a different vendor did; and
one sentence of abstention licence trades real findings for zero false positives — are
written up with their numbers in
[`recall/README.md`](https://github.com/musharna/llm-panel/blob/main/recall/README.md).

## On real PRs (AACR-Bench)

The real-world numbers come from running the panel over
[AACR-Bench](https://github.com/alibaba/aacr-bench) PRs and scoring the findings with
**upstream's own evaluator** — an LLM judge doing path → line → semantic matching, so the
numbers are theirs, not a self-graded matcher's. 18 PRs, a three-judge panel (one
subscription model, two free-tier), three prompt styles
(`recall/aacr-upstream --prompt-style`). The default row is the shipped prompt measured at
`e2ad666` (2026-09-06); the other two are re-measurements from 2026-08-28:

| `--prompt-style`   | semantic recall | precision | findings read per validated hit |
| ------------------ | --------------- | --------- | ------------------------------- |
| `defect` (default) | 9.8%            | 9.5%      | 10.5                            |
| `broad`            | 26.0%           | 13.2%     | 7.6                             |
| `volume`           | 25.2%           | 7.9%      | 12.6                            |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/bench-dark.png">
  <img alt="recall against precision for the three prompt styles; error bars are the ±2 pp re-run noise floor" src="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/bench-light.png" width="660">
</picture>

Against the `defect` row above, `broad` has higher recall and fewer findings read per
validated hit (7.6 vs 10.5). Its significance test is against an earlier arm: paired with
the pre-rewrite `defect` prompt (12.2% recall, 6.1 findings read per hit), `broad` doubled
recall (McNemar on paired references, p = 0.0005) for 25% more reading per hit (6.1 → 7.6).
`volume` reaches `broad`'s recall by verbosity alone, at lower precision (7.9% vs 13.2%). A declared
cost cut kept `defect` as the default for its precision and names `broad` the only
candidate for a future change (`recall/benchmarks/cost-cut/README.md`).

**Against the paper's own baselines, the panel's precision is ordinary and its recall is
low.** [AACR-Bench's Table 3](https://arxiv.org/abs/2601.19494) (v3, 2026-01-30), single
models on all 200 PRs, "No context" — the diff plus title and description, no repository
code — is the closest published condition to the diff-in-prompt arm above:

| paper, "No context", all 200 PRs | recall | precision |
| -------------------------------- | ------ | --------- |
| GPT-5.2                          | 47.1%  | 7.0%      |
| Claude-4.5-Sonnet                | 42.9%  | 8.7%      |
| DeepSeek-V3.2                    | 36.5%  | 5.6%      |
| GLM-4.7                          | 27.6%  | 11.3%     |
| Qwen-480B-Coder                  | 27.4%  | 9.4%      |
| this panel, `defect`, 18 PRs     | 9.8%   | 9.5%      |
| this panel, `broad`, 18 PRs      | 26.0%  | 13.2%     |

The rows are **not directly comparable**: ours is an 18-PR subsample scored with a
different judge model, without the PR title and description, and it is one subscription
model plus two free-tier ones against single frontier models. What can be said: `defect`
sits at the low-recall end of that spread, `broad` sits inside the paper's recall range at
better-than-paper precision, and nothing here has been measured on the full 200. The
variance floor is measured (effects under ~5–7 pp are re-run noise at this n), three
earlier readings were withdrawn on re-measurement and nothing above rests on one, and
location agreement overstates semantic agreement ~2x (22.8% vs 12.2% of references) — which is why scoring is
delegated upstream. The full comparability caveats, every run ledger and the data
licensing are in
[`recall/benchmarks/README.md`](https://github.com/musharna/llm-panel/blob/main/recall/benchmarks/README.md).

## Tests

```sh
./claimlib-controls              #  90
./llm-panel-controls             # 466
./panel-report-controls          # 353
./panel-triage-controls          #  27
./recall/aacr-upstream-controls  # 118
./recall/aacr-recut-controls     #  27
./privacy-controls               #  10
cd recall && ./panel-recall selftest && python3 validate_corpus.py
```

CI runs all seven suites on every push (Python 3.11, 3.12 and 3.13).

Most sections target a defect that **shipped**, and assert the fixed behaviour _and_ —
where the pre-fix input is representable — that the broken version would have failed on
it. The rest guard new behaviour (the roster loader, the re-cut's join) or are the positive
and negative controls that keep the others honest. An assertion that passes on both the broken and the fixed code tells you
nothing.

## Known limitations

- **The judge roster's shipped defaults will not work for you** until you configure it.
- **Judges can read the working tree.** `--diff` sends untracked file contents to remote
  APIs. Don't point it at a repo holding secrets you haven't gitignored.
- **Reviewing a repository means trusting its `.opencode/`, `opencode.json[c]`,
  `.claude/settings*.json` hooks and `.mcp.json`.**
  opencode loads plugins, tools and agent definitions from the tree it is pointed at, so
  a repository can ship code that a judge would run as you. `llm-panel` refuses (exit 9)
  when the tree carries any of that. `claude -p` was measured to run a tree's
  `.claude/settings.json` hooks with no trust prompt, so a claude judge is refused the same
  way when the tree declares hooks or `.mcp.json`; `--unsafe-agent` overrides all of it.
- **A prompt over 128 KB is written to `<repo>/.llm-panel-material/` for the run** so
  judges' read tools can reach it; it is removed when the run ends, on any exit. On a
  shared host, the prompt is also visible in the judge processes' command lines while
  they run.
- **A panel is not a jury.** Independent models generate candidates; verification against
  code, tests, and execution is still yours to do.
- **Recall is measured on a 27-defect Python corpus.** That number does not transfer to
  other languages or to defect classes the corpus doesn't contain.
- **The headline recall numbers are prompt- and condition-specific.** They move with
  `--prompt-style`, roster health, and diff-vs-checkout context — see
  [On real PRs](#on-real-prs-aacr-bench) before quoting any of them.
- **Every other fixture has verified _scope_, not proven absence.** Their known unplanted
  defects are recorded in each `truth.json` and re-checked by execution in
  `validate_corpus.py`, so a judge that finds one is not scored as wrong. Anything not yet
  recorded still depresses the recall floor by making a true finding look like noise.

## License

MIT — see [LICENSE](https://github.com/musharna/llm-panel/blob/main/LICENSE). The MIT
grant covers the code in this repository; the benchmark data under `recall/benchmarks/`
contains third-party material (PR diffs and review-comment text) that stays under its
upstream terms — see
[recall/benchmarks/PROVENANCE.md](https://github.com/musharna/llm-panel/blob/main/recall/benchmarks/PROVENANCE.md).
