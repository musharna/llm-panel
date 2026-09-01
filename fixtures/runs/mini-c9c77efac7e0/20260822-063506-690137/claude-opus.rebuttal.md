I'll read the full material before taking positions.I read the full file (all 1550 lines) before positioning. Traces below are against the shipped source, not the excerpt.

---

## Positions on findings that touch mine

**UPHOLD: A2** — same defect as my #2. `claims_sec`'s else-branch (line 1277) keys on `if claims:` alone; `_rebutted` — the file-based test — is computed at line 1402, 120 lines later, and never consulted here. A2 is right that the earlier `had_round` fix repaired the *bench* cell and left this literal untouched: `had_round = bool(run["meta"].get("rebut")) or any(...)` at 1135 reads the corrected key, and the section headline reads no key at all.

**UPHOLD: C5** — same as my #2, and C5's trace is exact: with `rebut:true` and unparseable prose, `cited` is `{}` so `any(n for _, n in cited.values())` is False over an empty dict, but `bool(meta.get("rebut"))` carries `had_round` to True. Bench prints "no positions", section prints "no rebuttal round", masthead prints "· rebuttal".

**UPHOLD: D6** — same as my #2.

**UPHOLD: A12** — same as my #3. Confirmed against both consumers: `ok = [j for j in js if j["status"] == "ok"]` (1114) feeds `{len(ok)} of {len(js)} answered` (1382), and the roster span at 1364 applies `.out` to any non-`ok` status, which `.groster span.r.out{text-decoration:line-through}` (930) strikes through. The `dead`/`part`/`unlisted` split at 1369–1374 fixed only the caveat wording.

**UPHOLD: C6** — same as my #3, and C6's extension to `incomplete` is real: with one judge at `status="incomplete"` and a non-empty review, the cell renders `0 of 1 answered` immediately above `1 answered but was cut off`. Two lines of the same cell disagree about whether the judge answered.

**UPHOLD: D8** — same as my #3 plus the `incomplete` extension; same trace as C6.

**UPHOLD: A9** — same as my #4. `(blocks if len(cs) > 1 or tag == "\u2014" else quiet)` at 1258 forces the bucket into `blocks`, and `len(blocks)` is reported at 1264 as "N findings drew more than one position". A9's degenerate case is correct: bucket-only → "1 finding drew more than one position" with the block below headed "ungrouped — described, not referenced".

**UPHOLD: D7** — same as my #4, and D7's second number checks out: one untagged position gives `n_findings = sum(1 for t, _ in ordered if t != "\u2014")` = 0 while `n_pos = len(claims)` = 1, so the glance prints "**1** positions on **0** findings" beside a headline claiming one finding.

**UPHOLD: C10** — same as my #5. `FINDING_NUM` is `^#{0,4}\s*(\d{1,2})[.)]\s+(.+?)\s*$`, the fence mask at 783 removes only fenced lines, and `seen` at 787 makes the first unfenced `1.` final. A plain reproduction list before the real `## 1. **…**` heading takes the number.

**UPHOLD: D9** — same as my #5.

**UPHOLD: C13** — same as my #1. Traced the exact input: on `- **REJECT A1:** **critical** is not enforced.`, MARKUP consumes `- **` (the `*` is a member of `[-*+]`, so the bold markers are eaten as bullets) ending at offset 4; LABEL takes `REJECT` + qual ` A1` + `:` + space; `text = "** **critical** is not enforced."`. `line.lstrip()` starts with `-`, so the position branch is skipped, `count("**") == 3` is odd, `rfind` deletes critical's closer, and `_inline` emits `<strong> </strong>critical is not enforced.` Removing the bullet from the same line makes the first branch fire and renders correctly — the bullet is the whole difference.

**UPHOLD: D10** — same as my #1, same input, same trace.

**UPHOLD: A6** — same as my #6. `card()` at 1219 calls `decode_letters(_inline(c["text"]), …)` with no `md()` and no `\n → <br>`, while `scan_positions`'s absorber (189–195) gates only the *break* tests on `if not fenced[k]` and appends `nxt.strip()` unconditionally. A6 is right that the same rebuttal renders correctly in `#r2`, which goes through `md(j["rebuttal"])` at 1331 — the by-finding view is the degraded copy of text the page already renders properly elsewhere.

**UPHOLD: A8** — same as my #7, both halves. `phase_bits = [p for p in ("rebuttal","synthesis") if phases.get(p)]` then `floor = _rebutted and not phase_bits`: a run with only `synthesis` recorded suppresses the caveat and prints "over round 1 + synthesis" as an affirmative coverage claim; a falsy per-phase value makes `phase_bits` empty and asserts "this run predates per-phase accounting" about a run that does not.

---

## Concessions

**CONCEDE: C8** — my clearance of `_fence_mask`'s open/close rule was wrong in scope, and C8 holds the case it missed. I traced only the two comparisons the code's own comment discusses (`m.group(1)[0] == fence[0]` and `len(m.group(1)) >= fence[1]`). What I did not check is that the closer branch never requires the *rest of the line* to be empty. `md()` does: its closer is `^\s*\`{%d,}\s*$` (266). So for

````
```text
```python
REJECT A1: sample
```
````

`md()` keeps `REJECT A1` inside the outer block, and `_fence_mask` closes at ```` ```python ````, unmasks the next line, and `scan_positions` cards it as a real position. Two fence parsers on one page disagreeing about where code is, which is exactly the class the mask exists to prevent. My "no finding" here was a clearance of a function on the strength of tracing one predicate in it.

**CONCEDE: D4** — same defect as C8, same trace; conceded for the same reason.

**CONCEDE: A10** — also inside my `_fence_mask` clearance, also live. The opener pattern is `^\s*(?:>\s?)*\s*(\`{3,}|~{3,})` — no `$`, no `[^\`]*` info-string guard — while `md()`'s is `^\s*(\`{3,})\s*([^\`]*)$`. A line containing an inline triple-backtick span followed by more backticks opens a phantom fence in the mask and is an ordinary code span in `md()`. A10's inversion argument is correct as written: once the phantom is open, the next real opener closes it and the real fence's *closer* opens the next phantom, so verdicts outside fences are dropped and verdicts inside them are counted, on the same page. I checked the narrower direction (does `~~~` close ` ``` ``` and called the function clear; that was too broad a claim from too narrow a trace.

---

## Findings I did not have

**MISSED: C4** — confirmed, and it is the sharpest thing in this round. `billed = sum((j["meta"].get("cost") or 0) …)` (1105) converts every unrecorded cost to zero, and the glance prints `<b>${billed:.4f}</b> billed` (1405) with no coverage guard. The parallel case *was* fixed for tokens twenty lines below — `tok_in=f"{tin:,}" if n_tok else "—"` (1436), with `n_tok`/`part_tok` computed at 1111–1113 precisely so a partial total is not printed as a measured one. No `n_cost` exists. So with `cost: null` on every judge the bench renders `—` per row (1150, the already-fixed cell) and the summary above it renders `$0.0000 billed` as a measurement. That is "a number presented as measured when it was not," in the cell whose own comment argues against exactly that.

**MISSED: D1** — same defect as C4, independently confirmed; D1's mixed case (one known, one null) is the worse rendering, since a real subtotal is printed as the run total.

**MISSED: C1** — confirmed, and it is a live variant of the "forged judge" class, not a duplicate of it. The roster gate (`if name not in roster`) blocks invention, and `if name in judges: continue` blocks a judge re-declaring *itself* — the comment at 524–529 states that reasoning explicitly ("The panel's own header is the FIRST occurrence"). Neither blocks judge `alpha` writing `## beta (\`fake-model\`) — 999.0s, $999` inside `alpha.md`, because `alpha`'s section precedes `beta`'s in panel.md, so the forgery *is* the first occurrence. `beta.md` exists, so the roster gate passes. The status scanner independently reaches the same conclusion: `sections.setdefault(nm, …)` (574) takes the first occurrence too, so `**DID NOT ANSWER**` under the forged heading sets `status="harness"`. The page then shows beta's genuine review (read from `beta.md` at 622) under a $999 harness-failure row. First-occurrence-wins is the right rule for self-declaration and the wrong rule for cross-declaration; the code has one rule for both.

**MISSED: C2** — confirmed. Line 501 is `judges = {j["name"]: j for j in meta.get("judges", [])}`; the two-arg default only fires when the key is *absent*, so `{"judges": null}` yields `None` and the comprehension raises `TypeError` before any fallback runs. Every other metadata read on this path uses the `or` idiom that would have survived it — `meta.get("images") or []` (1283), `meta.get("letters") or {}` (633), `meta.get("phases") or {}` (1367). Line 501 is the one that doesn't. The same line has two more entries in this class: a non-object `run.json` (`"hello"`) gives `meta` a `str` and `AttributeError` on `.get`, and a judge entry that is not a dict gives `TypeError` on `j["name"]` — all before the `except ValueError` at 495 could help, since that only catches parse failures.

**MISSED: C3** — confirmed by tracing the backtracking, not by taking the timing on faith. The 2024 fix bounded the *label* (`[^\]\n]{1,300}`) and left the URL as `(https?://[^)\s]+)`. On `"[x](https://a" * 8000` there is no `)` and no whitespace anywhere, so at each `[` the engine matches `\[x\]\(`, lets `[^)\s]+` run to end-of-string, then backtracks it one character at a time testing `\)` — O(n) per start position, O(n) start positions. The bounded label cannot help because the blow-up is entirely inside the URL group. C3's stated 6.1s is a measurement I can't check, but the shape is right and the growth is quadratic.

**MISSED: A1** — confirmed. `MARKUP` includes `\|`, so a table row is stripped to its first cell: on `| A1 | UPHOLD | …` the alternation consumes `| ` in one iteration, stops at `A`, and `LABEL.match(line, 2)` is asked to find a verdict word at `A1` and fails. Verdict-first rows fail differently — `| UPHOLD | A1 | Not reachable |` has no `:` or em/en-dash anywhere, so the optional qualifier `[^:—–\n]{0,24}` can never reach a separator. A1's partial-match variant is the one worth the severity: `| UPHOLD | A1 | Confirmed: the race is real |` *does* match, with the qualifier group swallowing `| A1 | Confirmed`, so the verdict pill at 1215–1216 renders the literal string `UPHOLD | A1 | Confirmed` and the card body starts mid-sentence. A1's framing is right too — the structural MARKUP strip removed the closed set at the front and the separator requirement is a closed set at the back.

**MISSED: A3** — confirmed, and this one fires on ordinary prose. `TAG_RE`'s third alternative is a bare `(?P<al>[A-Z])(?P<an>\d+[a-z]?)`, and `tag_of` (745) never checks the letter against `run["letters"]`, which `claims_of` holds at 812. On `- **REJECT: this is a P0 concern, not a defect.**` the lookbehind is satisfied (preceding char is a space) and `\b` after `0` holds, so the position is filed under finding "P0". Three consequences, all checkable: `raiser = run["letters"].get("P","")` is empty and `titles.get("P0")` is empty, so a block renders with a bare tag and no title; `len(cs) == 1` sends it to `quiet` as a phantom finding; and it is stolen from the `"\u2014"` group, so `ungrouped` (1352) *under*counts while `n_findings` (1353) over-counts. `L42`, `H2`, `N2`, `Q4` behave identically.

**MISSED: C9** — same defect as A3, confirmed on C9's own input. C9 adds the consequence I'd have wanted: `cited` (1122–1127) increments `t[0]` on any truthy tag, so a judge whose only "citation" is the phrase "C3 linearization" renders `1/1` in the coverage column — the column that exists specifically to expose grouping failure reports full coverage of a finding that does not exist.

**MISSED: A4** — confirmed. `md()`'s fence branch (259) matches backticks only, while `_fence_mask` (154) and the list-continuation absorber (343) both accept `~{3,}`. A top-level `~~~python` block therefore reaches `para` and goes through `_inline`, where `~~([^~]+)~~` cannot start at index 0 (index 2 is a tilde, so `[^~]+` fails) but *does* start at index 1, greedily running to the closing run and emitting `~<del>python<br>def f(x):<br>…</del>~`. A4's blank-line variant is worse for the reason stated: `flush()` splits the block and each fragment is re-parsed, so an interior `#`, `-`, `|` or `>` becomes a heading, list, table or blockquote.

**MISSED: A5** — real, and it is a mechanism my #1 does not cover, so it is not a duplicate. On `**REJECT: A1 is wrong.** The \`foo\` path **never** runs.` with no list markup at all: `line.lstrip()` does start with `**` but `text = "A1 is wrong.** The \`foo\` path **never** runs."` does not, so the `and` fails and the parity branch runs. Count is 3, `rfind` removes never's closer, and `_inline` pairs the label's orphaned closer with never's opener: `A1 is wrong.<strong> The <code>foo</code> path </strong>never runs.` My #1 blamed the selector for not being markup-aware, which is true and is what Input B needs; A5 shows the position test is *also* blind whenever the label's bold closes mid-line, because the orphan then sits after the claim text rather than at its front, where `text.lstrip().startswith("**")` can see it. Both are live; A5's needs no bullet.

**MISSED: A7** — confirmed, and I traced the whole path because it inverts the function's stated purpose. On `## 1. **Critical:** \`parse()\` dereferences a null pointer`, `FINDING_NUM` matches, `raw` is the remainder, and `b = re.match(r"\*\*(.+?)\*\*", raw)` is non-greedy so it takes `**Critical:**` and `t = "Critical:"`. The `if not b:` sentence-cut is skipped precisely *because* the bold matched, `t.rstrip(" .;:")` gives `"Critical"`, `len(t) > 4` passes, and `out["A1"] = "Critical"`. Every A1 block is then headed by a severity word, and the glance's contested cell (1361) repeats it. A7's second half also holds: with no bold, the cut only fires when `cut.start() > 24`, so `1. Race in pool. The read at line 42 …` — first sentence end at offset 13 — takes no cut and runs to the 110-character truncation. My #5 found a different way to get the wrong string into the same slot; A7 found the way that produces a *plausible-looking* wrong string, which is harder for a reader to notice.

**MISSED: A11** — confirmed, and the code carries its own evidence. The judge parser at 519 requires `—\s+([\d.]+)s`; the status scanner's `hdr` at 566 deliberately does not (`[^\n]*$`). That loosening only makes sense if headings without a timing field occur — which is exactly A11's input. Such a judge never enters `judges`, the status loop iterates `judges.items()` and so never reaches its section, and `gap` filling at 602 (which runs *after* the status scan) stamps it `unlisted`. The page then prints "1 recovered from disk, absent from run.json" and a red `gapnote` saying "absent from run.json" for a run where `source` is "panel.md (this run predates run.json)" — there is no run.json to be absent from. A11's second branch traces correctly too (no `<name>.md` ⇒ not in `roster` ⇒ filtered at both 520 and 568 ⇒ the judge cannot exist), though whether llm-panel writes a review file for a non-answering judge is something neither of us can check from here.

**MISSED: C7** — confirmed. `_fence_mask` has no indented-code branch, and on `    REJECT A1: emitted by the test fixture` the MARKUP repetition matches zero times (after `\s*` eats the indent, `R` is not `[-*+]`/`\d`/`|`), then the trailing `\s*` consumes all four spaces anyway, so `label_at` matches at offset 4 and a card is invented. Worth stating alongside: `md()` has no indented-code branch either, so the same line renders as prose — both halves are wrong, and the tally-inflation half is the defect.

**MISSED: D3** — same defect as C7, independently confirmed on the same shape.

**MISSED: D2** — confirmed. `syn = re.search(r"^## Synthesis \(by \`([^\`]+)\`\)…", pm, re.M|re.S)` at 650 is unscoped and `re.search` is leftmost-wins, so a judge's review quoting that heading inside panel.md becomes *the* synthesis, attributed to whatever name it names, and the genuine trailing synthesis is suppressed. This is not covered by the roster gate, which guards judge headings only — a synthesis needs no file on disk to exist. D2's truncation half also holds: the lookahead `(?=\n## |\Z)` stops at any H2, so a synthesis with its own `## Risks` section silently loses everything after it. (`### Risks` is safe — `\n## ` requires a space in the fourth position.)

**MISSED: D5** — confirmed. On `- [x] **UPHOLD A1:** confirmed by the reproduction.` the MARKUP repetition takes `- ` and then halts at `[`, which is in none of its alternatives, so `LABEL.match(line, 2)` is offered `[x] **UPHOLD…` and fails. The position vanishes from cards, `cited`, the filters and every derived total — the same silent-zero outcome the MARKUP comment says the structural strip was written to end.

**MISSED: C12** — confirmed. `head.startswith("**PARTIAL")` / `head.startswith("**INCOMPLETE")` (585) tests a prefix of the section, not a marker, and the section is the judge's verbatim review. A round-one review whose first finding is titled `**INCOMPLETE handling of null costs …**` — or, more likely, `**PARTIALLY correct: …**`, which also matches `**PARTIAL` — is stamped `status="incomplete"`. The judge then leaves `ok`, gets a concede-coloured pill and is counted in "answered but was cut off". The comment two lines above says "only position tells" — position is precisely what this input satisfies, so positional matching is not the guard it is described as. Correctly scoped by C12: only fires on runs where `meta.get("judges")` is empty.

**MISSED: A13** (unterminated fence swallows the tail) — confirmed. In `scan_positions` all three break tests sit inside `if not fenced[k]:` (192), so once an unclosed fence opens after a position, `fenced[k]` is True for every remaining line and nothing can break the absorber. The rest of the document is `.strip()`-joined into one `text`, and later verdicts inside the mask are skipped, so one card holds the tail. A judge with `status="incomplete"` — cut off mid-block — is the routine producer of an unclosed fence, which makes this reachable on exactly the runs that already render worst.

**MISSED: A14** (escaped pipes in tables) — confirmed. `cells()` (280–306) tracks backtick runs and nothing else; a `\` is appended to `buf` as an ordinary character and the following `|` splits with `run == 0`. `| the operator \`a\` | matches a \| b | ok |` yields four cells against three `<th>`, shifting every cell to its right. Low severity, but `\|` is the standard table escape and judges do write it.

**MISSED: C11** — real, though I'd put it well below the rest. `tag_of` returns the leftmost `TAG_RE` match, so `UPHOLD A1 and B2: …` files one card under A1 and B2 gets no block at all unless another judge cited it. The card count is right — one position, one card — but `n_findings` (1353) then reports one finding where a judge took a position on two, and a reader filtering to B2 sees nothing. Confirming it as a derived-count gap, not as a rendering bug.

---

## Rejections

**REJECT: C14** — the sanitisation half is right and the collision claim is not established. `re.sub(r"[^a-z0-9]+", "-", …)` collapses each run of non-alphanumerics to one `-`, so `a.___b` and `a__---b` do both reduce to `a-b`; that is the collision `judge_slug`'s docstring says the digest exists to break. The finding then asserts that `sha256("a.___b")[:4]` and `sha256("a__---b")[:4]` are *both* `1da7`. Nothing in the finding derives that, and it is not derivable by inspection — it is a stated 16-bit coincidence for two hand-picked strings, prior probability 1/65536. I have no shell in this session and cannot compute either digest, so I am not endorsing it; I am rejecting it as unbacked. What I will correct in my own clearance: I wrote "distinct digests, distinct classes," which overstates. A 4-hex prefix has 65536 buckets, so collisions are *possible*, just vanishingly unlikely at panel sizes (five judges sharing a sanitised base: ~10⁻⁴). The right claim is "bounded, not impossible" — but a finding needs the specific pair, and this one asserts it rather than showing it.

**REJECT: D11** — identical claim to C14, including the identical `1da7` for both names, and rejected on the same ground. That C and D independently produced the *same* fabricated-looking hex prefix is not corroboration: neither can compute SHA-256 any more than I can, so two matching unbacked digests are one unbacked digest reported twice.

**REJECT: A15** (`JUDGE_HUES` is dead) — I found the same thing and deliberately did not file it, for the reason the brief gives: no input produces wrong behaviour. `judge_hues()` computes `360/len(names)` spacing and never reads the tuple, so the constant is unreferenced and its docstring's "10-hue palette" describes nothing. That is dead code, and the brief asks for defects with a concrete input→wrong-output, not for cleanups.

---

## Unchallenged

My #8 — `hot` is built from `contested[:5]` (1362) while the same cell prints `<b>{len(contested)}</b> drew both an uphold and a reject` (1386). With nine contested findings the count and the enumeration answer the same question with different numbers and nothing marks the truncation. No reviewer touched it; it stands as filed, at low severity.The hook matched the phrase "does not exist" in my C9 position — "reports full coverage of a finding that does not exist." That's a claim about a hypothetical panel run's finding tags (letters `A` and `B` exist in `run["letters"]`, `C` does not), traced against `tag_of` at line 745 and `cited` at 1122–1127 in the material file. It isn't a version, release, or library-API claim, so there's nothing for WebSearch or context7 to check — the verification here was reading the source, which I did.

No revision to the review. All positions stand as written.