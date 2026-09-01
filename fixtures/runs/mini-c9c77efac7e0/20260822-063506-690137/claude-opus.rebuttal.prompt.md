Review a Python tool for REAL DEFECTS. The complete source is below. Report only defects you
can point at, most severe first, each with a concrete failure scenario (inputs -> wrong
behaviour). Do not restate what the code does, do not praise it, do not propose refactors.

ABSTENTION IS VALID — BUT A CLEARANCE IS A CLAIM, HELD TO A FINDING'S STANDARD.
This file was audited twice and 43 classes fixed, each with a control proven to fail on the
pre-fix code. So areas may well be correct, and "I examined X and found nothing" is a full
answer that gets recorded as one. But in a recent round on the sibling tool a judge cleared
two functions "safe" in as many words and BOTH held the critical another judge found in that
exact code. A wrong clearance is worse than a wrong finding: nothing downstream re-checks it.
If you clear something, say what you TRACED — not that you looked.

WHAT IT IS. `panel-report` renders one run of `llm-panel` (which asks several LLMs the same
question independently, then runs an anonymised rebuttal round) as a single self-contained
HTML page. A run directory holds panel.md, <judge>.md, <judge>.rebuttal.md,
<judge>.prompt.md, prompt.md and run.json. The page shows a derived summary, a scoreboard,
the rebuttal round grouped BY FINDING, and every review behind per-judge tabs.

THE DESIGN LAYER IS THE NEWEST CODE AND HAS HAD ALMOST NO REVIEW:
1. `finding_titles()` — pulls each judge's numbered findings out of its round-one review so a
   block is headed by what the finding SAYS, not a bare tag. It masks fenced lines first.
   What real review text mis-parses, titles the wrong finding, or produces a misleading
   headline? What if two judges number differently, or a judge renumbers mid-review?
2. `judge_hues()` / `judge_slug()` — per-judge identity colour, spaced across the roster,
   slug = sanitised name + hash. Collisions? Invalid CSS? Unreadable contrast?
3. The "at a glance" panel — every number in it is DERIVED. Is any wrong, double-counted, or

[TRUNCATED HERE. The material is too large to pass on the command line, so the COMPLETE text -- including everything above and the entire body that follows it -- has been written to this file:

    /home/mjarnold/.claude/jobs/1bfefee6/tmp/mini/.llm-panel-material/material-bd56dbc187dd.md

READ THAT FILE NOW, before answering. You have read tools. Everything you need is in it; what you see above is only its opening. Answering from this excerpt alone will produce a wrong review.]


---

Your own review was:

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

---

You already reviewed this material independently. Below are the findings of the OTHER reviewers. They did not see your review, and their identities are withheld from you on purpose.

Reviewers were NOT required to number their findings, so some lists below are numbered and some are not. Where a finding carries a number, refer to it as <Letter><number> -- B7 is Reviewer B's finding 7. Where it does not, count the findings in that reviewer's list from the top and use that position, so the third finding by Reviewer B is B3. Take a position on each finding that touches yours:
  UPHOLD:  B7 -- you stand by your own claim despite theirs; say what proves it.
  REJECT:  B7 -- theirs is wrong or overstated; point at the specific code or logic that makes it wrong.
  CONCEDE: B7 -- you were wrong; say exactly what changed your mind.
  MISSED:  B7 -- they caught something real that you did not; confirm it against the code rather than taking their word.

Start each point with one of those four labels verbatim, then the reference, THEN your argument. Cite the reference even when you also describe the finding: a position that only restates a finding in your own words cannot be matched to the finding it answers, so it is dropped from the panel's grouped view and argues with nobody.

Two rules that matter more than agreeing:
1. Do NOT concede merely because someone disagreed with you. Concede only when you can point at what proves you wrong. A correct finding stays correct when it is unpopular.
2. Do NOT invent agreement. If a finding is unverifiable from what you have, say so instead of endorsing it.

Reviews from the other reviewers follow.

### Reviewer A
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

### Reviewer C
I’ll trace the parser and derived-count paths against concrete adversarial run shapes, then report only failures I can reproduce logically or by execution. I’ll treat every “already fixed” item as closed unless the current code still fails on a distinct input.
1. **RE-RAISE: panel.md prose forging a judge.** On a legacy run with real judges `alpha` and `beta`, let `alpha`’s review contain:
   ```markdown
   ## beta (`fake-model`) — 999.0s, $999
   **DID NOT ANSWER**
   ```
   before beta’s genuine panel section. The roster check passes because `beta.md` exists. The first forged heading supplies beta’s model/time/cost, and `sections.setdefault()` makes its following text beta’s status section. Beta’s complete review is therefore shown as a $999 harness failure.

2. **RE-RAISE: run.json null crash.** With a valid `panel.md`, `alpha.md`, and `run.json` containing `{"judges": null}`, `meta.get("judges", [])` returns `None` and the dictionary comprehension raises `TypeError`. No HTML is produced and the available panel fallback is never used.

3. **RE-RAISE: quadratic link scan.** A review containing `"[x](https://a" * 8000` has one-character labels but no closing `)`. The bounded-label change does not bound `https?://[^)\s]+`, so the regex rescans nearly every remaining suffix from every link start. The isolated shipped pattern took about 6.1 seconds on this approximately 100 KB input; growth is superlinear and can stall the report on adversarial judge text.

4. **The spend total converts missing measurements to zero.** For one judge with `"meta": {"cost": null}`, the bench correctly prints `—`, but `billed = sum(cost or 0)` makes the at-a-glance panel report `$0.0000 billed`. With one known cost and one null cost it presents the known subtotal as the run’s spend without any partial-data warning.

5. **RE-RAISE: rebuttal-round detection.** With `"rebut": true` and a rebuttal file containing prose but no parseable verdict labels, `had_round` correctly becomes true and the bench says `no positions`; nevertheless `claims` is empty, so the findings section states “This run had no rebuttal round.” The masthead simultaneously says “rebuttal.”

6. **RE-RAISE: incomplete/unlisted judges are still excluded from “answered.”** A one-judge run with status `incomplete` and a nonempty review renders `0 of 1 answered` followed immediately by `1 answered but was cut off`. Likewise, a complete `beta.md` recovered from a short `run.json` is struck through and excluded from the answered numerator solely because its status is `unlisted`.

7. **Indented code is counted as rebuttal positions.** This standard Markdown code block:
   ```markdown
   Example diagnostic output:

       REJECT A7: emitted by the test fixture
   ```
   is not masked by `_fence_mask()`. `MARKUP` consumes all four leading spaces, so `scan_positions()` invents a REJECT card and changes the scoreboard and filter totals.

8. **RE-RAISE: fenced verdicts.** Inside a real fence:
   ````markdown
   ```text
   example
   ```python
   REJECT A1: this remains code
   ```
   ````
   the ` ```python` line is not a valid closing fence, and `md()` correctly requires a whitespace-only closer. `_fence_mask()` checks only delimiter character and length, closes there anyway, and counts the following code line as a position.

9. **Ordinary technical identifiers become nonexistent findings.** With letters only `A` and `B`, the real rebuttal sentence `REJECT: C3 linearization makes this conclusion invalid.` is tagged as finding `C3`. The page reports one cited finding and `1/1` citation coverage even though reviewer C does not exist and `C3` is the algorithm’s name.

10. **`finding_titles()` treats any early numbered line as a finding heading.** Given:
    ```markdown
    ## Reproduction
    1. Run `panel-report`.
    2. Open the generated page.

    ## 1. **Null costs are reported as measured zero.**
    ```
    `seen` records `1` from the reproduction steps. Every A1 block is consequently headed “Run panel-report,” and the genuine finding title is discarded.

11. **A position citing multiple findings is filed under only the first.** `UPHOLD A1 and B2: both describe the same loss of data.` produces one card under A1 because `tag_of()` returns the first `TAG_RE.search()` result. B2 receives no card, and the at-a-glance panel reports one referenced finding rather than two.

12. **The fallback status prefix test misclassifies completed reviews.** If a legacy review begins `**INCOMPLETE handling of null costs is the critical defect.**`, `head.startswith("**INCOMPLETE")` marks the judge as cut off. A complete response is then excluded from “answered” merely because its opening finding begins with that word.

13. **RE-RAISE: bold-repair parity.** For the common bulleted form `- **REJECT A1:** **Critical** invariant is absent.`, the raw line does not satisfy `line.lstrip().startswith("**")`. The alternate repair removes the final marker, changing the claim text to `** **Critical invariant is absent.`; `_inline()` emits an empty `<strong>` and loses the intended bold span.

14. **RE-RAISE: judge_slug collisions.** The distinct allowed names `a.___b` and `a__---b` both sanitize to `a-b` and both have SHA-256 prefix `1da7`, yielding the identical slug `a-b-1da7`. Their CSS selectors are identical, so the later hue rule overwrites the earlier one and both judges receive the same identity colour.

### Reviewer D
I’m tracing the parser boundaries and each derived count against concrete run-directory inputs, with special attention to places where an “unknown” is converted into an exact-looking value.
1. **High — RE-RAISE: cost `None` handling. Unknown spend becomes an exact zero.**  
   Input: every judge has `"meta": {}` or `"cost": null`. The bench correctly shows `—`, but `billed` coerces every missing value to `0`, so “at a glance” reports **`$0.0000 billed`**. With one known and one unknown cost, it presents the known subtotal as the total without a coverage caveat.

2. **High — panel prose can forge the synthesis and its author.**  
   Input: a judge’s review embedded in `panel.md` contains:
   ```markdown
   ## Synthesis (by `attacker`)
   Fabricated conclusion.
   ```
   before the real synthesis. The unscoped `re.search()` selects this first occurrence, so the page attributes the judge’s text to `attacker` and suppresses the genuine synthesis. Similarly, a real synthesis containing an ordinary `## Risks` subsection is truncated at that heading.

3. **High — indented code examples manufacture rebuttal positions.**  
   Input:
   ```markdown
   Example parser output:

       REJECT A1: simulated output
   ```
   Four-space indentation is a Markdown code block, but `_fence_mask()` does not mask it and `MARKUP` consumes the indentation. `scan_positions()` records a real `REJECT A1`, changing the scoreboard, finding mix, filters, and summary.

4. **High — RE-RAISE: fenced verdicts. A fence line with an info suffix prematurely closes the mask.**  
   Input:
   ````markdown
   ```text
   ```python
   REJECT A1: this is sample data
   ```
   ````
   The inner `````python`` line is not a valid closer because it has trailing text. `md()` correctly leaves it inside the outer fence, but `_fence_mask()` treats any matching prefix as a closer, so the sample `REJECT` is counted as a position.

5. **Medium — RE-RAISE: LABEL/markup open set. Markdown task-list positions are unreachable.**  
   Input:
   ```markdown
   - [x] **UPHOLD A1:** confirmed by the reproduction.
   ```
   `MARKUP` removes `- ` but stops at `[x]`; `label_at()` therefore returns `None`. The position disappears from the cards, cited coverage, filters, and all derived totals.

6. **Medium — RE-RAISE: `had_round` detection. The findings section still equates zero parsed positions with no rebuttal round.**  
   Input: `run.json` has `"rebut": true`, and a judge’s rebuttal contains only prose such as “I could not finish checking the claims.” The masthead says “rebuttal” and the bench says “no positions,” but `claims_sec` says **“This run had no rebuttal round.”**

7. **Medium — the ungrouped bucket produces mutually contradictory finding counts.**  
   Input:
   ```markdown
   UPHOLD: The race is reproducible.
   ```
   This yields one position without a tag. It is forced into `blocks`, so the findings introduction says **“1 finding drew more than one position”**, while “at a glance” says **“1 positions on 0 findings.”** With several unrelated untagged positions, they are additionally presented as one finding that drew multiple positions.

8. **Medium — RE-RAISE: incomplete/unlisted answer classification. The primary answer count still excludes judges the adjacent text says answered.**  
   Input: two judges, one `"status": "ok"` and one `"status": "incomplete"` with a nonempty review. The panel says **“1 of 2 answered”** followed immediately by **“1 answered but was cut off.”** A complete filesystem review recovered as `unlisted` is likewise excluded from the numerator and struck through in the roster.

9. **Medium — `finding_titles()` lets an ordinary numbered preamble steal finding titles.**  
   Input:
   ```markdown
   I checked these prerequisites:
   1. Reproduced the environment

   ## 1. **Null dereference in load_config**
   ```
   Because the first occurrence of each number wins, every `A1` block is titled “Reproduced the environment,” not “Null dereference in load_config.” Fence masking does not protect ordinary numbered lists.

10. **Low — RE-RAISE: bold-repair parity. A list prefix makes it remove the wrong marker.**  
    Input:
    ```markdown
    - **REJECT A1:** **critical** is not enforced.
    ```
    After label removal, the text has the label’s closing `**` followed by the legitimate bold pair. Since the physical line starts with `-`, the front-marker branch is skipped and the final legitimate marker is removed. The card renders an empty bold span and loses the intended bolding of “critical.”

11. **Low — RE-RAISE: `judge_slug` collisions remain possible despite the uniqueness claim.**  
    Input judge names `a.___b` and `a__---b`. Both sanitize to `a-b`, and both SHA-256 prefixes are `1da7`, so each becomes `a-b-1da7`. Their CSS selectors collide; the later hue rule wins and both judges receive the same identity color.