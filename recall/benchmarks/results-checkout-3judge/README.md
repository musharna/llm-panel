# Checkout 3-judge run — the same panel, standing in the repository

The paired repo-access arm of the clean run. Same 18+9 instances, same roster
(codex + big-pickle + nemotron), same defect prompt, effort high, timeout 900s, same
upstream judge (`anthropic/claude-opus-4.5`, `judge failures during scoring: 0` both
sides). Exactly two things differ from `../results-clean-3judge`:

1. `--cwd-mode checkout` — each panel runs with `--cwd` on a shallow checkout of the PR
   head instead of an empty temporary directory, and
2. one added prompt sentence (CHECKOUT_NOTE) telling the judges the working directory is
   that checkout.

Binaries md5-pinned in `BINARIES.txt` (source tree clean at `efc3bde`). Same expected
skips as the clean arm: uv@ed57db2 and ComfyUI@cfc3122 (pos), keycloak@1463502 (neg) —
heads unreachable on GitHub, so the paired reference sets are identical.

|              | positive (valid refs) | negative (REJECTED refs) |
| ------------ | --------------------: | -----------------------: |
| instances    |                 18/20 |                     9/10 |
| judge slots  | **54/54**, 0 degraded |    **27/27**, 0 degraded |
| references   |                   123 |                       36 |
| findings     |                   126 |                       65 |
| line matches |            37 (30.1%) |               11 (30.6%) |
| **semantic** |        **19 (15.4%)** |                4 (11.1%) |
| precision    |                 15.1% |                     6.2% |

## Paired against the clean arm: up, but not significant

Same references, same panel, so the right test is McNemar on discordant pairs
(`aacr-recut` join key), not Fisher on the margins:

| cut (pos)    |   n | clean       | checkout    | gained | lost | McNemar p  |
| ------------ | --: | ----------- | ----------- | -----: | ---: | ---------- |
| ALL          | 123 | 13 (10.6%)  | 19 (15.4%)  |     11 |    5 | **0.2101** |
| defect-y     |  78 | 8 (10.3%)   | 14 (17.9%)  |     10 |    4 | 0.1796     |
| maintainable |  45 | 5 (11.1%)   | 5 (11.1%)   |      1 |    1 | 1.0000     |
| AI-authored  |  85 | 8 (9.4%)    | 15 (17.6%)  |     10 |    3 | 0.0923     |
| human        |  38 | 5 (13.2%)   | 4 (10.5%)   |      1 |    2 | 1.0000     |

Negative side: 1 → 4 semantic matches (2.8% → 11.1%), McNemar p = 0.3750.

Read the drift both ways: the checkout **lost 5 references the diff-in-prompt panel had
found**, alongside the 11 it gained. Whatever the repository adds, it also changes what
the judges attend to — repo access is not a superset of diff reading.

## How much of the lift is volume?

Findings rose 78 → 126 (+62%) while precision held roughly flat (16.7% → 15.1%), and the
negative arm's matches rose in step (1 → 4 on 29 → 65 findings). Findings per semantic
match: clean 6.0, checkout 6.6, broad 7.3 — so the checkout converts extra findings at
nearly the clean arm's rate, unlike the broad prompt whose 10.6% → 26.0% was volume at
declining precision. On every axis the checkout sits between clean and broad. The
concentration is informative: the whole gain lives in defect-y and AI-authored references;
maintainability and human-authored cuts did not move.

## What repo access looked like per instance

gemini-cli@c6e6248 found 16 located findings on a 3.4KB diff (clean arm: far fewer to
work with in-prompt); cherry-studio@5644b00 wrote 20 against 23 references;
ts-go@b970689 wrote 19 on a 79KB diff. Judges explore the tree (the two largest diffs
initially timed nemotron out at 900s doing exactly that — see below).

## Roster degradation and retries (all cleared)

The run needed three retry passes to reach full rosters; every retry re-ran the whole
instance (all three judges), and the final state is 0 degraded slots on both sides:

- nemotron 900s harness timeouts on the two largest diffs (es@a6a4623 22KB,
  ts-go@b970689 79KB) — cleared on retry 1, so they do not stand.
- provider-unavailable slots (ollama@b6002f6, es@e38d20c, ClickHouse@5fb6ee3 — retry 1;
  FreeCAD@82fef4a, lvgl@a0067e3 — retry 2, after a codex quota reset), and
- neg ollama@c2d08dd, which failed a different judge on each of two attempts
  (big-pickle harness, then nemotron unavailable) and cleared on the third.

Retries change nothing for the paired test — the reference sets never moved — but the
checkout condition is harder on the plumbing: judges exploring a checkout burn more
wall-clock and more provider quota than judges reading a prompt.

Abstentions: pos 3/54 reviews, neg 1/27. Path resolution (pos): exact=52, basename=14,
ambiguous=1, relocated=1.
