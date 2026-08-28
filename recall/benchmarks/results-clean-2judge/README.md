# Clean run, two judges — the roster-matched control

Not a new panel run. The clean arm's recorded run dirs (`../results-clean-3judge`,
`BINARIES.txt` copied) re-extracted with `aacr-upstream reextract --judges codex,big-pickle`
under extractor 3, then scored with the same upstream judge (`judge failures during
scoring: 0`, both sides). Nemotron's reviews are recorded as `excluded`, not degraded.

Why it exists: under the `volume` prompt (`../results-volume-3judge`) nemotron returned no
text within 900 s on every instance, so that arm is effectively codex + big-pickle. This is
the same two judges on the same 18 + 9 instances with the house `defect` prompt.

|          | refs | findings | line matches | semantic matches | semantic recall | precision |
| -------- | ---: | -------: | -----------: | ---------------: | --------------: | --------: |
| positive |  123 |       45 |           14 |                8 |        **6.5%** |     17.8% |
| negative |   36 |       33 |            6 |                4 |           11.1% |     12.1% |

Nemotron contributed 46 of the clean arm's 91 positive findings and 7 of its 15 matches.
Scores: `../scores/clean2j-{pos,neg}.json`.
