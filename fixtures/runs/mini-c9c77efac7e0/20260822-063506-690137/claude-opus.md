Reviewed against the pasted source only; each finding names the exact transformation, and I traced the string/state path rather than inferring from the symptom.

---

## 1. Bold repair picks the wrong marker whenever the label sits behind list markup

`claims_of`, the branch selector:

```python
if line.lstrip().startswith("**") and text.lstrip().startswith("**"):
```

`MARKUP` strips `- `, `1. `, `| ` etc. before `LABEL` matches, so `label_at` happily accepts a bulleted position — but the repair selector reads `line.lstrip()`, which for any bulleted line starts with the bullet, not `**`. Both documented shapes then fall through to the parity branch and it removes the wrong marker.

**Input A** — `- **REJECT: A1 is wrong.** But **B2** stands.`
`MARKUP` ends at 4 (`- **`), `LABEL` consumes `REJECT: `, so `text = 'A1 is wrong.** But **B2** stands.'`. `line.lstrip()[0] == '-'` → first branch skipped. `text.count("**") == 3` → odd → `rfind` deletes **B2's closer**. `_inline` renders `A1 is wrong.<strong> But </strong>B2 stands.` — "But" is bolded, B2's emphasis is destroyed. The correct removal was the *first* `**`.

**Input B** — `- **REJECT A1:** **critical** is not enforced.`
`text = '** **critical** is not enforced.'`. `text.lstrip()` does start with `**`, but `line.lstrip()` does not, so the position branch is skipped again; parity is odd (3), `rfind` deletes the last marker → `** **critical is not enforced.` → `<strong> </strong>critical is not enforced.` This is *exactly* the output the in-code comment says the position test prevents.

The mechanism is the offset: the selector must ask what the line looks like at `MARKUP.match(line).end()`, which is the same offset `label_at` already uses. Marking as **RE-RAISE: bold-repair parity both ways** — the parity arithmetic is present and correct for `**REJECT…` at column 0; the *selector* is not markup-aware, and the file's own MARKUP comment says a judge writing its whole rebuttal as bullets is the observed common case.

## 2. "This run had no rebuttal round" is asserted from parser silence, and contradicted three ways on the same page

`claims_sec`'s else-branch is keyed on `if claims:` alone and never consults `had_round`:

```python
claims_sec = ('<h2 class="sec">The findings</h2><p class="sub">This run had no '
              'rebuttal round — re-run with <code>--rebut</code> …')
```

**Input:** run.json with `"rebut": true`; all judges wrote their positions as blockquotes (`> **REJECT: A1 …**`), which `MARKUP` deliberately does not strip. `scan_positions` returns `[]` for every judge → `claims == []`.

Page output: masthead prints `· rebuttal` (from `m.get("rebut")`); `had_round` is `True` so every bench row prints the red **"no positions"** cell; the spend cell may print "round one only … the rebuttal round typically costs more than round one"; the tabs render each judge's rebuttal in `#r2`. And the findings section tells the reader the round never happened and to re-run with `--rebut`. Zero positions parsed is a parser result, not a run property; the fallback states it as a run property.

Secondary, same site: on a run with no run.json, `had_round = bool(meta.get("rebut")) or any(n for _, n in cited.values())` reduces to "positions exist", while `_rebutted` thirty lines later uses `any((j.get("rebuttal") or "").strip())`. Two definitions of "did round two happen" on one page, and the file-based one is the correct evidence — the bench renders `—` (not applicable) for judges whose rebuttal files are non-empty and visible in the tab.

## 3. `len(ok)` counts a judge recovered from disk as not having answered

```python
ok = [j for j in js if j["status"] == "ok"]
...
cells = [("the panel", f'<b>{len(ok)}</b> of {len(js)} answered{why}' …)]
```

`unlisted` is assigned in `load_run` purely from `roster - set(judges)` — a *metadata* gap. Its `<name>.md`, `<name>.rebuttal.md` and positions are all loaded and rendered.

**Input:** 5 review files on disk, run.json written before the last judge finished (4 entries). The glance headline reads **"4 of 5 answered"** with the sub-note "1 recovered from disk, absent from run.json" — the page says a judge did not answer while displaying its full answer, its rebuttal positions in the cards, and its row in the scoreboard. The same status also drives

```python
f'<span class="r{"" if j["status"] == "ok" else " out"}" …'
```

and `.groster span.r.out{text-decoration:line-through}`, so that judge's name is **struck through** in the roster beside the note saying it was recovered intact.

**RE-RAISE: `unlisted` reported as cut off** — the fix landed in the `dead`/`part`/`unlisted` split only. The mechanism (`unlisted` treated as a failure status by every `status == "ok"` predicate) is untouched, and it now surfaces in the top-line count and the roster rather than in the caveat text.

## 4. The ungrouped bucket is counted as a finding in the section headline

```python
(blocks if len(cs) > 1 or tag == "\u2014" else quiet).append(block)
...
f'<p class="sub">{len(blocks)} finding{"s" if len(blocks) != 1 else ""} drew '
f'more than one position, most-contested first; each block gathers every '
f'position taken on that finding. …'
```

`"—"` is forced into `blocks` regardless of size, but `len(blocks)` is then reported as a count of findings that drew >1 position.

**Input:** tags A1 (3 positions), A2 (1), B1 (1), plus 6 ungrouped positions. `blocks = [A1, "—"]`, `quiet = [A2, B1]`. Header: **"2 findings drew more than one position"** — one did. The at-a-glance cell on the same page computes `n_findings = sum(1 for t, _ in ordered if t != "\u2014")` = **3 findings**, so the two derived numbers disagree and neither matches the count of multi-position findings (1).

Degenerate case: no finding draws more than one position but some positions are ungrouped → `len(blocks) == 1` → "1 finding drew more than one position, most-contested first". Also, the trailing clause "each block gathers every position taken on that finding" is false for the ungrouped block by construction — those positions are on many different findings.

## 5. `finding_titles` cannot see `## Defect 1:` headings, so the first unfenced numbered list claims the number

```python
FINDING_NUM = re.compile(r"^#{0,4}\s*(\d{1,2})[.)]\s+(.+?)\s*$", re.M)
```

The number must be the first token after the hashes. `load_run`'s own roster comment states the observed corpus shape: *"A real panel.md is full of judge-written `## ` headings (`## Defect 1: ...`)"*. That shape does not match — `##` + `\s*` then `D`. The fence mask removes fenced repro blocks, but nothing removes an **unfenced** numbered list, and `seen` makes the first match final.

**Input** (one judge, letter A):

```
## Defect 1: `secs: null` crashes the report

Repro:

1. Write {"judges":[{"name":"codex","secs":null}]} to run.json
2. Run panel-report

## Defect 2: the tally double-counts group headings
```

Result: `A1 → "Write {"judges":[{"name":"codex","secs":null}]} to run.json"`, `A2 → "Run panel-report"`. Both pass `len(t) > 4`. Every A-tag block on the page is now headlined with a reproduction step, and the same string is repeated in the "contested" glance cell via `_titles.get(t, "")`. The docstring's promise — *"a block is headed by what the finding SAYS"* — is inverted, and the failure is silent because the tag is still correct.

Adjacent to the fixed "titles claimed from fenced lines": the fence mask closed the fenced instance of this mechanism; the mechanism is *first-numbered-line-wins over a pattern that doesn't match the corpus's own heading grammar*, and it survives unfenced.

## 6. Claim cards render absorbed multi-line text through `_inline()` only

`scan_positions` deliberately absorbs continuation lines, including fenced ones (`if not fenced[k]` gates the break, not the append), with `text += "\n" + nxt.strip()`. `card()` then does `decode_letters(_inline(c["text"]), …)` — `_inline` has no fence handling, no list handling, and no `\n → <br>`.

**Input:**

```
- **REJECT: A2.** The signature is:
  ```python
  def f(a, **kw): ...
  ```
  so it is fine.
```

1. `.strip()` on each absorbed line destroys the code's indentation.
2. `text.count("**")` is now **2** (`A2.**` plus `**kw`) — even — so the parity repair does not fire and the label's orphaned `**` survives. Code content is silently voting in the emphasis-repair arithmetic.
3. In `_inline`, `` (`{1,3})(.+?)\1 `` (no `re.S`) matches *within* the ` ```python ` line: backtick-1 opens, backtick-2 is `.+?`, backtick-3 closes → the fence marker becomes `<code>` `` ` `` `</code>` followed by loose text `python`.
4. `re.sub(r"\*\*(.+?)\*\*", …, flags=re.S)` then pairs `A2.**` with `**kw` **across the code block**, emitting `<strong>` around the fence, the `<code>` artifact and `def f(a, `.

Rendered card: one run-on line (no `<br>`), a stray inline code span, the code de-indented, and a `<strong>` spanning the sample. The absorber was added for multi-line positions; the renderer was not brought along.

## 7. The spend floor caveat is suppressed by *any* recorded phase

```python
phase_bits = [p for p in ("rebuttal", "synthesis") if phases.get(p)]
...
floor = _rebutted and not phase_bits
```

`floor` asks "is `phase_bits` empty", not "is every round that ran accounted for".

**Input:** `meta["phases"] = {"synthesis": …}` with rebuttal absent (rebuttal phase not recorded, or recorded and the record lost) while rebuttal files exist. `phase_bits = ["synthesis"]` → `floor` is `False`, and the cell prints an affirmative coverage claim, **"over round 1 + synthesis"**, with no caveat — while omitting the round the comment two lines above measures at 63–65% of total spend. The predicate should be `"rebuttal" not in phase_bits` when `_rebutted`, and symmetrically for synthesis.

Second reachable path in the same expression: `phases.get(p)` is a truthiness test. If the recorded per-phase value is numeric and the rebuttal round cost `0.0` (a panel of `claude-opus` + `codex`, both `billing == "subscription"` per the file's own bench logic), `phases.get("rebuttal")` is falsy → the phase is treated as unrecorded. With rebuttal as the only phase, `phase_bits == []` → `floor` becomes `True` and the page prints "this run predates per-phase accounting … treat this as a floor" about a run that has per-phase accounting and whose rebuttal genuinely cost nothing — a fabricated shortfall.

## 8. `contested[:5]` is a silent cap

```python
hot = "".join(… for t, cs in contested[:5])
...
("contested", f'<b>{len(contested)}</b> drew both an uphold and a reject'
              f'<div style="margin-top:7px">{hot}</div>')
```

With 9 contested findings the cell reads "**9** drew both an uphold and a reject" above exactly 5 titles, with nothing saying the list is truncated. The count and the list are both presented as the answer to the same question. (Low severity — the number is right; the enumeration silently isn't.)

---

## Cleared — what I traced

- **`judge_slug` / `judge_hues` / `judge_css`.** Traced `a-b` vs `a.b` through `re.sub` + `sha256(name)[:4]` — distinct digests, distinct classes. Traced the empty-base path (non-ASCII name → `""` → `"j"` → `j-j-<hash>`) and confirmed the emitted selector is always `.j-` + `[a-z0-9-]+`, so no ident can start with a digit or contain an invalid character. Traced key agreement three ways: `judge_dot(j["name"])`, `judge_css` from `_hues.items()`, and `_hues = judge_hues([j["name"] for j in js])` all key off the same `j["name"]`, so no dot can reference an unemitted rule. `int((base + i*step) % 360)` is bounded to `[0,359]` and interpolates into `hsl(<h> 48% 42%)` — valid space-separated syntax; the property is set on the `.jdot` element itself so the `var(--jh,210)` fallback is never silently used. No finding.
- **`decode_letters` attribute safety.** Traced why `re.split(r"(<[^>]*>)", seg)` cannot be broken by a URL: `_inline` runs `html.escape` first, so any `>` in a judge-supplied href is `&gt;` before `stash("raw", …)` restores it into the attribute. Traced the outer split's non-greedy `<(?:code|pre)\b.*?</(?:code|pre)>` against `md()`'s `<pre class="code"><code>…</code></pre>` — it terminates at `</code>`, leaving `</pre>` in the next segment, where the tag-split isolates and skips it. No finding.
- **`_inline` placeholder integrity.** Traced the `\x00`/`\x01` strip landing *before* `stash`, the `idx >= len(spans)` guard in `restore`, and the `***x***` rule ordering ahead of `**` so the three-marker form cannot split into mismatched tags. The only defect I found here is the interaction in #6, not the placeholder machinery.
- **`md()`'s list builder.** Traced `base = min(it[0] for it in items)` → `build(idx, base)`'s `items[idx][0] >= indent` is unconditionally true on entry, so one call drains all items and the outer `while idx < len(items)` loop cannot spin; traced the `frag[-1].endswith("</li>")` guard against the "<ul>" opener case. Traced `MAXD` : `level = {ind: min(i, MAXD) …}` bounds distinct levels to 7, so `build` recursion depth is ≤ 7 regardless of input indentation. No finding.
- **`cells()` scoping inside `md()`.** Checked the shadowing risk directly: `i` and `n` are both *assigned* inside `cells`, so Python binds them as `cells`-locals at compile time; `md`'s loop counter and line count are untouched. No finding.
- **`_fence_mask` open/close rule.** Traced ```` ```` ```` closing ` ``` ` (allowed, `len >= fence[1]`), ` ``` ` failing to close ```` ```` ```` (falls to `else`, stays masked), and `~~~` vs ` ``` ` (char mismatch, stays masked). No finding.
- **`json.dumps(payload).replace("</", "<\\/")`** — traced the `</script>` breakout path; closed.

Two things I noticed and am *not* raising as defects: `JUDGE_HUES` and `STATE` are dead (`JUDGE_HUES` has no reader since `judge_hues` computes spacing), and `failnote` / `n_ok` / `n_all` / `billed` / `quota` are passed to `TEMPLATE.format` but have no placeholder in it — harmless with `str.format`, but `failnote` still contains the pre-fix logic that files `unlisted` under "answered but was cut off", so it will re-introduce finding #3's wording if anyone reconnects it.