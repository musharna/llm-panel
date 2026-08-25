# Clean 3-judge run — the headline result

Panels: codex + big-pickle + nemotron, effort high, timeout 900s, seed-42 sample drawn by
AACR-Bench's own converter. Binaries md5-pinned in `BINARIES.txt` (source tree clean at
`17c7958`), so what produced these numbers is identifiable — `git rev-parse HEAD` is not.

Scored by the **upstream** evaluator (`alibaba/aacr-bench`) with a real LLM judge
(`anthropic/claude-opus-4.5`, outside the panel's own model families). `judge failures
during scoring: 0` on every arm — asserted by `aacr-score`, not assumed.

|                    | positive (valid refs) | negative (REJECTED refs) |
|--------------------|----------------------:|-------------------------:|
| instances          | 18/20                 | 9/10                     |
| judge slots        | **54/54**, 0 degraded | 26/27, 1 degraded        |
| references         | 123                   | 36                       |
| findings           | 79                    | 30                       |
| line matches       | 26 (21.1%)            | 4 (11.1%)                |
| **semantic**       | **13 (10.6%)**        | 1 (2.8%)                 |
| precision          | 16.5%                 | 3.3%                     |

## Roster and timeout are worth ~2x

Against the degraded 2-judge pilot (`../results-pilot-2judge`, 300s, 39/54 slots), scored
with the SAME extractor so only roster and timeout differ:

| | pilot | clean |
|---|---|---|
| semantic recall | 5.7% | **10.6%** |
| line recall | 13.0% | 21.1% |
| precision | 11.9% | 16.5% |

Two positive instances returned zero findings in the pilot purely by hitting the 300s cap,
and they carry 20 of the 123 references. At 900s they yield 8 and 4 located findings.

## Location agreement overstates semantic agreement ~2x

21.1% of references had a finding at the right file and line; 10.6% had one that a judge
called the same concern. Half of the location hits are the panel talking about the same
line for a different reason. A location-based matcher cannot detect that about itself,
which is why scoring is delegated upstream.

## Do NOT quote the valid-vs-rejected ratio

10.6% vs 2.8% is 3.80x and reads like discrimination. **Fisher exact p = 0.194.** The
pilot's version (5.7% vs 0.0%) gives p = 0.352. Neither is significant.

At the clean effect size ~138 references per arm would give 80% power, and the benchmark
holds 639 negative references, so this IS answerable with a larger negative sample —
roughly 35 negative PRs rather than the 10 sampled here. An earlier estimate of ~919/arm
came from the degraded pilot and should be ignored. Both estimates rest on very few events
(the negative arm has ONE) and are themselves unstable.

## Known limits of these numbers

* Unlocated findings are withheld from upstream and counted in each result's `unlocated`
  field. They are NOT non-matches there: an empty path is falsy, so upstream's path filter
  is skipped, and a None line skips its line filter — a location-less comment matches every
  reference. Handing them over inflated line matches from 20 to 50 on the first pilot
  scoring.
* Precision partly measures verbosity. One instance's judges wrote a reasoning transcript
  ("Let me look at...", "But actually, I need to..."); such prose mentions real filenames,
  resolves by basename, and survives as findings.
* Sentinel compliance varies ~10x by judge (big-pickle 52.6%, codex 26.3%, nemotron 5.3%),
  so abstention is a property of the judge, not the panel.
