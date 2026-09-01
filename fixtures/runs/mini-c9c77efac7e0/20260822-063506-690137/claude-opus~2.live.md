Reviewed as one judge. Findings first, then the clearances with what I traced.

---

## 1. A rebuttal written as a verdict table contributes zero positions — and the bench asserts the judge produced none

`MARKUP` strips `|`, so tables were meant to be supported, but `LABEL` still requires a `:` / em-dash / en-dash after the verdict word. In a table the verdict cell is delimited by `|`, not by a separator.

Input (a shape models reach for constantly in a "give your position on each finding" round):

```
| Finding | Position | Reasoning |
|---|---|---|
| A1 | UPHOLD | The read at line 42 is unsynchronised. |
| A2 | REJECT | Not reachable from any entry point. |
```

`MARKUP.match` consumes `"| "` (one iteration; the next char is `A`, which ends the repetition), `LABEL.match(line, 2)` is asked to match `UPHOLD|REJECT|…` against `A1 | UPHOLD …` and fails. Verdict-first rows fail too: on `| UPHOLD | A1 | Not reachable |` the qualifier group `[^:—–\n]{0,24}` finds no `:` or dash within 24 chars and the match dies.

Result: `j["labels"]` all zero, `tot == 0`, and because some *other* judge produced positions `had_round` is true, so the bench prints the red cell with `title="this judge was asked to rebut and produced no positions"` — an affirmative claim that is false about a judge whose rebuttal is fully present in the round-2 tab. No cards, no scoreboard bar, absent from the finding blocks.

Partial-match variant, worse than silence: `| UPHOLD | A1 | Confirmed: the race is real |` *does* match, with `qual = "| A1 | Confirmed"`, so the verdict pill renders `UPHOLD | A1 | Confirmed` and the card text starts at "the race is real |".

This is the same class the MARKUP comment says it fixed structurally ("a list of names cannot guard an open set") — the structural strip landed, but the *separator* requirement re-imposes the same closed set at the other end.

## 2. "This run had no rebuttal round" is printed whenever zero positions parse — contradicting three other places on the same page

`build()`: `claims_sec`'s else-branch fires on `if claims:` alone.

```python
claims = claims_of(run)
if claims: ...
else: claims_sec = '…This run had no rebuttal round — re-run with --rebut…'
```

Nothing in that branch consults `meta["rebut"]` or the rebuttal files. With finding #1 (or #10) knocking out every judge, a run that *did* rebut renders:

- masthead: `· rebuttal` (from `m.get("rebut")`),
- the question note: "Judges that rebutted were additionally shown the other reviews" (file-based test),
- bench: `no positions` in red, i.e. "this judge **was asked** to rebut",
- section: "This run had no rebuttal round — re-run with `--rebut`".

The already-fixed `had_round` item repaired the *bench* cell; the section headline is a separate literal that still states the round didn't happen. `_rebutted` — the correct file-based test — is computed 60 lines further down in the same function and not used here.

## 3. `tag_of` accepts any capital-letter-plus-digit token, so ordinary prose invents findings

`TAG_RE`'s third alternative is bare `[A-Z]\d+[a-z]?`, and the letter is never checked against `run["letters"]`, which `claims_of` has in hand.

Input: `- **REJECT: this is a P0 concern, not a defect.**`
→ `tag_of` returns `P0` → the position is grouped under a finding "P0", `raiser = letters.get("P", "")` is empty, `titles.get("P0")` is empty, so the page renders a block headed `P0 · 1 position` in the quiet `<details>`.

Same for `L42` (line citations), `H2`/`H3` (heading levels), `N2` (`O(N2)`), `Q4`, `S3`, `A100`, `K8s` (`\d+[a-z]?` swallows the `s`). Two consequences beyond the phantom block: the position is stolen from the honest "ungrouped — described, not referenced" bucket (so the "not grouped" glance cell *under*counts), and `n_findings` in "**N** positions on **M** findings" is inflated by one fake finding per distinct noise token.

The leftmost-match rule saves the common case (`REJECT: A1 is a P0 concern` → `A1`), so this fires exactly when the judge described the finding instead of citing it — the case the ungrouped bucket exists to report.

## 4. `~~~` fenced code renders as struck-through prose

`md()`'s fence branch matches backticks only: `re.match(r"^\s*(`{3,})\s*([^`]*)$", ln)`. `_fence_mask` recognises `~{3,}` and so does the list-continuation absorber — the top-level renderer is the one place that doesn't.

Input in any review or rebuttal:

```
~~~python
def f(x):
    return x is None
~~~
```

No fence branch, no list, no table → it lands in `para` and goes through `_inline`, where `~~([^~]+)~~` matches from the second tilde of the opener to the first two of the closer. Output: `~<del>python<br>def f(x):<br>    return x is None<br></del>~` — the code shown as strikethrough, indentation collapsed by HTML. If the block contains a blank line it is worse: `flush()` splits it, and any line inside beginning with `#`, `-`, `|` or `>` is then re-parsed as a heading, list, table or blockquote. That is precisely the "code as prose, prose as code" inversion the `{python}` info-string comment describes, still live for the tilde flavour.

## 5. The bold repair removes the wrong marker when the label's bold closes mid-line

`claims_of()`: the first branch requires *both* `line` and `text` to start with `**`; otherwise an odd marker count removes the **last** one, on the stated premise that "the unpaired one is the LAST".

Input: ``**REJECT: A1 is wrong.** The `foo` path **never** runs.``

`m.end()` lands after `REJECT: `, so `text = "A1 is wrong.** The `foo` path **never** runs."` — it does *not* start with `**`, so the elif runs. Count is 3 → odd → `rfind` removes the closer after "never" → `_inline` then pairs the label's orphaned closer with "never"'s opener:

> A1 is wrong.**<strong> The `foo` path </strong>**never runs.

A clause that was never emphasised is bolded, and the word that was loses it. The orphan here is the *first* `**` in `text` (the label's closer), which the position test can't see because the label consumed the text between the two markers.

## 6. Position cards render multi-line arguments through `_inline` only, so lists and code collapse into one run-on line

`card()` emits `decode_letters(_inline(c["text"]), …)` — no `md()`, no `<br>`, no paragraph handling — while `scan_positions`'s absorber deliberately pulls in continuation lines and `.strip()`s each one.

Input:

```
**UPHOLD A1: the race is real.**
- The read at line 42 is unsynchronised.
- The write at line 88 happens on the pool thread.
```

Card body: `the race is real. - The read at line 42 is unsynchronised. - The write at line 88 happens on the pool thread.` — one flowed line, bullets as literal hyphens. An absorbed fenced block is worse: `.strip()` has already deleted every indent, the ` ``` ` markers survive as literal text (the `(`{1,3})(.+?)\1` span can't match a lone fence line), and the newlines collapse, so a code sample renders as a single run of tokens. The same rebuttal renders correctly in the round-2 tab, which goes through `md()` — the by-finding view, which is the page's headline feature, is the degraded copy.

## 7. `finding_titles` headlines a finding with its severity tag

The bold extractor takes whatever bold span opens the item, on the assumption it is the title:

```python
b = re.match(r"\*\*(.+?)\*\*", raw)
t = b.group(1) if b else raw
```

Input (`## 1. **Critical:** `parse()` dereferences a null pointer`) → `t = "Critical:"` → rstrip → `"Critical"` → passes `len(t) > 4` → `out["A1"] = "Critical"`. A judge that prefixes severity (`1. **HIGH** — Race in worker pool`, `1. **[P0]** …` → "P0]" → 3 chars, dropped instead) gets *every* finding block headed by its severity word, and the at-a-glance contested list reads `A1 3u 2r Critical`. The block "names a finding without saying what it IS" — the exact failure the function was written to remove, now with a plausible-looking word in place of the tag.

Second mis-title in the same function: the no-bold path only cuts at a sentence end when `cut.start() > 24`. `1. Race in pool. The read at line 42 is unsynchronised and the write at line 88 …` has its first sentence end at offset 13, so no cut happens and the headline runs 110 characters into the argument before the ellipsis.

## 8. The spend floor caveat is suppressed when only *some* phases are accounted, and asserted falsely for a zero-valued phase

```python
phase_bits = [p for p in ("rebuttal", "synthesis") if phases.get(p)]
floor = _rebutted and not phase_bits
```

`floor` asks whether *any* phase is recorded, not whether the *rebuttal* is. A run whose `run.json` carries `"phases": {"synthesis": …}` but no rebuttal entry gets `phase_bits == ["synthesis"]` → `floor` False → the cell prints `$X billed` + "over round 1 + synthesis" with no floor warning, while the rebuttal round — which the comment measures at 63–65% of total spend — is missing from the number. The caveat is withheld from a case that needs it more than the legacy case it was written for.

The inverse: the test is truthiness, not presence. Any falsy per-phase record (`0`, `0.0`, `{}` — e.g. an all-subscription panel where round two billed nothing, or a serialiser that writes an empty object for a no-cost phase) yields `phase_bits == []` → the page asserts "this run predates per-phase accounting … treat this as a floor" about a run that has exact per-phase accounting. That is a false provenance claim, in the same cell that exists to prevent one.

## 9. "N findings drew more than one position" counts the ungrouped bucket as a finding

```python
(blocks if len(cs) > 1 or tag == "\u2014" else quiet).append(block)
…
f'<p class="sub">{len(blocks)} finding{…} drew more than one position…'
```

The ungrouped bucket is unconditionally in `blocks`. With 7 argued findings plus an ungrouped block the sub-head says "8 findings drew more than one position" while the section shows 7 findings and one bucket that is explicitly not a finding. If the ungrouped bucket holds exactly one position and nothing else was argued, it says "1 finding drew more than one position" when no finding drew more than one, and the block below it is headed "ungrouped — described, not referenced".

Related mismatch in the glance: "**{n_pos}** positions on **{n_findings}** findings" — `n_pos` counts every position including ungrouped ones, `n_findings` excludes the bucket, so the two halves of the sentence are drawn from different populations. The "not grouped" cell states the remainder separately, so the page carries both numbers without reconciling them.

## 10. `_fence_mask` opens a phantom fence on a line that merely *starts* with an inline triple-backtick span

`md()` requires the whole line to be `^\s*(`{3,})\s*([^`]*)$` — no backticks in the info string. `_fence_mask` has neither the `$` anchor nor the `[^`]*` guard:

```python
m = re.match(r"^\s*(?:>\s?)*\s*(`{3,}|~{3,})", ln)
```

Input line in a rebuttal (about markdown handling — this corpus is full of it): ` ```REJECT``` is a tag I never wrote, not a verdict.`

The mask opens a fence on that line. Every subsequent line is masked until another line begins with three backticks — i.e. the *next real code fence's opener closes the phantom*, which inverts the mask from there: the real block's body is scanned and its **closer** opens the next phantom. So both directions fail at once — the judge's own `**REJECT: A1 …**` lines are dropped, and a verdict line quoted *inside* a fence (the single most likely false position, per the function's own docstring) is counted and carded as that judge's position. `md()` renders the same line correctly as an inline code span, so the rendered review and the tally disagree about where the code is.

`finding_titles` shares the mask, so the same line in a round-one review blanks every finding title after it.

## 11. In the panel.md fallback, a failed judge is either mislabelled `unlisted` or dropped entirely

Two patterns in `load_run` disagree about what a judge heading looks like. The judge parser requires the timing field:

```python
r"^## ([\w.-]+)\s+\(`([^`]+)`\)\s+—\s+([\d.]+)s(.*)$"
```

The status scanner deliberately does not:

```python
hdr = re.compile(r"^## (\S+)\s+\(`[^`]+`\)[^\n]*$", re.M)
```

A legacy run whose failed judge is headed ``## or-kimi (`kimi-k2`) — **DID NOT ANSWER**`` (no `N.Ns`) never enters `judges`, so the status loop — which iterates `judges.items()` — never reaches its section and never sets `harness`. It falls to `roster_gap` and is filled with `status="unlisted"`, so the glance prints "1 recovered from disk, absent from run.json" and the red `gapnote` says "absent from run.json" for a run that has no run.json at all. The one judge the reader most needs classified is the one classified wrongly.

Worse branch of the same gate: `if name not in roster: continue`, and `roster` is built from `<name>.md` files. If the harness writes the DID-NOT-ANSWER marker into panel.md without leaving a `<name>.md` (which is what "the marker is written IN PLACE OF the review" implies), the judge cannot exist at all — the bench shows the survivors and the glance reads "4 of 4 answered", contradicting the footer's "judges that failed or were cut off are marked, not dropped".

## 12. `unlisted` judges are counted as not having answered, and struck through in the roster

The fix for "`unlisted` reported as cut off" split the *why* line but left the counts alone:

```python
ok = [j for j in js if j["status"] == "ok"]
…("the panel", f'<b>{len(ok)}</b> of {len(js)} answered{why}'
roster: f'<span class="r{"" if j["status"] == "ok" else " out"}"'   # .out = line-through
```

Input: `run.json` written before the fifth judge finished, all five reviews on disk. The glance reads "**4** of 5 answered", the fifth judge's name is struck through in the roster (`.groster span.r.out{text-decoration:line-through}`), and its complete review, rebuttal and cost are rendered two sections below. The metadata gap is stated in the small print and denied by the headline number.

(Related dead code: the `failnote` lambda passed to `TEMPLATE.format` still classifies `unlisted` as "answered but was cut off" — it is inert only because `{failnote}`, `{n_ok}`, `{n_all}`, `{billed}` and `{quota}` no longer appear in `TEMPLATE`.)

## Smaller

- **Unterminated fence swallows the tail into one card.** In `scan_positions`, the absorber's break tests are all inside `if not fenced[k]:`. After an unclosed ` ``` ` (routine for a judge with `status="incomplete"`, i.e. cut off mid-block), every remaining line — blank lines, headings, later verdicts — is appended to the last position's `text`, so one card contains the rest of the document.
- **Escaped pipes in tables.** `cells()` protects backtick runs but not `\|`. `| the operator `a` | matches a \| b | ok |` splits at the escaped pipe, producing one more `<td>` than there are `<th>`s and shifting every cell right of it.
- **`JUDGE_HUES` is dead.** `judge_hues()` computes `360/len(names)` spacing and never reads the tuple; the docstring's "10-hue palette" refers to a constant nothing consumes.

---

## What I cleared, and what I traced to clear it

- **`judge_slug` / `judge_hues` / the dot CSS (question 2).** Traced: `judge_slug` output charset is `[a-z0-9-]+-[0-9a-f]{4}`, always `j-`-prefixed at the call site so no class starts with a digit, and an empty sanitisation falls back to `"j"`; a collision now needs both the sanitised base *and* a 16-bit digest prefix to agree. `judge_css` is built with an f-string (`{{--jh:{h}}}` → `{--jh:210}`) and passed to `TEMPLATE.format` as a *value*, so its braces are never re-scanned. `--jh` is set on `.j-<slug>`, which is on the same element carrying `.jdot`, so `hsl(var(--jh,210) 48% 42%)` resolves on that element; after `var()` substitution it is the CSS Color 4 space-separated form, valid in current browsers, and the `@media`/`[data-theme]` overrides only change S/L. I checked every `judge_dot` call site (bench, tabs, glance roster, `card()` via `c["judge"]`) — all names come from `run["judges"]` keys, which is exactly what `_hues` was built over, so no dot falls back to the default 210. At 10 judges (36° apart) the light-mode 48%/42% and dark-mode 58%/64% pairs stay above 3:1 against `--surface`. No defect found.
- **The `\x00`/`\x01` placeholder machinery in `_inline`.** Traced: control bytes are stripped after `html.escape` and before the first `stash`, `restore` bounds-checks the index, and `stash("raw", …)` is reachable only from the link rule whose URL group is anchored to `https?://`, so no `javascript:`/`data:` href can reach the `raw` path.
- **The JSON island.** Traced: every value in `payload` passes through `md()` → `_inline` → `html.escape`, so no raw `<` reaches `judges_json`; with `</` escaped and no raw `<`, the `<!--<script` double-escape breakout that would otherwise apply to script-data parsing is unreachable.
- **`decode_letters` attribute safety.** Traced both splits: the outer one removes `code`/`pre` regions, the inner `(<[^>]*>)` split means `DECODE_RE.sub` only ever runs on segments that do not begin with `<`, so no attribute value (including the `href` case in the comment) can be rewritten.
- **`find_runs` sort.** Traced: `out.sort(reverse=True)` on `(mtime, Path)` tuples cannot raise on an mtime tie because `PurePath` implements the ordering operators for same-flavour paths.
- **`cells()` scoping.** Traced: `i`, `n`, `run`, `buf` are all assigned inside the nested function, so they are locals and do not clobber `md()`'s loop variables `i`/`n` — the backtick-run tracker is correct for `` `a|b` ``, ``` ``a|b`` ```, and unbalanced runs (which leave `run != 0` and simply stop splitting for the rest of the row).

I did **not** verify: the actual `run.json` schema (so #8's `phases` value type is inferred from the truthiness test, not observed), whether llm-panel writes a `<judge>.md` for a judge that never answered (#11's second branch), and whether any file other than `panel.md`/`prompt.md`/`<judge>*.md` is written into a run directory — a stray `notes.md` would become a judge named `notes` with `status="unlisted"`, a tab, a hue, and a slot in the "of N answered" denominator.