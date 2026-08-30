# Transport-controlled replication: broad vs volume on human-authored references, all-or-gpt (2026-08-30)

**Result.** With every panel on one transport, the codex-CLI subset's broad-over-volume
advantage does not reproduce, and the full-sample human-reference comparison runs the other
way: `broad` 13/150 (8.7%) vs `volume` 23/150 (15.3%), discordant 5 / 15, one-sided McNemar
(broad > volume) **p = 0.99**, two-sided 0.04. H1 (the original pre-registered direction) is
not supported for the second time. H2, the pre-declared discriminator, lands on the
"advantage vanishes" branch: on the 13 PRs that both arms had run on the codex CLI, the
codex panels gave broad 10 vs volume 4 (7 / 1); the same 13 PRs on `or-gpt` give 5 vs 10
(3 / 8, one-sided p = 0.97). **Same model, different harness, different reviewer** — the
original per-slot split was a transport effect, not a property of the richer PRs.

Protocol: `PREREG.md` (committed at e3aa2cb before any panel ran). Sample, arms, extractor,
evaluator and retry policy as in `../results-human-2arm/PREREG.md`; the 43 panels already on
`or-gpt` were reused verbatim, the 27 codex-transport panels re-run with the slot filled by
`or-gpt` (`openai/gpt-5.6-sol` via OpenRouter under opencode). Scores
`../scores/human-orgpt-{broad,volume}-pos.json`; test
`python3 ../aacr-mcnemar scores human-orgpt-broad human-orgpt-volume [h2-codex-both-ids.txt]`.

## H1 — full sample, all cuts

| cut | n | broad | volume | only-broad / only-volume | two-sided p | one-sided (broad>volume) |
|---|---|---|---|---|---|---|
| human-authored (primary) | 150 | 13 (8.7%) | 23 (15.3%) | 5 / 15 | 0.04 | **0.99** |
| AI-authored | 296 | 53 (17.9%) | 72 (24.3%) | 22 / 41 | 0.02 | 0.99 |
| all | 446 | 66 (14.8%) | 95 (21.3%) | 27 / 56 | 0.002 | 1.00 |
| defect-y categories | 240 | 47 (19.6%) | 77 (32.1%) | 19 / 49 | 0.0004 | 1.00 |
| maintenance categories | 206 | 19 (9.2%) | 18 (8.7%) | 8 / 7 | 1.0 | 0.50 |

Wilson 95% CIs, all refs: broad [11.8, 18.4], volume [17.8, 25.3]. Output: broad 671
findings at 9.8% semantic precision, volume 1,562 at 6.1%. The verbosity/efficiency pattern
of the two earlier samples holds; on this transport volume's extra findings also buy
recall (pooled +6.5 points, p = 0.002), which they did not on the mixed-transport run
(18.2 vs 15.9, p = 0.26).

## H2 — the 13 codex-both PRs, codex panels vs their or-gpt replacements

| run | human refs | broad | volume | only-broad / only-volume | one-sided p |
|---|---|---|---|---|---|
| original, codex CLI (`../results-human-2arm`) | 81 | 10 (12.3%) | 4 (4.9%) | 7 / 1 | 0.035 |
| this run, or-gpt | 81 | 5 (6.2%) | 10 (12.3%) | 3 / 8 | 0.97 |

Per-PR human-reference matches, codex (broad, volume) → or-gpt (broad, volume):

| PR | refs | codex | or-gpt |
|---|---|---|---|
| lvgl@e526b2a | 18 | 4, 2 | 1, 5 † |
| waveterm@61b0fb4 | 9 | 2, 1 | 1, 1 |
| react@b045f18 | 5 | 2, 0 | 1, 0 |
| Checkmate@32b54dd | 4 | 1, 0 | 1, 2 |
| SDL@1526727 | 5 | 1, 0 | 1, 0 ‡ |
| appwrite@710b8bd | 5 | 0, 1 | 0, 2 |
| other 7 PRs | 35 | 0, 0 | 0, 0 |

† or-gpt broad panel stood 2/3 (nemotron `harness` twice). ‡ or-gpt volume panel stood 2/3
(or-gpt `tool-calls` stop ×4). Both within the fixed retry policy; neither re-asked.

**Sensitivity (the reversal vs the vanishing).** The reversal is carried by lvgl, whose
or-gpt *broad* panel is the one missing a judge. Excluding lvgl (12 PRs, 63 refs): codex
broad 6 vs volume 2 (5 / 1, one-sided p = 0.11) → or-gpt 4 vs 5 (3 / 4, p = 0.77). Excluding
both degraded PRs (11 PRs, 58 refs): or-gpt 3 vs 5 (2 / 4). Full-sample H1 without the two
degraded PRs: human 11 vs 18 (4 / 11, two-sided p = 0.12); pooled 62 vs 89 (p = 0.002). So:
*volume > broad on human references* is nominal and leans on a 2/3 panel; *broad > volume
does not survive the transport change* holds on every cut.

**Positive control.** The 22 PRs whose panels were reused verbatim were re-scored by the
evaluator: 8 / 12 human matches yesterday, 8 / 13 today — one reference flipped in 69, so the
evaluator's stochasticity is not what moved the 13 re-paneled PRs (10, 4 → 5, 10).

## Reading

- The seed-42 claim ("broad reaches human-authored references volume does not") is now
  0-for-2 on fresh samples and its one surviving foothold — the codex-CLI subset — was a
  harness artefact. Withdrawn without residue.
- What the harness changes is the review, not the model's knowledge: the same
  `gpt-5.6-sol` behind codex's tool loop favours the `broad` prompt; behind opencode's it
  favours `volume`. A benchmark number for a "model" is a number for a model-in-a-harness.
  Any future arm holds the transport fixed, as this run did.
- Not tested here, and the natural next cut: per-judge recall (extract each panel with
  `aacr-upstream reextract --judges <one>`) would say whether the swing is in the gpt slot
  itself or in how the panel merge weighs it against big-pickle and nemotron.

## Run ledger

- Panels: 27 re-run (14 broad, 13 volume) + 43 reused. Attempts: 42 (15 retries under the
  fixed policy: 6 `unavailable`, 9 `harness`). No beyond-policy retry this time.
- Slots answered: broad 104/105 (lvgl broad, nemotron), volume 103/105 (SDL@1526727 volume,
  or-gpt; SDL@96dfef3 volume, big-pickle — carried over from the reused panels).
- Wall: 11:20–16:36 EDT; evaluator 16:37–16:50, 0 judge failures.
- Cost: $8.02 OpenRouter for the 42 attempts (the $3.80 estimate omitted retries); evaluator
  scoring on OpenRouter (Opus 4.5) not itemised.
- Binaries: `BINARIES.txt` — same pinned `llm-panel` / `claimlib.py` / `aacr-upstream`
  (md5 4f66beab…) as the original run's post-fix half.
