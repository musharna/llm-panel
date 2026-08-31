# llm-panel

Put the same question to several models independently, then read every answer in full.

Judges run in parallel, never see each other's work, and answer from their own reading of
your repo. An optional second round shows each of them the others' findings — anonymised —
and asks them to defend or withdraw. The output is a single self-contained HTML page where
that second round is grouped **by the finding being argued about**, so comparing what five
models said about one line of code doesn't mean holding five documents in your head.

To be precise about what that grouping is and isn't: it keys on the rebuttal letter each
finding is given (A1, B2 …), so it collects the _discussion_ around one judge's finding. It
is **not** semantic clustering — two judges independently raising the same underlying defect
stay two findings, and with `--rebut` omitted there is no grouping at all.

It is not a voting machine. A panel _generates candidate defects_; it does not establish
truth by counting agreements. Every finding still has to be checked against the code.

```
llm-panel --diff "Which of these changes is most likely to be wrong?"
panel-report --open          # render the newest run and open it
panel-triage --bad           # which runs went wrong, across every run root
```

## What's here

|                        |                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------- |
| `llm-panel`            | asks the judges, in parallel, and writes the run to disk                               |
| `panel-report`         | renders a run as one self-contained HTML page, grouped by claim                        |
| `panel-triage`         | finds the runs that _failed_, which a listing shows as ordinary rows                   |
| `recall/panel-recall`  | measures what the panel **misses**, against a corpus of planted defects                |
| `recall/aacr-upstream` | runs the panel over AACR-Bench PRs and hands the findings to **upstream's** evaluator  |
| `recall/aacr-score`    | invokes that evaluator, and refuses to report a number from a judge that isn't running |
| `claimlib.py`          | the one measurement boundary: reviews → span-grounded observations                     |
| `*-controls`           | the regression suites — 715 controls, every one tied to a defect that shipped          |

## Install

Pure Python 3.11+ standard library. No dependencies, no build step, nothing to pip install.

```sh
git clone <this repo> ~/llm-panel
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

## Configure your roster

**The built-in judge list is a default, not a fixture — it names the author's accounts.**
Yours will be different. Point the roster at models you actually have:

Copy [`roster.example.json`](roster.example.json) to
`~/.config/llm-panel/roster.json` (`$XDG_CONFIG_HOME` honoured; `$LLM_PANEL_CONFIG` wins).
It is strict JSON — no comments, no trailing commas — because a typo'd key is fatal rather
than silently ignored:

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

**How to pick judges — and why "one per vendor" is _not_ the answer.** It is tempting to
treat vendor labels as a proxy for independent opinions. The evidence says they aren't:
[Kohli 2026](https://arxiv.org/html/2605.29800) measured cross-family judge correlation at
φ̄=0.389 against same-family 0.437 — barely different — with the three _most_ correlated pairs
being cross-family, and found that restricting to one judge per family made effective
independence **worse** (n_eff 1.93 vs 2.18). Family is display metadata here, not policy.

The six-judge set above did score 6/6 against this corpus where a two-vendor panel scored
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

A malformed config is **fatal** and names the offending key. Quietly falling back to the
built-in roster would run a panel you didn't ask for, and bill you for it.

## Using it

- `--diff` attaches the working-tree diff, so nobody has to describe the change —
  including you, who would describe it favourably.
- `--rebut` adds the anonymised second round. Worth it whenever a finding would trigger
  real work: the first run of it killed three confident findings that were simply wrong.
- `--judges a,b,c` overrides the default panel. `codex~2` runs the same model a second
  time as a **full, separate judge** — its own file, its own letter, its own row.
  Collapsing repeats would hide exactly the disagreement that makes them worth running.
- `--thread NAME` keeps a persistent conversation per judge. For design questions, not review.
- Long questions go via stdin: `llm-panel - <<'ASK' … ASK`.

Judges reading through `codex`/`opencode`/`claude` can **read your repo**. `ollama` judges
answer from the prompt alone with no tool loop, so they cannot verify a claim against code.
Treat their findings accordingly.

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

## Tests

```sh
./claimlib-controls              #  77
./llm-panel-controls             # 277
./panel-report-controls          # 307
./panel-triage-controls          #  15
./recall/aacr-upstream-controls  #  39
cd recall && ./panel-recall selftest && python3 validate_corpus.py
```

Every control corresponds to a defect that **shipped**, and each asserts the fixed
behaviour _and_ — where the pre-fix input is representable — that the broken version would
have failed on it. An assertion that passes on both the broken and the fixed code tells you
nothing.

## Known limitations

- **The judge roster's shipped defaults will not work for you** until you configure it.
- **Judges can read the working tree.** `--diff` sends untracked file contents to remote
  APIs. Don't point it at a repo holding secrets you haven't gitignored.
- **A panel is not a jury.** Independent models generate candidates; verification against
  code, tests, and execution is still yours to do.
- **Recall is measured on a 27-defect Python corpus.** That number does not transfer to
  other languages or to defect classes the corpus doesn't contain.
- **On real PRs, what you ask for determines what you get.** Scored by
  [AACR-Bench](https://github.com/alibaba/aacr-bench)'s **own** evaluator with a real LLM
  judge, on 18 PRs at full roster: the shipped `defect` prompt scores **12.2% semantic
  recall / 16.5% precision**, and a `broad` prompt asking for what a careful maintainer
  would actually raise scores **26.0% / 13.2%** — 2.13x the recall for a slightly lower hit
  rate and 2.7x the output. That gain is exactly volume: findings x2.67, precision x0.80
  (McNemar on the paired references, p = 0.0005). Figures are extractor-3 re-measurements
  (2026-08-28); extractor 2 silently dropped plain `- path:line` bullets, and the loss fell
  on the `defect` arms, not `broad`.
  A volume-matched control settles what that gain is: the `defect` prompt told only to be
  exhaustive scores **25.2%** (31/123, vs broad p = 1.0) — but with 392 findings at 7.9%
  precision to broad's 243 at 13.2%. Verbosity alone buys the recall; the broad prompt's
  content buys efficiency. An earlier draft added "and a different set of hits (more
  human-authored references)"; a pre-registered replication on 35 fresh PRs (150
  human-authored references) found broad 12.0% vs volume 10.7%, one-sided p = 0.40 — the
  claim is withdrawn. A transport-controlled re-run (every panel through one harness) found
  8.7% vs 15.3%, and the claim's one foothold — a 13-PR subset that had run through the
  codex CLI — did not survive a re-run; a per-judge cut showed a same-transport re-run of
  another judge moved as much, so the subset was noise, not a harness effect. A full-sample
  variance floor (single-judge re-extractions of both runs, evaluator replicate included)
  put a same-judge re-run at up to ±3 human-ref matches of 150 with zero evaluator noise —
  human-ref effects under ~5–7 pp of recall are inside re-run noise at n=35, which every
  subgroup claim so far was. A declared cost cut over all of it settled the default:
  volume's recall is bought at half broad's precision and ~16–18 findings read per
  validated hit (defect: 6.1), so the default stays `defect`; the only candidate for a
  future default change is `broad` (`recall/benchmarks/cost-cut/README.md`). See
  `recall/benchmarks/results-volume-3judge/README.md`,
  `recall/benchmarks/results-human-2arm/README.md` and
  `recall/benchmarks/results-human-2arm-orgpt/README.md`.
  An earlier version of this bullet split recall by a DEFECT/IMPROVEMENT classifier I
  wrote; that split was circular and is withdrawn — on the benchmark's own `category`
  field the `defect` prompt recalls both classes at the same rate. The default stays
  `defect`; both ship behind `--prompt-style`. See
  `recall/benchmarks/results-broad-3judge/README.md`.
- **The benchmark judges read the diff, not the repository.** `aacr-upstream` runs each
  panel in an empty temporary directory with the diff in the prompt, so the numbers above
  are diff-in-prompt review. A reviewer with the checkout — as the benchmark's own
  reviewers have — can see callers, tests and history that these judges cannot.
  The paired repo-access arm (`--cwd-mode checkout`, same instances and roster) puts the
  judges in a shallow checkout of the PR head: recall moves 12.2% → 15.4% (15 → 19 of the
  same 123 references) but McNemar p = 0.48, and the checkout **loses 7** of the clean
  arm's matches while gaining 11 — repo access changes what judges attend to rather than
  strictly adding. Findings rise 91 → 157 at precision 16.5% → 12.1%, sitting between the
  clean and broad arms on every axis. See
  `recall/benchmarks/results-checkout-3judge/README.md`.
- **Location agreement overstates semantic agreement ~2x.** 22.8% of references had a
  finding at the right file and line; 12.2% had one a judge called the same concern. A
  location-based matcher cannot detect that gap about itself, which is why scoring is
  delegated upstream.
- **A degraded roster costs about half the recall.** The same sample with one judge's quota
  spent and a 300s timeout scores 6.5% semantic recall against 12.2% — same extractor
  (3), so only roster and timeout differ. Two instances returned nothing at 300s purely by hitting
  the cap while holding 20 of the 123 references.
- **There is no valid-vs-rejected gap to read.** Under extractor 3 the panel matched 12.2%
  of accepted review comments and 11.1% of _rejected_ ones — ratio 1.10, Fisher exact
  p = 1.0. (Extractor 2 had reported 3.80x at p = 0.194; the recovered bullets matched
  rejected comments at the same rate as accepted ones.) The panel does not discriminate
  comments reviewers accepted from ones they rejected.
- **Unlocated findings are withheld from upstream, not handed over empty.** Upstream skips
  its path filter when the generated path is falsy and its line filter when the line is
  None, so a location-less comment matches _every_ reference. Passing them through inflated
  line matches from 20 to 50 on the first scoring run.
- **Every other fixture has verified _scope_, not proven absence.** Their known unplanted
  defects are recorded in each `truth.json` and re-checked by execution in
  `validate_corpus.py`, so a judge that finds one is not scored as wrong. Anything not yet
  recorded still depresses the recall floor by making a true finding look like noise.

## License

MIT — see [LICENSE](LICENSE).
