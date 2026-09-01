# llm-panel

[![controls](https://github.com/musharna/llm-panel/actions/workflows/controls.yml/badge.svg)](https://github.com/musharna/llm-panel/actions/workflows/controls.yml)
[![pypi](https://img.shields.io/pypi/v/llm-panel.svg)](https://pypi.org/project/llm-panel/)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/musharna/llm-panel/blob/main/LICENSE)
[![python: 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://github.com/musharna/llm-panel/blob/main/pyproject.toml)

Put the same question to several models independently, then read every answer in full.

Judges run in parallel, never see each other's work, and answer from their own reading of
your repo. An optional second round shows each of them the others' findings — anonymised —
and asks them to defend or withdraw. The output is a single self-contained HTML page where
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

The rendered report — the scoreboard counts spend and names who answered; the
citation-overlap tables show where the panel's attention landed (three judges reviewing a
[cline](https://github.com/cline/cline) PR, converging on one line of `TerminalProcess.ts`):

![panel report: scoreboard, bench, and citation-overlap tables](https://raw.githubusercontent.com/musharna/llm-panel/main/docs/report.png)

**Contents:** [What's here](#whats-here) · [Install](#install) ·
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
| `*-controls`           | the regression suites — 890 controls, every one tied to a defect that shipped          |

## Install

Pure Python 3.11+ standard library on Linux, macOS or WSL — it needs POSIX file locks and
process groups, and says so on Windows instead of tracing back. No dependencies, no build
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

If none are present the panel still runs, fails loudly, exits 4, and tells you what to
install. A missing tool is one judge's problem, never the whole panel's.

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
- `--rebut` adds the anonymised second round. Worth it whenever a finding would trigger
  real work: the first run of it killed three confident findings that were simply wrong.
  To be precise about the report's grouping of that round: it keys on the rebuttal letter
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

Judges reading through `codex`/`opencode`/`claude` can **read your repo**. `ollama` judges
answer from the prompt alone with no tool loop, so they cannot verify a claim against code.
Treat their findings accordingly.

Exit codes are deliberate and `llm-panel --help` lists them: 0 every judge answered ·
1 usage, config, or a failure of this program · 2 `--file` could not be read · 4 degraded
panel (a judge never ran — our failure, reported as such) · 7/8 `--diff` could not produce
a diff / had nothing to review · 9 the opencode agent or the reviewed tree is not verified
safe · 11/12 `--repeat` out of range / a repeat suffix typed by hand · 130 interrupted,
with whatever landed kept in the run directory.

The rebuttal round as rendered — every position each judge took on each finding, grouped
by the finding under dispute, disagreements marked CONTESTED. This run: four free-tier
judges asked to review llm-panel's own failure-classification code; one failed and is
reported as `harness`, the other three upheld 7 findings, rejected 4, and missed 6:

![rebuttal round: positions grouped by the finding being argued about](https://raw.githubusercontent.com/musharna/llm-panel/main/docs/rebuttal.png)

## What it actually catches

`recall/panel-recall` is the part most tools like this don't have: a corpus of defects
planted in real code, each one **proven to misbehave by execution**, so "the panel missed
it" is a measurement rather than an impression.

> **At least one of four independent passes (codex ×2 + claude-opus ×2) matched 25 of 27
> known targets in this controlled, single-file Python corpus.** That is a keyword-matched
> lower bound on an easy corpus — not an estimate of real-world code-review capability.
> 95% CI 76.6–97.9%, and that is before accounting for defects clustering within fixtures.

**Read that next to a real-world number.** [CR-Bench](https://arxiv.org/html/2603.11078v1)
(Nutanix, 2026) builds review tasks from _real_ bugs `git blame`d out of merged PRs in
django, sympy, astropy and scikit-learn, and reports GPT-5.2 + Reflexion at **32.8% recall
and 5.1% precision**. The gap between that and 25/27 is the corpus, not the panel: hand-
planted single-mechanism defects in ~40-line files are far easier than real defects in
mature codebases, and the two numbers are not even the same estimand — different agents,
different context, different definitions of a hit.

So this corpus is a **development instrument**, good for controlled A/Bs where ground truth
must be known and iteration must be cheap (the abstention experiment below is exactly that).
It is not evidence of absolute capability, and no number from it should be quoted as one.

Three results worth knowing before you trust any of the output:

- **Recall was limited by the roster, not by the models.** The two defects that panel
  never found — a `.get(k, default)` that doesn't apply to an explicit `null`, and a
  corrupt cache file silently becoming empty — are both found by a **six-vendor** panel
  (OpenAI / NVIDIA / Zhipu / Moonshot / DeepSeek / xAI): 4/6 → **6/6** on those two
  fixtures. The best two judges there, at 4/6 each, beat codex at 2/6 — and both were
  broken or out of credit until the roster was repaired. If your panel is missing things,
  check who is actually answering before concluding the models can't see it.
- **Running the same model twice recovered nothing.** First passes 25/27, with repeats
  25/27. The repeat-passes idea is well supported in the literature and did not reproduce
  here. An earlier grader bug reported +1 and it was an artifact. Adding a _different
  vendor_ did what adding a second pass of the same one could not.
- **Letting judges say "nothing is wrong here" is a precision/recall trade, not a free
  win either way.** One sentence of abstention licence is the whole difference.

  |             | findings/fixture | false positives       |
  | ----------- | ---------------- | --------------------- |
  | licence on  | 0.42             | 0 / 6 judges          |
  | licence off | 2.17             | 2, from 1 of 5 judges |

  Findings-per-fixture is measured on fixtures that _do_ contain defects, where the extra
  findings were verified **true** — so the licence suppresses real findings (one judge went
  3.00 → 0.00 on files with genuine defects). False positives are measured on
  `p01-exhaustive-codec`, the one fixture with **proven** absence rather than verified
  scope — which is what makes a false-positive rate computable at all. There, the same
  judge on the same code abstained with the licence and produced two demonstrably false
  findings without it (it claimed int and str subclasses were rejected; `encode(MyInt(1))`
  returns `'A'`).

  So: the licence costs true findings and prevents false ones. Which you want depends on
  whether chasing a false lead costs you more than missing a real defect. Caveat worth
  stating: one proven fixture, eleven reviews.

## On real PRs (AACR-Bench)

The planted corpus above is a development instrument; the real-world numbers come from
running the panel over [AACR-Bench](https://github.com/alibaba/aacr-bench) PRs and
scoring the findings with **upstream's own evaluator** — a real LLM judge doing
path → line → semantic matching, so the numbers are theirs, not a self-graded matcher's.
The prompt style is a flag of that harness, `recall/aacr-upstream --prompt-style`, not of
`llm-panel`. On 18 PRs at full roster (extractor-3 re-measurements, 2026-08-28):

| `--prompt-style`   | semantic recall | precision | findings read per validated hit |
| ------------------ | --------------- | --------- | ------------------------------- |
| `defect` (default) | 12.2%           | 16.5%     | 6.1                             |
| `broad`            | 26.0%           | 13.2%     | 7.6                             |
| `volume`           | 25.2%           | 7.9%      | 12.6                            |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/bench-dark.png">
  <img alt="recall against precision for the three prompt styles; error bars are the ±2 pp re-run noise floor" src="https://raw.githubusercontent.com/musharna/llm-panel/main/docs/bench-light.png" width="660">
</picture>

`broad` — asking for what a careful maintainer would actually raise — doubles the
default's recall (McNemar on paired references, p = 0.0005). But the `volume` control
shows what that class of gain is made of: it is the `defect` prompt plus one
exhaustiveness clause, reaches the same recall (p = 1.0 vs broad), and pays for it with
half of broad's precision. On a 35-PR replication the ordering holds on both transports
while every arm's precision falls (broad ~9.7%, volume ~5.5–6.1%, ~16–18 findings read
per hit). A declared cost cut over all of it settled the product default: **it stays
`defect`**; the only candidate for a future default change is `broad`
(`recall/benchmarks/cost-cut/README.md`).

Three things to know before quoting any of it:

- **The variance floor is measured.** Re-running the same judge on the same 35 PRs moves
  up to ±3 human-reference matches of 150, with an evaluator replicate at exactly zero —
  so effects under ~5–7 pp of recall are re-run noise at this n, which every subgroup
  claim so far was.
- **Three earlier readings were withdrawn on re-measurement** — a DEFECT/IMPROVEMENT
  split (the classifier was circular), "broad finds different hits" (pre-registered
  replication on 35 fresh PRs, p = 0.40), and a transport effect that did not survive a
  re-run. Nothing above rests on a withdrawn claim.
- **Location agreement overstates semantic agreement ~2x** (22.8% of references had a
  finding at the right file and line; 12.2% had one a judge called the same concern) —
  which is why scoring is delegated upstream instead of done by a local matcher.

The rest — the repo-checkout arm, what a degraded roster costs, accepted-vs-rejected
comments, why unlocated findings are withheld from upstream — with every run ledger and
the data licensing, is in
[`recall/benchmarks/README.md`](https://github.com/musharna/llm-panel/blob/main/recall/benchmarks/README.md).

## Tests

```sh
./claimlib-controls              #  83
./llm-panel-controls             # 356
./panel-report-controls          # 313
./panel-triage-controls          #  15
./recall/aacr-upstream-controls  #  96
./recall/aacr-recut-controls     #  27
cd recall && ./panel-recall selftest && python3 validate_corpus.py
```

CI runs all six suites on every push (Python 3.11, 3.12 and 3.13).

Every control corresponds to a defect that **shipped**, and each asserts the fixed
behaviour _and_ — where the pre-fix input is representable — that the broken version would
have failed on it. An assertion that passes on both the broken and the fixed code tells you
nothing.

## Known limitations

- **The judge roster's shipped defaults will not work for you** until you configure it.
- **Judges can read the working tree.** `--diff` sends untracked file contents to remote
  APIs. Don't point it at a repo holding secrets you haven't gitignored.
- **Reviewing a repository means trusting its `.opencode/` and `opencode.json[c]`.**
  opencode loads plugins, tools and agent definitions from the tree it is pointed at, so
  a repository can ship code that a judge would run as you. `llm-panel` refuses (exit 9)
  when the tree carries any of that; `--unsafe-agent` overrides, and a claude judge gets a
  note about project hooks instead, because whether `claude -p` loads them is unverified.
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
