# Transport-controlled replication: broad vs volume on human-authored references, all-or-gpt (2026-08-30)

**Result.** With every panel on one transport, the codex-CLI subset's broad-over-volume
advantage does not reproduce, and the full-sample human-reference comparison runs the other
way: `broad` 13/150 (8.7%) vs `volume` 23/150 (15.3%), discordant 5 / 15, one-sided McNemar
(broad > volume) **p = 0.99**, two-sided 0.04. H1 (the original pre-registered direction) is
not supported for the second time. H2, the pre-declared discriminator, lands on the
"advantage vanishes" branch: on the 13 PRs that both arms had run on the codex CLI, the
codex panels gave broad 10 vs volume 4 (7 / 1); the same 13 PRs on `or-gpt` give 5 vs 10
(3 / 8, one-sided p = 0.97). The per-judge cut below then shows the swing is **not** located
in the gpt slot: a same-transport re-run of nemotron swung by the same amount. The
original per-slot split was not a property of the richer PRs; whether it was the harness or
run-to-run variance the data cannot separate, and the noise-floor control points to variance.

Protocol: `PREREG.md` (committed at e3aa2cb before any panel ran). Sample, arms, extractor,
evaluator and retry policy as in `../results-human-2arm/PREREG.md`; the 43 panels already on
`or-gpt` were reused verbatim, the 27 codex-transport panels re-run with the slot filled by
`or-gpt` (`openai/gpt-5.6-sol` via OpenRouter under opencode). Scores
`../scores/human-orgpt-{broad,volume}-pos.json`; test
`python3 ../aacr-mcnemar scores human-orgpt-broad human-orgpt-volume [h2-codex-both-ids.txt]`.

## H1 — full sample, all cuts

| cut                      | n   | broad      | volume     | only-broad / only-volume | two-sided p | one-sided (broad>volume) |
| ------------------------ | --- | ---------- | ---------- | ------------------------ | ----------- | ------------------------ |
| human-authored (primary) | 150 | 13 (8.7%)  | 23 (15.3%) | 5 / 15                   | 0.04        | **0.99**                 |
| AI-authored              | 296 | 53 (17.9%) | 72 (24.3%) | 22 / 41                  | 0.02        | 0.99                     |
| all                      | 446 | 66 (14.8%) | 95 (21.3%) | 27 / 56                  | 0.002       | 1.00                     |
| defect-y categories      | 240 | 47 (19.6%) | 77 (32.1%) | 19 / 49                  | 0.0004      | 1.00                     |
| maintenance categories   | 206 | 19 (9.2%)  | 18 (8.7%)  | 8 / 7                    | 1.0         | 0.50                     |

Wilson 95% CIs, all refs: broad [11.8, 18.4], volume [17.8, 25.3]. Output: broad 671
findings at 9.8% semantic precision, volume 1,562 at 6.1%. The verbosity/efficiency pattern
of the two earlier samples holds; on this transport volume's extra findings also buy
recall (pooled +6.5 points, p = 0.002), which they did not on the mixed-transport run
(18.2 vs 15.9, p = 0.26).

## H2 — the 13 codex-both PRs, codex panels vs their or-gpt replacements

| run                                           | human refs | broad      | volume     | only-broad / only-volume | one-sided p |
| --------------------------------------------- | ---------- | ---------- | ---------- | ------------------------ | ----------- |
| original, codex CLI (`../results-human-2arm`) | 81         | 10 (12.3%) | 4 (4.9%)   | 7 / 1                    | 0.035       |
| this run, or-gpt                              | 81         | 5 (6.2%)   | 10 (12.3%) | 3 / 8                    | 0.97        |

Per-PR human-reference matches, codex (broad, volume) → or-gpt (broad, volume):

| PR                | refs | codex | or-gpt |
| ----------------- | ---- | ----- | ------ |
| lvgl@e526b2a      | 18   | 4, 2  | 1, 5 † |
| waveterm@61b0fb4  | 9    | 2, 1  | 1, 1   |
| react@b045f18     | 5    | 2, 0  | 1, 0   |
| Checkmate@32b54dd | 4    | 1, 0  | 1, 2   |
| SDL@1526727       | 5    | 1, 0  | 1, 0 ‡ |
| appwrite@710b8bd  | 5    | 0, 1  | 0, 2   |
| other 7 PRs       | 35   | 0, 0  | 0, 0   |

† or-gpt broad panel stood 2/3 (nemotron `harness` twice). ‡ or-gpt volume panel stood 2/3
(or-gpt `tool-calls` stop ×4). Both within the fixed retry policy; neither re-asked.

**Sensitivity (the reversal vs the vanishing).** The reversal is carried by lvgl, whose
or-gpt _broad_ panel is the one missing a judge. Excluding lvgl (12 PRs, 63 refs): codex
broad 6 vs volume 2 (5 / 1, one-sided p = 0.11) → or-gpt 4 vs 5 (3 / 4, p = 0.77). Excluding
both degraded PRs (11 PRs, 58 refs): or-gpt 3 vs 5 (2 / 4). Full-sample H1 without the two
degraded PRs: human 11 vs 18 (4 / 11, two-sided p = 0.12); pooled 62 vs 89 (p = 0.002). So:
_volume > broad on human references_ is nominal and leans on a 2/3 panel; _broad > volume
does not survive the transport change_ holds on every cut.

**Positive control.** The 22 PRs whose panels were reused verbatim were re-scored by the
evaluator: 8 / 12 human matches yesterday, 8 / 13 today — one reference flipped in 69, so the
evaluator's stochasticity is not what moved the 13 re-paneled PRs (10, 4 → 5, 10).

## Reading

- The seed-42 claim ("broad reaches human-authored references volume does not") is now
  0-for-2 on fresh samples and its one surviving foothold — the codex-CLI subset — was a
  harness artefact. Withdrawn without residue.
- "Same model, different harness, different reviewer" was this README's first reading of
  H2 and is **withdrawn** by the per-judge cut below: H2 as pre-declared could not tell a
  transport effect from a re-run, because it had no same-transport re-run control. The cut
  supplied one, and it moved as much as the gpt slot. Any future H2 of this shape carries
  its own re-run arm.
- What survives: on 81 human references with per-judge counts of 0–7, a single 13-PR
  subgroup cannot carry a direction claim in either transport. The pilot's claim is
  0-for-2 on fresh samples, and the subset that seemed to keep it alive is within noise.

## Per-judge cut (declared before scoring; `perjudge/DECLARED.md`)

Each of the 13 PRs' panels re-extracted with one judge's review only
(`aacr-upstream reextract --judges <one>`) and scored by the same evaluator; human-reference
matches out of 81, all-reference out of 254 (`perjudge/table.txt`, scores in
`../scores/perjudge/`). The two free slots were re-run on the same transport, so their
change is the noise floor for a same-judge re-run.

| slot                        | codex-run broad / volume | or-gpt-run broad / volume | broad−volume: codex-run → or-gpt-run |
| --------------------------- | ------------------------ | ------------------------- | ------------------------------------ |
| gpt (codex → or-gpt)        | 7 / 3                    | 3 / 5                     | +4 → −2 (swing −6)                   |
| nemotron (same transport)   | 4 / 0                    | 2 / 4                     | +4 → −2 (swing −6)                   |
| big-pickle (same transport) | 2 / 2                    | 1 / 3                     | 0 → −2 (swing −2)                    |

The gpt slot's swing equals nemotron's, whose transport did not change. On all 254
references the picture is the same: gpt 15 / 31 → 13 / 24, nemotron 9 / 10 → 9 / 24,
big-pickle 19 / 14 → 16 / 17 — the or-gpt run's pooled tilt toward volume is mostly
nemotron's volume arm (364 → 507 findings), not the swapped slot. Read: run-to-run variance
of a three-judge panel on 13 PRs is at least as large as the effect the transport swap was
credited with. The transport reading is not falsified, but it is not supported either.

## Variance floor — full sample (declared before scoring; `perjudge35/DECLARED.md`)

The same single-judge re-extraction, extended to all 35 PRs (150 human refs per arm), plus
one duplicate evaluator pass over a byte-identical extraction to separate scoring noise from
panel noise. 13 evaluator passes, 0 failures (`perjudge35/table.txt`, scores in
`../scores/perjudge35/`). The codex judge only answered on its 13-PR quota subset, so the
gpt-slot comparison stays on those PRs; the floor comes from big-pickle and nemotron, whose
model AND transport were identical across the two runs.

- **Evaluator noise is nil.** The replicate pass (codex-broad-nemotron scored twice) matched
  exactly: human 6 vs 6, all 21 vs 21, 0/35 PRs discordant. Every delta below is panel
  stochasticity, not scoring.
- **Same-transport run-to-run deltas, human refs (orgpt-run − codex-run):** big-pickle
  −1 (broad) / +1 (volume), nemotron −1 (broad) / +3 (volume). Floor = 3 matches
  (max |delta|), SD ≈ 1.9 across the four pairs; 2–4 of 35 PRs discordant per pair.
- **On all 446 references** the floor is far worse: deltas −4, +3, +2, **+13** — the +13 is
  nemotron's volume arm, whose findings drifted 861 → 1004 between runs with nothing
  changed. Verbosity drift alone moves all-ref matches by ~40% of a typical judge's total.
- **The transport swap sits inside the envelope.** On the 13 codex-both PRs the gpt slot's
  run-to-run deltas were −4 (broad) / +2 (volume); same-transport judges on the _same_ PRs
  swung −1/+1 (big-pickle) and −2/+4 (nemotron). Nothing about the swapped slot's movement
  exceeds a plain re-run's.
- **Positive control:** restricted to the 13 PRs, 10/12 cells reproduce the 08-30 per-judge
  cut exactly and 2 are within 1 (both nemotron-broad; fresh evaluator pass).

Read: at n=35, a per-judge human-ref effect must exceed ~3 matches (2 SD ≈ 4) to clear a
same-judge re-run, and a panel-level human-ref effect below ~8–10 matches out of 150
(~5–7 pp of recall) is inside re-run noise. The pilot's subgroup claims (deltas of 2–6)
never had a chance at this sample size; this run's all-refs volume>broad result
(95 vs 66 of 446, 21.3% vs 14.8%, p=0.002 — H1 table above) is the only effect measured so
far that clears the floor with room to spare.

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
