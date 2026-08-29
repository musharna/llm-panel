# Human-authored references: broad vs volume, pre-registered (2026-08-29)

**Result: the pre-registered hypothesis is not supported.** On 150 human-authored valid
references across 35 PRs, `broad` matched 18 (12.0%) and `volume` 16 (10.7%); discordant
pairs 9 / 7; one-sided McNemar (broad > volume) **p = 0.40**, two-sided 0.80. The seed-42
observation that generated the hypothesis (10/38 vs 5/38, broad never losing a human match)
did not replicate on a fresh sample.

The protocol is `PREREG.md` (committed before any panel ran, with the run-time deviations
appended before scoring). Sample `../upstream/pos-human-n35.jsonl`; arms identical except
`--prompt-style`; effort high, timeout 900 s, `--cwd-mode empty`, extractor 3; scored once
by the upstream evaluator with `anthropic/claude-opus-4.5`. Scores:
`../scores/human-{broad,volume}-pos.json`. Test: `python3 ../aacr-mcnemar scores human-broad human-volume`.

## Pooled and by category (descriptive)

| cut | n | broad | volume | only-broad / only-volume | two-sided p | one-sided (broad>volume) |
|---|---|---|---|---|---|---|
| human-authored (primary) | 150 | 18 (12.0%) | 16 (10.7%) | 9 / 7 | 0.80 | **0.40** |
| AI-authored | 296 | 53 (17.9%) | 65 (22.0%) | 18 / 30 | 0.11 | 0.97 |
| all | 446 | 71 (15.9%) | 81 (18.2%) | 27 / 37 | 0.26 | 0.92 |
| defect-y categories | 240 | 53 (22.1%) | 65 (27.1%) | 19 / 31 | 0.12 | 0.97 |
| maintenance categories | 206 | 18 (8.7%) | 16 (7.8%) | 8 / 6 | 0.79 | 0.40 |

Wilson 95% CIs, all refs: broad [12.8, 19.6], volume [14.9, 22.0]. Output: broad 738
findings at 9.6% precision (semantic match rate), volume 1,466 at 5.5% — the same 2x volume
/ half precision pattern as the seed-42 sample, at lower recall for both arms (this sample
is the 35 PRs with the *most* human comments, excluding seed 42; it is not a random draw).

## The roster substitution is not nil

Codex hit its weekly cap after 14 PRs; the remaining 21 ran with the same model
(`gpt-5.6-sol`) through OpenRouter under opencode (`or-gpt`). The deviation note promised a
per-slot cut so the effect of the substitution would be visible rather than assumed away.
It is visible:

| PRs | human refs | broad | volume | only-broad / only-volume | one-sided p |
|---|---|---|---|---|---|
| codex on both arms (13) | 81 | 10 (12.3%) | 4 (4.9%) | 7 / 1 | 0.035 |
| or-gpt on both arms (21) + mixed (1) | 69 | 8 (11.6%) | 12 (17.4%) | 2 / 6 | 0.97 |

Under the codex CLI the pilot's direction reappears (broad > volume on human references,
7 vs 1 discordant); under opencode + OpenRouter it reverses. Two readings, not separable
here:

1. *Harness.* Same model, different tool loop and effort plumbing (`--variant high` vs
   `model_reasoning_effort`); the volume prompt's "be exhaustive" may land differently.
   or-gpt's volume arm produced 820 findings over 22 PRs (37/PR) to codex's 646 over 13
   (50/PR), so it is not simply more verbose.
2. *PR mix.* The sample is ordered by human-comment count, so the codex PRs are the 13
   richest in human comments (81 of 150 refs) and the or-gpt PRs the leaner 22. Slot and
   PR-richness are confounded by construction.

Neither cut is confirmatory: the codex subset has 8 discordant pairs, and the split was not
the pre-registered test. What the full sample says is the result; what the split says is
that "same model" did not mean "same reviewer", and any future arm must hold the transport
fixed or randomise it across PRs.

## What this closes and what it opens

- The seed-42 README's claim that broad's content "reaches human-authored references that
  volume does not" is **withdrawn as a general claim**; it holds on the codex-CLI subset of
  this sample and fails on the rest. The root README now says so.
- Verbosity vs content, on the numbers that survived: volume-matched verbosity reproduces
  broad's recall on every cut of both samples; broad buys precision (9.6% vs 5.5% here,
  13.2% vs 7.9% on seed 42), not a different population of references.
- Open: a transport-controlled replication (all-codex after the cap resets, or all-or-gpt),
  which is cheap ($6 of OpenRouter for 42 panels here) once the roster is held fixed.

## Run ledger

- Panels: 70 (35 × 2). Slots answered: broad 105/105, volume 104/105 (SDL@96dfef3 volume,
  big-pickle 429 on five attempts). Codex-slot PRs: broad 14, volume 13.
- Deviations (all in `PREREG.md`): transport substitution after PR 14; bridge E2BIG crash on
  an 839 KB diff, fixed in `ea38c1c` before PRs 31–35 ran (no judge reached during the
  loop); one extra retry each on three.js volume (restart) and SDL volume (burst).
- Cost: $5.95 OpenRouter for the 42 or-gpt panels; codex panels on subscription quota; judge
  scoring on OpenRouter (Opus 4.5) not itemised here.
- Binaries: `BINARIES.txt` (md5 of the pinned `llm-panel`, `claimlib.py`, `aacr-upstream`
  before and after the E2BIG fix).
