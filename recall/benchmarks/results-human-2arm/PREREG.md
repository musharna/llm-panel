# Pre-registration — broad vs volume on human-authored references (2026-08-28)

Written and committed BEFORE any panel in this directory ran.

**Origin.** On the seed-42 sample (18 PRs, 38 human-authored references) the `broad` prompt
matched 10 human-authored references and the `volume` prompt 5, with broad never losing a
human-authored match to any arm (broad vs volume 5/0, McNemar p = 0.06). Volume's gain over
`defect` was entirely on AI-authored references. That sample generated this hypothesis and
is NOT part of the confirmatory sample below.

**Hypothesis (one-sided, stated in advance).** On human-authored valid references, semantic
recall under `--prompt-style broad` exceeds that under `--prompt-style volume`.
Secondary, descriptive only: the same on AI-authored references (pilot suggested volume ≥ broad).

**Sample.** `../upstream/pos-human-n35.jsonl` (sha256 9bcdba53c68182c1…): the 35 positive AACR-Bench PRs
with ≥3 human-authored comments, excluding the 18 seed-42 instances, ordered by human-comment
count then seed-42 shuffle, each diff verified fetchable before selection (2 unfetchable
skipped: ClickHouse@cc96255, keycloak@21d4538). 150 human-authored references, 446 total.
Sized for 26% vs 13% at α = .05, 80% power (unpaired ceiling 144/arm).

**Arms.** Identical except `--prompt-style`: broad vs volume. Roster codex + big-pickle +
nemotron, effort high, timeout 900 s, `--cwd-mode empty`, extractor 3, upstream evaluator
with `anthropic/claude-opus-4.5`. Arms interleaved per PR so a cut-short run stays balanced.
Binaries md5-pinned in `BINARIES.txt`.

**Test.** Exact McNemar on discordant pairs over the human-authored references, one-sided
(broad > volume); report the two-sided p as well, the discordant counts, and Wilson CIs.
Also report the pooled and AI-authored cuts descriptively.

**Retry policy (fixed).** A provider refusal (`unavailable`) is re-run up to 3 times; a
harness timeout once; codex quota exhaustion is waited out, never counted. A slot still
degraded after that stands and is reported. No instance is dropped for its result.

**Stopping rule.** All 35 PRs × 2 arms, then score once. No interim looks at recall.

**Deviation, recorded 2026-08-29 before any further panel ran.** After 14 of 35 PRs (both
arms complete, 28 panels) the codex judge hit its ChatGPT *weekly* usage cap (06:29 EDT,
reset Sep 3 12:26 PM EDT). For the remaining 21 PRs (plus ClickHouse@d67628c's volume arm,
whose codex slot was the refusal) the codex slot is filled by `or-gpt` = the same model,
`openai/gpt-5.6-sol`, reached through OpenRouter under the opencode transport instead of the
codex CLI. Same prompt, effort, timeout, `--cwd-mode empty`; what differs is the harness
(opencode's tool loop and `--variant high` instead of codex's `model_reasoning_effort`), and
billing (per-token instead of subscription). Roster note: `~/.config/llm-panel/roster.json`
`judges.or-gpt`. The analysis treats codex and or-gpt as one slot; the README reports the
split (14 codex / 21 or-gpt PRs) and a per-slot descriptive cut so the substitution's effect
is visible rather than assumed nil. Hypothesis, sample, test and stopping rule unchanged.

**Run-time deviations, recorded before scoring (2026-08-29).**
1. *Bridge crash on the largest diff.* ollama@498792c's diff (839 KB) exceeded Linux's
   128 KB per-argument limit; the bridge passed the prompt as argv and raised E2BIG at exec,
   and the driver — which had no cap on "bridge produced nothing" — relaunched it 569 times
   before being stopped. Fixed by sending the prompt on stdin (commit ea38c1c) and capping
   no-result relaunches at 2; PRs 31–35 ran on the fixed bridge. No judge was ever reached
   during the loop, so no panel was consumed or discarded.
2. *Retry counters reset on the restart.* three.js@7388f60's volume arm had stood degraded
   (nemotron `unavailable` ×4); the restarted driver retried it once more and nemotron
   answered, so that panel is 3/3 rather than 2/3. One retry beyond the fixed policy.
3. *Whole-panel burst on the last instance.* SDL@96dfef3's volume arm lost all three judges in
   the same minute (or-gpt and nemotron "stopped on tool-calls before text", big-pickle 429)
   on four attempts. Because the failure was a shared burst rather than three independent
   refusals — the same PR's broad arm had three full reviews 30 min earlier and the diff is
   14 KB — one further attempt was made before any score was computed: or-gpt and nemotron
   answered, big-pickle 429'd again. The panel stands at 2/3. One retry beyond the policy.
Final slot count: broad 105/105, volume 104/105.
