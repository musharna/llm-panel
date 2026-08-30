# Pre-registration: transport-controlled replication of the human-authored broad-vs-volume test

Written 2026-08-30 before any panel of this run was launched. Companion to
`../results-human-2arm/PREREG.md`, whose sample, arms, test and retry policy this run inherits.

**Why.** The original run filled its `codex` slot with two transports: the codex CLI for the
first 14 PRs and `or-gpt` (same model, `openai/gpt-5.6-sol`, via OpenRouter/opencode) for the
remaining 21 after the ChatGPT weekly cap. The per-slot descriptive cut split in opposite
directions — codex-transport PRs broad 10 vs volume 4 (discordant 7/1, one-sided p = .035),
or-gpt PRs 8 vs 12 (2/6) — and that split is confounded with PR human-comment richness by
construction (the sample is ordered by comment count, so codex got the richest PRs). This run
removes the transport variable so the confound can be resolved.

**Design.** Same 35 PRs, same two arms, same extractor (3), same evaluator
(`anthropic/claude-opus-4.5`), same bridge (md5 4f66beab…) and `llm-panel` (md5 86484d63…).
The 43 panels that already ran on `or-gpt` are reused verbatim (their run dirs, not re-asked).
The 27 panels that ran on codex (14 broad, 13 volume) are re-run with the slot filled by
`or-gpt`, roster `or-gpt,big-pickle,nemotron`, effort high, timeout 900 s, `--cwd-mode empty`.
Result: all 70 panels on one transport. Retry policy and stopping rule as in the original
PREREG; every re-panel is fresh (no cherry-picking against the codex panels it replaces).

**H1 (confirmatory, one-sided, same as the original).** On the 150 human-authored references,
recall under `broad` exceeds recall under `volume`. Exact McNemar on discordant pairs,
one-sided broad > volume; two-sided p, discordant counts and Wilson CIs reported.

**H2 (the discriminator, pre-declared).** Restricted to the 13 PRs whose *both* arms ran on
codex in the original run (81 human-authored references), compare the discordant split under
or-gpt with the original 7/1:
- broad still beats volume (one-sided McNemar p < .05 on those 81 refs) ⇒ the pilot's
  direction is a property of the PR set / prompt, not of the reviewer transport;
- the advantage vanishes (p ≥ .05, or reverses) ⇒ "same model ≠ same reviewer": the codex CLI
  and opencode harnesses produce different reviews from one model, and the original per-slot
  split was a transport effect.
The H2 restriction is a subgroup of H1's sample and is interpreted descriptively alongside H1;
it is not a second confirmatory test.

**Also reported, descriptively.** Pooled (446 refs) and AI-authored cuts; findings-per-arm
and precision; per-PR paired change between the codex panel and its or-gpt replacement.

**Not a new hypothesis on the PR set.** ClickHouse@d67628c's volume arm already ran on or-gpt
(its codex slot was the refusal that triggered the substitution); only its broad arm is
re-paneled, so 14 broad / 13 volume re-panels.

**Cost.** ~27 × $0.14 ≈ $3.80 on OpenRouter plus evaluator scoring.

**Run-time record, written after the run and before scoring (2026-08-30 16:40 EDT).** No
deviation from the fixed retry policy. Two panels stood degraded within it: lvgl@e526b2a
broad (nemotron `harness` on both allowed attempts) and SDL@1526727 volume (or-gpt stopped
on `tool-calls` before emitting text on all four attempts, the same signature as
SDL@96dfef3's burst on 08-29). Neither was re-asked beyond policy; the README reports H2 with
and without them. 42 attempts for 27 panels; $8.02.
