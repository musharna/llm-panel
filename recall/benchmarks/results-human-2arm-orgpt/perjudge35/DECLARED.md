# Full-sample per-judge variance floor — declared 2026-08-31 before any evaluator pass

Descriptive analysis; not a confirmatory test. Written before extraction or scoring ran.

## Question

How large is a same-judge, same-transport, same-PR run-to-run swing on the full n=35 human-refs
sample? That number is the noise floor against which the gpt slot's transport-swap delta — and any
future subgroup claim at this sample size — must be read.

## Sample and cells

All 35 PRs in `pos-human-n35.jsonl` (150 human-authored references per arm). For each
run (codex-transport original `results-human-2arm`, or-gpt replication `results-human-2arm-orgpt`)
x arm (broad, volume) x judge, the finished panels are re-extracted with ONLY that judge's review
(`aacr-upstream reextract --judges <name>`) and scored by the upstream evaluator
(JUDGE_MODEL=anthropic/claude-opus-4.5). 12 cells:

- codex run judges: codex, big-pickle, nemotron
- orgpt run judges: or-gpt, big-pickle, nemotron

## Declared quantities

1. **Same-transport deltas (the floor):** for big-pickle and nemotron, run2 − run1 human-ref
   matches per arm — 4 deltas from judges whose model AND transport were identical across runs.
   Also reported on all references.
2. **Transport-swap delta:** the gpt slot (codex → or-gpt) per arm, read AGAINST the floor, not
   against zero.
3. **Per-PR discordance:** for each same-transport judge x arm pair, the count of PRs whose
   per-PR human-ref match count changed between runs, and the SD of the per-PR difference —
   feeds a paired detectable-effect estimate at n=35.
4. **Evaluator-noise decomposition:** ONE cell (codex-broad-nemotron) is scored TWICE on the
   byte-identical extraction. Its two scores differ only by evaluator stochasticity; the
   same-transport delta in (1) additionally contains panel stochasticity. Reported as
   evaluator-only |delta| vs same-transport |delta|.

## Declared reads (before numbers)

- The floor is the MAX |same-transport delta| across the 4 pairs (conservative), with the spread
  reported. A transport or prompt effect at n=35 is claimable only if it exceeds the floor.
- If evaluator-only |delta| is comparable to the same-transport |delta|, run-to-run panel variance
  cannot be separated from scoring variance at this n, and both must be quoted together.
- Positive control: restricting these full-35 extractions to the 13 codex-both PRs must
  approximately reproduce the 2026-08-30 perjudge cut (fresh evaluator pass, so approximate:
  same signs, magnitudes within ~2).

## What this is not

No hypothesis test is registered; nothing here confirms or refutes a transport effect. It sizes
the ruler.
