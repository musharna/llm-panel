Per-judge cut, declared 2026-08-30 before any evaluator pass (descriptive; not a confirmatory test).
Sample: the 13 codex-both PRs (81 human refs, 254 total). For each run (codex-transport original,
or-gpt replication) x arm (broad, volume) x judge, the panel is re-extracted with ONLY that judge's
review and scored by the upstream evaluator. Question: is the panel-level swing (codex 10,4 ->
or-gpt 5,10 on human refs) located in the gpt slot (codex -> or-gpt) or spread across the slots?
Noise floor: big-pickle and nemotron were re-run on the same transport, so their run-to-run change
is what a same-judge re-run looks like. Read: gpt-slot |delta| >> other slots' |delta| => transport.
