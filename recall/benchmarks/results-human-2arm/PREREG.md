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
