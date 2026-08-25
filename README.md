# llm-panel

Put the same question to several models independently, then read every answer in full.

Judges run in parallel, never see each other's work, and answer from their own reading of
your repo. An optional second round shows each of them the others' findings — anonymised —
and asks them to defend or withdraw. The output is a single self-contained HTML page
organised **by claim**, so comparing what five models said about one line of code doesn't
mean holding five documents in your head.

It is not a voting machine. A panel _generates candidate defects_; it does not establish
truth by counting agreements. Every finding still has to be checked against the code.

```
llm-panel --diff "Which of these changes is most likely to be wrong?"
panel-report --open          # render the newest run and open it
panel-triage --bad           # which runs went wrong, across every run root
```

## What's here

|                       |                                                                               |
| --------------------- | ----------------------------------------------------------------------------- |
| `llm-panel`           | asks the judges, in parallel, and writes the run to disk                      |
| `panel-report`        | renders a run as one self-contained HTML page, grouped by claim               |
| `panel-triage`        | finds the runs that _failed_, which a listing shows as ordinary rows          |
| `recall/panel-recall` | measures what the panel **misses**, against a corpus of planted defects       |
| `*-controls`          | the regression suites — 539 controls, every one tied to a defect that shipped |

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

**Pick for vendor diversity, not judge count.** Three judges from one vendor is one opinion
wearing three hats. The six above are six distinct families (OpenAI / NVIDIA / Zhipu /
Moonshot / DeepSeek / xAI); measured against the corpus they find 6/6 where a two-vendor
panel finds 4/6. Two further constraints worth knowing: wall-clock is the **slowest** judge,
not the sum, so one slow model sets the pace for every run; and `claude-*` are deliberately
absent from the default, because when Claude wrote the code under review a Claude judge
shares the author's blind spots. Add it explicitly when that isn't the case — it is strong.

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

On the 27-defect corpus a **two-vendor** panel (codex + claude-opus, each twice) finds
**25/27 (93%)**. Which panel found it is part of the number, not a footnote — see below.

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
- **Telling judges they may say "nothing is wrong here" costs real findings.** Removing
  one sentence of abstention licence moved findings from 0.42 to 2.17 per fixture and
  abstention from 67% to 0%. But the licence bought that abstention by suppressing
  _verified-true_ findings — one judge went 3.00 → 0.00 on files that do contain real
  defects. Whether it suppresses _false_ findings is **untested**, because no fixture here
  has proven absence of defects. On a file whose defects aren't enumerated, "abstained"
  and "missed" are the same observation.

## Tests

```sh
./llm-panel-controls        # 224
./panel-report-controls     # 300
./panel-triage-controls     #  15
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
- **The abstention behaviour above is unresolved**, and it is the honest open question:
  no fixture here proves absence, so the false-positive rate is not something this repo
  can currently report.

## License

MIT — see [LICENSE](LICENSE).
