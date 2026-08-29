# Volume arm — the defect prompt told not to stop

The control the broad and checkout arms both lacked. Every recall gain measured so far
arrived with more findings, and recall against a fixed reference set is findings ×
precision, so none of them could say whether the intervention's *content* mattered or only
its verbosity. This arm keeps the house `defect` prompt word for word — same scope, same
"do not propose refactors" — and adds one paragraph: be exhaustive, go through every hunk,
do not stop at the most severe, ten or more items is usual (`--prompt-style volume`,
`aacr-upstream`). Same 18 + 9 instances (seed 42), same roster (codex + big-pickle +
nemotron), effort high, timeout 900 s, empty cwd with the diff in the prompt, same upstream
judge (`anthropic/claude-opus-4.5`, `judge failures during scoring: 0` both sides),
extractor 3. Binaries md5-pinned in `BINARIES.txt` (source HEAD `2b81b32`, tree clean).

## Result

|                    | refs | findings | line recall | **semantic recall** | precision |
| ------------------ | ---: | -------: | ----------: | ------------------: | --------: |
| defect (clean)     |  123 |       91 |       22.8% |           **12.2%** |     16.5% |
| **volume**         |  123 |  **392** |       49.6% |           **25.2%** |  **7.9%** |
| broad              |  123 |      243 |       48.8% |               26.0% |     13.2% |
| checkout           |  123 |      157 |       31.7% |               15.4% |     12.1% |
| negative (rejected)|   36 |      220 |       47.2% |               19.4% |      3.2% |

Paired on the same 123 references (`../../aacr-mcnemar`):

| comparison          | a only | b only | McNemar p | note                                     |
| ------------------- | -----: | -----: | --------: | ---------------------------------------- |
| clean → volume      |      3 |     19 |    0.0009 | 15 → 31; the lift is real                |
| clean2j → volume    |      2 |     25 |   <0.0001 | roster-matched (codex+big-pickle) control |
| broad vs volume     |     13 |     12 |       1.0 | 32 vs 31 — same recall, **19 shared**    |
| checkout → volume   |      8 |     20 |     0.036 |                                          |

## What it says

1. **Verbosity alone reproduces the broad prompt's pooled recall.** 25.2% vs 26.0%, p = 1.0.
   The broad arm's headline gain over `defect` (12.2 → 26.0%) is therefore not evidence
   that *what* it asks for matters; a defect-only prompt told to keep going gets there too.
2. **It pays for it in output.** 392 findings to broad's 243 — 1.6× the reading for the
   same recall — and precision halves (16.5 → 7.9%; broad 13.2%). Matches per finding:
   defect 0.165, broad 0.132, volume 0.079. Returns diminish; precision is not constant in
   findings, so recall is *not* simply linear in volume. Broad's content buys efficiency.
3. **Same recall, different references.** Only 19 of broad's 32 and volume's 31 matches
   coincide. The split lines up with authorship: on the 38 human-authored references broad
   matches 10 and volume 5 (5 broad-only, 0 volume-only, p = 0.06); on the 85 AI-authored
   ones volume matches 26 to broad's 22. A defect-only prompt pushed for volume finds more
   of what other models flagged; the maintainer-style prompt finds more of what humans did.
   n is small for the human cut; treat it as a hypothesis for a larger sample.
4. **No discrimination, again.** Valid 25.2% vs rejected 19.4%, ratio 1.30, Fisher p = 0.66.
   On rejected PRs the arm emits 220 findings and matches 7 of them.

## The human-authored cut, across every arm

| arm | human-authored (n=38) | AI-authored (n=85) |
| --- | --------------------: | -----------------: |
| defect (clean) | 5 (13.2%) | 10 (11.8%) |
| checkout | 4 (10.5%) | 15 (17.6%) |
| broad | **10 (26.3%)** | 22 (25.9%) |
| volume | 5 (13.2%) | **26 (30.6%)** |

Human-only paired tests: broad vs clean 5/0 (p = 0.06), vs checkout 6/0 (p = 0.03), vs
clean2j 8/0 (p = 0.008), vs volume 5/0 (p = 0.06) — broad never loses a human-authored
match to any arm. Volume vs clean on human references is 2/2, p = 1.0: the exhaustiveness
instruction's gain is entirely on AI-authored references. A powered test of "broad > volume
on human-authored references" (26% vs 13%) needs ~144 human references per arm; the
benchmark holds 391 across 178 PRs (48 PRs carry ≥3), so ~48 PRs chosen for human
references, two arms. Not run.

## Roster and retries

53/54 positive slots, 27/27 negative, after four passes. Under this prompt nemotron
returned no text within 900 s on 10 of the first 18 positives and was refused by the
provider on 2 more (its trivial-question probe took 151 s with the endpoint alive); a
6-instance negative batch that afternoon answered 3/3 every time, so the morning failures
were partly provider load, not only the prompt. Codex quota ran out twice (13:08 and
16:55 EDT; 5-h windows), which set the pass boundaries. The one standing degradation is
`linera-io__linera-protocol@024925d`: nemotron refused on attempts 1, 2 and 4 and codex's
quota fell on attempt 3. Expected skips as in every arm: uv@ed57db2, ComfyUI@cfc3122
(pos), keycloak@1463502 (neg) — head commits GC'd upstream.

Per-judge located findings before merge (clean → volume): codex 30 → 115, big-pickle
15 → 95, nemotron 49 → 221. All three judges scaled. Scores: `../scores/volume-{pos,neg}.json`.
