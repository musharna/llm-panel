# Contributing

Issues and PRs welcome. Three things about this codebase are deliberate and worth
knowing before you patch it:

**The tools are single files on purpose.** `llm-panel`, `panel-report`, and
`panel-triage` are each one executable, stdlib-only Python file. Don't add
dependencies, split them into modules, or introduce a build step — auditability of one
readable file is a feature. The `src/llm_panel/` package is only a thin exec wrapper so
pip installs work; the root files stay canonical.

**Every fix ships with a control.** The `*-controls` suites are regression tests where
each control corresponds to a defect that actually shipped. If you fix a bug, add a
control that fails on the pre-fix code and says so in a comment — an assertion that
passes on both the broken and fixed versions tells you nothing. Run the seven suites
before pushing:

```sh
python llm-panel-controls && python panel-report-controls && \
python panel-triage-controls && python claimlib-controls && \
python recall/aacr-upstream-controls && python recall/aacr-recut-controls && \
python privacy-controls
```

CI runs exactly these on 3.11, 3.12 and 3.13.

**Failure classes are semantics, not logging.** `refused` (the provider said no) and
`harness` (our plumbing broke) license opposite conclusions, and ambiguity must default
to `harness`. Any change touching judge execution has to preserve that asymmetry.

For benchmark data questions (adding instances, upstream licensing, removal requests),
see `recall/benchmarks/PROVENANCE.md`.
