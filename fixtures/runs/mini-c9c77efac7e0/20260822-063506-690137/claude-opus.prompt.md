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
   presented as measured when it was not? The `floor` caveat on spend especially.
4. The argued/quiet split — findings with one position fold into a <details>. Anything
   unreachable, uncountable, or inconsistent with the filter counts?
5. `scan_positions()` / `_fence_mask()` / `label_at()` / MARKUP / the bold repair — what real
   rebuttal text is still miscounted in either direction?
6. `load_run()` — roster-from-filesystem, the panel.md fallback, `_num`, the status scan.
7. `md()` / `_inline()` / `decode_letters()` — judge text is arbitrary and adversarial.
8. Anywhere a failure is swallowed, or a number is presented as measured when it was not.

ALREADY FIXED — do not re-raise as new; mark duplicates "RE-RAISE: <x>" and show an input
that still fails if you believe one is live. Briefly: LABEL/markup open set, verdict word
boundary, hyphenated verdicts, fenced AND blockquoted verdicts, bold-repair parity both ways,
multi-line positions; run.json null secs/meta crash; cost None as "subscription"; footer
source claim; short run.json hiding judges; nested-list dedent dropping items; decode_letters
in href and its private pattern; quadratic link scan; synthesis truncated at `---`; panel.md
prose forging a judge AND a judge forging its own metadata; comma costs; image drops and
relative paths; the dead IMG_TYPES control; tautological controls; controls importing the
installed copy; n_fam counting the unknown bucket; `incomplete` vs "did not answer";
unescaped status; chars labelled bytes; Google Fonts; `***x***`; 4-backtick fences; pipes in
table code cells (single AND multi backtick); `{python}` fence info strings; per-judge
prompts discarded; token totals as measured zero; fenced code inside a bullet; had_round
reading a key that does not exist; titles claimed from fenced lines; judge_slug collisions;
the stale filter counter; the floor caveat missing on legacy runs; `unlisted` reported as
cut off.

Answer as one independent judge; you will not see the others this round.

--- FILE: panel-report ---
#!/usr/bin/env python3
"""Render an llm-panel run as a single self-contained HTML page.

A panel run leaves 4-5 essays plus a rebuttal round on disk -- 50-90 KB of argument across
20+ files. panel.md concatenates them, which means comparing what five models said about
ONE claim requires holding five documents in your head. This inverts that: the rebuttal
round is shown BY CLAIM, and the full reviews sit behind per-judge tabs underneath.

    panel-report                     # newest run, any repo
    panel-report --list              # recent runs
    panel-report <run-dir> --open
    panel-report --repo confound     # newest run whose repo key matches

Reads run.json when present (llm-panel writes it); falls back to parsing panel.md for runs
recorded before that existed, and says which it used.
"""
import argparse
import hashlib
import datetime as dt
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

STATE = pathlib.Path(__file__).resolve()  # placeholder; real root resolved below
# TWO roots, because llm-panel has two. It refuses to write inside the reviewed repo
# (judges can read their cwd, which would leak rivals' answers) and falls back to
# ~/.llm-panel. Running a panel from $HOME trips that check -- $XDG_CACHE_HOME is
# under $HOME -- so ordinary runs land in the fallback, where a single-root reader
# reports "no runs found" for panels that plainly exist.
RUNS_ROOTS = [pathlib.Path(os.environ.get("XDG_CACHE_HOME") or (pathlib.Path.home() / ".cache"))
              / "llm-panel" / "runs",
              pathlib.Path.home() / ".llm-panel" / "runs"]
RUNS = RUNS_ROOTS[0]

# Which vendor each judge belongs to. A panel's value is cross-family independence, so the
# family is worth showing next to the name -- three judges from one vendor is one opinion.
FAMILY = {
    "codex": "OpenAI", "claude-opus": "Anthropic", "claude-sonnet": "Anthropic",
    "or-grok": "xAI", "vis-grok": "xAI", "or-kimi": "Moonshot", "vis-kimi": "Moonshot",
    "or-deepseek": "DeepSeek", "deepseek": "DeepSeek", "deepseek-pro": "DeepSeek",
    "or-glm": "Zhipu", "or-glm-free": "Zhipu", "glm": "Zhipu",
    "or-qwen": "Alibaba", "qwen": "Alibaba", "local-qwen": "Alibaba (local)",
    "vis-gemini": "Google", "vis-gpt": "OpenAI", "kimi": "Moonshot",
    "local-llama": "Meta (local)", "local-small": "Alibaba (local)",
    "nemotron": "NVIDIA", "lightning": "NVIDIA", "big-pickle": "opencode",
}
KINDS = ["UPHOLD", "REJECT", "CONCEDE", "MISSED"]
# Judges separate the verdict from the claim with a COLON or an EM/EN DASH, and may
# qualify it ("CONCEDE, narrowly:"). A colon-only pattern counted 3 of claude-opus's
# 57 positions in one run -- the most thorough judge was almost entirely absent from
# the tally. A bare hyphen is deliberately NOT a separator: it would swallow prose
# like "REJECT-worthy items are listed below". Measured: 156 -> 210 positions, no
# false positives on a probe of verdict-word-initial prose.
# MARKUP is everything that can sit between the margin and a verdict word. It is an OPEN
# SET -- `- `, `* `, `+ `, `1. `, `1) `, `> `, `#### `, `| `, `**`, and any combination --
# and `^\s*\**` enumerated exactly two members of it. A judge that wrote its whole rebuttal
# as a bulleted or numbered list contributed ZERO positions: no cards, an all-zero tally,
# and a bench row rendering "—", i.e. presented as a judge that skipped the round. Four of
# five judges raised this, and it is the FOURTH patch to this one pattern for the same
# class of miss (colon-only dropped claude-opus; adjacency dropped or-kimi; the qualifier
# ate the tag). A LIST OF NAMES CANNOT GUARD AN OPEN SET: strip the markup structurally,
# then match the verdict at position 0 of what remains.
# NOT `#{1,6}`: a heading is a section LABEL, not a position. Allowing it gained exactly
# three corpus matches and all three were or-kimi's group headers (`## MISSED — real
# findings I confirmed...`) sitting above the `**MISSED: ...**` bullets they introduce --
# counting the header would have double-counted every position under it. A heading also
# stops the continuation absorber, so such a "position" would card as a bare title with no
# argument. Measured against 24 rebuttals: 3/3 heading matches were group labels.
# `>` is NOT stripped. A blockquote in a rebuttal is overwhelmingly someone ELSE's line
# being quoted -- "Reviewer B wrote: > REJECT A1: ..." was counted as the QUOTING judge's
# own REJECT, moving the scoreboard, the filter totals and the finding mix. That is the same
# class as a fenced verdict and gets the same treatment. It costs the rare judge who writes
# its own position as a blockquote, which is the cheaper mistake by far.
MARKUP = re.compile(r"^(?:\s*(?:[-*+]|\d+[.)]|\|)\s*)*\s*\**\s*")
# `\b` after the alternation: without it `REJECTED:`, `CONCEDED:`, `UPHOLDING:` and even
# "Rejecting the premise here:" (qualifier = "ing the premise here") were counted as
# positions -- a past-tense summary line invented cards nobody wrote.
# Trailing `\s*` not `\s`: `UPHOLD:no space after the colon` was silently dropped.
# `(?![\w-])` rather than `\b`: `\b` is satisfied by the boundary before a HYPHEN, so
# "REJECT-worthy items: A1 and A2" -- a category heading -- became a REJECT position filed
# under A1, with "-worthy items" absorbed as the qualifier.
LABEL = re.compile(r"(UPHOLD|REJECT|CONCEDE|MISSED)(?![\w-])\**([^:—–\n]{0,24})?\s*[:—–]\s*",
                   re.I)


def _fence_mask(lines):
    """Which lines sit inside (or are) a fenced code block. A rebuttal round is mostly
    judges QUOTING each other, so `REJECT: ...` inside a fence is the single most likely
    false position on the page -- it was counted in the tally, in the filter counts, and
    rendered as a card attributed to the quoting judge."""
    mask, fence = [], None          # fence = (char, length) while open
    for ln in lines:
        # `> ` is skipped so a fence opened inside a blockquote is still a fence; without
        # this, quoted code blocks were not masked at all and every verdict in them counted.
        m = re.match(r"^\s*(?:>\s?)*\s*(`{3,}|~{3,})", ln)
        if m and fence is None:
            fence = (m.group(1)[0], len(m.group(1)))
            mask.append(True)
        elif m and fence and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
            # A CLOSER must be at least as long as its opener. Comparing only the character
            # let an inner ``` close an outer ```` fence, unmasking everything after it --
            # the same defect md() had, fixed there and not here.
            fence = None
            mask.append(True)
        else:
            mask.append(fence is not None)
    return mask


def label_at(line):
    """The verdict match for `line`, or None. Markup first, verdict second."""
    return LABEL.match(line, MARKUP.match(line).end())


def scan_positions(rebuttal):
    """Every rebuttal position, fence-aware. ONE definition of what a position is:
    load_run's tally and claims_of used to decide separately, so the bench count and the
    cards could disagree and neither was wrong on its own terms."""
    lines = (rebuttal or "").split("\n")
    fenced = _fence_mask(lines)
    out = []
    for i, line in enumerate(lines):
        if fenced[i]:
            continue
        m = label_at(line)
        if not m:
            continue
        text = line[m.end():].strip()
        k = i + 1
        while k < len(lines):
            nxt = lines[k]
            if not fenced[k]:
                if not nxt.strip() or label_at(nxt) or nxt.lstrip().startswith("#"):
                    break
            text += "\n" + nxt.strip()
            k += 1
        out.append({"i": i, "line": line, "kind": m.group(1).upper(),
                    "qual": (m.group(2) or "").strip(), "text": text})
    return out


# ---------------------------------------------------------------- markdown (proven set)
def _inline(t):
    t = html.escape(t)
    # Strip the control bytes used as placeholder delimiters BEFORE stashing. Judge text is
    # arbitrary (hexdumps, binary quoted into prose), and a literal \x00N\x01 in the input
    # either indexed past the end of `spans` -- crashing the whole report with IndexError --
    # or resolved to a DIFFERENT span's content, silently substituting unrelated text.
    t = t.replace("\x00", "").replace("\x01", "")
    spans = []

    def stash(kind, text):
        spans.append((kind, text))
        return f"\x00{len(spans) - 1}\x01"

    t = re.sub(r"(`{1,3})(.+?)\1", lambda m: stash("code", m.group(2)), t)
    # `[^\]]+` unbounded made an unclosed `[` rescan almost the whole suffix at every
    # position: 20k bare `[` took 0.68s, ~90 KB of them stalls the report for many seconds.
    # A link label does not span lines and is not thousands of characters long; bounding it
    # makes the scan linear in practice without rejecting any real link.
    t = re.sub(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{stash("raw", m.group(2))}" '
                         f'rel="noopener noreferrer">{m.group(1)}</a>', t)
    # `***x***` resolved as ** then * and emitted `<strong><em>x</strong></em>` -- tags
    # closed in the wrong order, which is invalid HTML, not merely ugly. Handle the
    # three-marker form FIRST so the pair never splits it.
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", t, flags=re.S)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", t)

    def restore(m):
        idx = int(m.group(1))
        if idx >= len(spans):          # unreachable now that input is stripped; belt and braces
            return m.group(0)
        kind, text = spans[idx]
        return f"<code>{text}</code>" if kind == "code" else text

    return re.sub(r"\x00(\d+)\x01", restore, t)


def md(src, _depth=0):
    if not src or _depth > 3:
        return f"<p>{_inline(src or '')}</p>"
    lines = src.split("\n")
    out, para, i, n = [], [], 0, len(lines)

    def flush():
        if para:
            out.append("<p>" + _inline("\n".join(para)).replace("\n", "<br>") + "</p>")
            para.clear()

    while i < n:
        ln = lines[i]
        # The info string was `[\w.+-]*`, so ```` ```{python} ```` / ```` ```console,hl=2 ````
        # (notebook and R-markdown flavours) were not recognised as a fence AT ALL: the code
        # rendered as prose and got `**`-mangled, and the block's CLOSING fence was then read
        # as an OPENER that swallowed everything after it into a <pre>. The review inverts --
        # code as prose, prose as code. Anything that is not a backtick is an info string.
        m = re.match(r"^\s*(`{3,})\s*([^`]*)$", ln)
        if m:
            flush()
            # A closer must be AT LEAST AS LONG as its opener, or a ```` ``` ```` example
            # written inside a 4-backtick fence closes the outer block early, losing the rest
            # of the fence body and emitting a spurious extra block.
            openlen, body, i = len(m.group(1)), [], i + 1
            while i < n and not re.match(r"^\s*`{%d,}\s*$" % openlen, lines[i]):
                body.append(lines[i]); i += 1
            i += 1
            out.append(f'<pre class="code"><code>{html.escape(chr(10).join(body))}</code></pre>')
            continue
        if (re.match(r"^\s*\|.*\|\s*$", ln) and i + 1 < n
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])):
            flush()
            rows = []
            while i < n and re.match(r"^\s*\|", lines[i]):
                rows.append(lines[i]); i += 1
            # Split on pipes that are NOT inside a code span. `| `a|b` | ok |` was split at
            # the pipe inside the backticks, producing a phantom third cell and breaking the
            # code markup across two of them.
            def cells(r):
                # Toggling on EVERY backtick meant a ``double`` span was already "outside"
                # code by the time the pipe arrived, so `| ``a|b`` | ok |` rendered three
                # cells. A span is delimited by a RUN of n backticks and closed by a run of
                # the same length, exactly like a fence.
                txt = r.strip().strip("|")
                parts, buf, run = [], "", 0
                i = 0
                while i < len(txt):
                    ch = txt[i]
                    if ch == "`":
                        rest = txt[i:]
                        n = len(rest) - len(rest.lstrip("`"))
                        if run == 0:
                            run = n
                        elif n == run:
                            run = 0
                        buf += txt[i:i + n]
                        i += n
                        continue
                    if ch == "|" and run == 0:
                        parts.append(buf); buf = ""
                    else:
                        buf += ch
                    i += 1
                parts.append(buf)
                return [c.strip() for c in parts]
            head = "".join(f"<th>{_inline(c)}</th>" for c in cells(rows[0]))
            body = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells(r)) + "</tr>"
                           for r in rows[2:])
            out.append(f'<div class="tw"><table class="md"><thead><tr>{head}</tr></thead>'
                       f'<tbody>{body}</tbody></table></div>')
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            flush()
            lv = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{lv}>{_inline(m.group(2))}</h{lv}>"); i += 1; continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", ln):
            flush(); out.append("<hr>"); i += 1; continue
        if re.match(r"^\s*>\s?", ln):
            flush(); buf = []
            while i < n and re.match(r"^\s*>\s?", lines[i]):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append("<blockquote>" + md("\n".join(buf), _depth + 1) + "</blockquote>")
            continue
        if re.match(r"^\s*([-*+]|\d+[.)])\s+", ln):
            flush()
            items = []
            while i < n and re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
                mm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i])
                items.append([len(mm.group(1)), bool(re.match(r"\d", mm.group(2))),
                              mm.group(3), []])
                i += 1
                # Continuation lines are kept RAW. `+= " " + line.strip()` flattened a
                # fenced code block inside a bullet onto one line -- `- The fix should be:`
                # followed by a ```python block rendered as an inline code span with
                # "python" prepended and every indent gone. Code samples inside bullets are
                # the dominant shape of a code-review rebuttal, so this fired constantly.
                # A blank line does not end the item while a fence is open.
                infence = None
                while i < n:
                    ln2 = lines[i]
                    fm = re.match(r"^\s*(`{3,}|~{3,})", ln2)
                    if infence is None:
                        if not ln2.strip() or not ln2.startswith((" ", "\t")):
                            break
                        if re.match(r"^\s*([-*+]|\d+[.)])\s+", ln2):
                            break
                    if fm:
                        infence = None if infence == fm.group(1)[0] else fm.group(1)[0]
                    items[-1][3].append(ln2)
                    i += 1

            # Depth is CLAMPED rather than trusted. Nesting deeper than this is not
            # meaningful in a review, and unbounded recursion here crashed the whole
            # report (RecursionError at ~1,200 levels) instead of rendering a flat list.
            MAXD = 6
            seen = sorted({it[0] for it in items})
            level = {ind: min(i, MAXD) for i, ind in enumerate(seen)}
            for it in items:
                it[0] = level[it[0]]

            def _item(it):
                """An item whose continuation holds a fence is rendered as MARKDOWN so the
                block survives; anything else keeps the cheap single-paragraph join."""
                cont = it[3]
                if any(re.match(r"^\s*(`{3,}|~{3,})", c) for c in cont):
                    pad = min((len(c) - len(c.lstrip()) for c in cont if c.strip()),
                              default=0)
                    body = "\n".join(c[pad:] for c in cont)
                    return _inline(it[2]) + md(body, _depth + 1)
                return _inline(" ".join([it[2]] + [c.strip() for c in cont if c.strip()]))

            def build(idx, indent):
                tag = "ol" if items[idx][1] else "ul"
                frag = [f"<{tag}>"]
                while idx < len(items) and items[idx][0] >= indent:
                    if items[idx][0] > indent:
                        sub, idx = build(idx, items[idx][0])
                        # The splice assumes the previous fragment is an <li> to nest
                        # into. Entering at the MINIMUM level (below) makes it possible
                        # for the first item to be deeper than the entry indent, where
                        # frag[-1] is still the "<ul>" opener -- slicing 5 chars off that
                        # DESTROYS it. A deeper item with no parent gets its own <li>.
                        if frag[-1].endswith("</li>"):
                            frag[-1] = frag[-1][:-5] + sub + "</li>"
                        else:
                            frag.append(f"<li>{sub}</li>")
                        continue
                    frag.append(f"<li>{_item(items[idx])}</li>")
                    idx += 1
                frag.append(f"</{tag}>")
                return "".join(frag), idx

            # `build(0, items[0][0])` assumed the FIRST item is the shallowest, and threw
            # away the index build() returned. `  - first` / `- second` ranks to levels
            # [1, 0]: the loop exits the moment it meets level 0 and the remainder is
            # DROPPED -- no error, no marker, the review silently loses its concluding
            # bullets. Two judges found this independently. Enter at the minimum level so
            # no item can sit above the entry point, then drain any remainder.
            base = min(it[0] for it in items)
            pieces, idx = [], 0
            while idx < len(items):
                frag, nxt = build(idx, base)
                pieces.append(frag)
                idx = nxt if nxt > idx else idx + 1
            out.append("".join(pieces)); continue
        if not ln.strip():
            flush(); i += 1; continue
        para.append(ln); i += 1
    flush()
    return "".join(out)


def decode_letters(html_text, letters):
    """Annotate anonymous cross-references with the judge they refer to.

    Round two hides identities from the JUDGES, which is the point. The READER is not the
    one being kept honest, and without this every "Reviewer B correctly notes ..." is
    unresolvable. The original wording is preserved; the name is added, never substituted.
    Code and pre blocks are skipped so a literal "Reviewer A" in quoted source is untouched.
    """
    if not letters:
        return html_text

    def annotate(m):
        letter = (m.groupdict().get("rl") or m.groupdict().get("sl")
                  or m.groupdict().get("al") or m.groupdict().get("bare"))
        if letter not in letters:
            return m.group(0)
        return f'{m.group(0)}<span class="decode">{html.escape(letters[letter])}</span>'

    parts = re.split(r"(<(?:code|pre)\b.*?</(?:code|pre)>)", html_text, flags=re.S)
    for i, seg in enumerate(parts):
        if seg.startswith("<code") or seg.startswith("<pre"):
            continue
        # Rewrite TEXT NODES ONLY. Splitting on code/pre alone left every other tag's
        # ATTRIBUTES exposed: `[the patch](https://example.com/pr/-A1)` became
        # `<a href="...-A1<span class="decode">codex</span>">` -- the browser ends href at
        # the inner quote, invents a `decode` attribute and prints `codex</span>"` as loose
        # text beside a broken link. Naming <a> in the skip list would fix this one tag and
        # leave the mechanism for the next; a tag is never a text node, so skip them all.
        bits = re.split(r"(<[^>]*>)", seg)
        for k, b in enumerate(bits):
            if not b.startswith("<"):
                bits[k] = DECODE_RE.sub(annotate, b)
        parts[i] = "".join(bits)
    return "".join(parts)


# ---------------------------------------------------------------- run loading
def find_runs(limit=20, repo=None):
    out = []
    seen = set()
    for root in RUNS_ROOTS:
        if not root.is_dir():
            continue
        for d in root.glob("*/*/"):
            if repo and repo.lower() not in d.parent.name.lower():
                continue
            if d.resolve() in seen:
                continue
            if (d / "panel.md").is_file() or (d / "run.json").is_file():
                seen.add(d.resolve())
                out.append((d.stat().st_mtime, d))
    out.sort(reverse=True)
    return [d for _, d in out[:limit]]


# Module level so the control that asserts this is a WHITELIST can actually reach it.
# It was a local literal inside build(), so `hasattr(pr, "IMG_TYPES")` was always False,
# the image-MIME injection control never executed, and the suite still printed
# "all controls green" -- a control that is on disk and does not run. Three judges caught it.
IMG_TYPES = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
             "webp": "webp", "avif": "avif"}


def _num(x, default=None):
    r"""float() that cannot abort the report. `[\d,.]+` admits `.`, `1.2.3`, `1,2.3.4`,
    and a single malformed heading used to raise ValueError out of load_run() and
    produce NO html at all. A number we cannot read is an absence, not a crash."""
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return default


def load_run(d):
    """Structured view of a run. run.json when present, else parse panel.md."""
    meta, source = {}, "run.json"
    rj = d / "run.json"
    if rj.is_file():
        try:
            meta = json.loads(rj.read_text(encoding="utf-8"))
        except ValueError:
            meta, source = {}, "panel.md (run.json unreadable)"
    else:
        source = "panel.md (this run predates run.json)"

    pm = (d / "panel.md").read_text(encoding="utf-8") if (d / "panel.md").is_file() else ""
    judges = {j["name"]: j for j in meta.get("judges", [])}

    # THE ROSTER IS AUTHORITATIVE FROM THE FILESYSTEM, NOT FROM PROSE.
    # panel.md embeds every review verbatim, so a review that quotes a section
    # heading is indistinguishable from a real one by any pattern -- the panel
    # planted `## fake (`demo`) -- 1.0s, $999` inside a review body and the page
    # rendered a judge named `fake`. A real panel.md is full of judge-written
    # `## ` headings (`## Defect 1: ...`), so tightening the pattern cannot work:
    # container and content share a grammar. A judge cannot be forged by prose
    # because prose cannot create <name>.md.
    roster = {p.name[:-3] for p in d.glob("*.md")}
    roster -= {"panel", "prompt"}
    roster = {n for n in roster
              if not n.endswith((".rebuttal", ".prompt", ".live", ".rebuttal.prompt"))}

    # Fall back to the report's own prose for older runs. Costs and timings live in the
    # per-judge headings: "## codex  (`gpt-5.6-sol`) — 65.0s, 11473 in / 362 out, $0.0047"
    if not judges and pm:
        for m in re.finditer(r"^## ([\w.-]+)\s+\(`([^`]+)`\)\s+—\s+([\d.]+)s(.*)$", pm, re.M):
            name, model, secs, tail = m.groups()
            if name not in roster:      # prose quoting a heading is not a judge
                continue
            if name in judges:
                # The roster gate stops prose INVENTING a judge, but not a real judge's own
                # review re-declaring ITSELF: `codex.md` containing
                # `## codex (\`fake-model\`) — 999.0s, $999` overwrote codex's genuine
                # heading, so the completed judge displayed as fake-model / 999s. The panel's
                # own header is the FIRST occurrence; everything after it is review body.
                continue
            # `[\d,.]+` + strip: the heading parser read `$1,234.56` as `$1` and
            # rendered $1.0000 -- a 1000x understatement. The Cost-section parser
            # below already stripped commas; the two disagreed.
            cost = re.search(r"\$([\d,.]+)", tail)
            toks = re.search(r"([\d,]+) in / ([\d,]+) out", tail)
            judges[name] = {
                "name": name, "model": model, "secs": _num(secs, 0.0), "transport": "?",
                "status": "ok", "meta": {
                    "cost": _num(cost.group(1)) if cost else None,
                    "billing": "subscription" if "plan quota" in tail else None,
                    "tokens": {"input": int(toks.group(1).replace(",", "")),
                               "output": int(toks.group(2).replace(",", ""))} if toks else {}}}
    # Only consult the prose when run.json did not describe the judges. Previously this
    # ran unconditionally and could overwrite a structured cost/billing with a parsed one.
    # Billing lives in the Cost section, not the heading:
    #   - claude-opus: $1.7547 (plan quota), 511.0s, ok
    for m in (re.finditer(r"^\s*-\s+([\w.-]+):\s+(?:\$([\d,.]+)|no cost reported|free)"
                          r"([^\n]*)$", pm, re.M) if not meta.get("judges") else []):
        name, amt, tail = m.group(1), m.group(2), m.group(3)
        if name in judges:
            if "plan quota" in tail:
                judges[name].setdefault("meta", {})["billing"] = "subscription"
            if amt is not None:
                judges[name].setdefault("meta", {})["cost"] = _num(amt)

    # Statuses that panel.md states in prose. Each judge is checked against ITS OWN
    # section only. The previous version ran `^## <name>\b.*?\*\*DID NOT ANSWER` per judge
    # with re.S: the lazy quantifier walked past the section boundary and matched the NEXT
    # judge's failure marker, so every judge listed above the first failure was reported as
    # having not answered. `\b` also let `or-glm` match the heading `or-glm-free`
    # (the boundary sits between "m" and "-"), and the roster ships several such prefix
    # pairs. Split into sections once and match names EXACTLY.
    if not meta.get("judges"):          # never override a status that run.json stated
        # Bound each section by the next JUDGE heading. `(?=\n## |\Z)` stopped at the
        # first heading the judge wrote inside its own review (`## Defect 1: ...`), so
        # the scanned span was whatever prose happened to precede it.
        hdr = re.compile(r"^## (\S+)\s+\(`[^`]+`\)[^\n]*$", re.M)
        marks = [(m.group(1), m.start(), m.end()) for m in hdr.finditer(pm)
                 if m.group(1) in roster]
        sections = {}
        for i, (nm, st, en) in enumerate(marks):
            # First occurrence wins, for the same reason: a heading a judge wrote inside its
            # own review must not replace the section the panel actually emitted, or the
            # status scan reads the forged body instead of the real one.
            sections.setdefault(
                nm, pm[en:(marks[i + 1][1] if i + 1 < len(marks) else len(pm))])
        for name, j in judges.items():
            sec = sections.get(name, "")
            # The marker is written IN PLACE OF the review, so it opens the section.
            # Substring-anywhere marked codex `harness` on a 6,954-byte review whose
            # only offence was describing this bug -- the defect reported itself into
            # existence. A judge's prose may mention any marker; only position tells.
            head = sec.lstrip()
            if head.startswith("**DID NOT ANSWER"):
                j["status"] = "harness"
            elif head.startswith("**PARTIAL") or head.startswith("**INCOMPLETE"):
                j["status"] = "incomplete"
            elif head.startswith("**NO REBUTTAL"):
                j["status"] = j.get("status", "ok")

    # A judge on disk that run.json never mentions is NOT absent from the run -- it is
    # absent from the metadata. A run.json written before the last judge finished (4
    # entries against 5 reviews) rendered a 4-judge page reading `4/4 answered`, with
    # the fifth judge's review, cost and rebuttal simply gone and no warning anywhere.
    # Recover it from the filesystem and say so on the page rather than under-reporting.
    # `source` was stamped "run.json" the moment the file PARSED and never revised, so a
    # run.json of `{}` or `{"judges": []}` produced a page whose every number came from
    # panel.md under a footer asserting the structured source. The docstring's promise --
    # "says which it used" -- was false in exactly the case where it matters.
    if source == "run.json" and not meta.get("judges"):
        source = "panel.md (run.json carried no judges)"

    gap = sorted(roster - set(judges))
    for name in gap:
        judges[name] = {"name": name, "model": "—", "secs": None, "transport": "?",
                        "status": "unlisted", "meta": {}}

    # ONE normalisation for BOTH construction paths. The panel.md fallback always built
    # meta/status/labels; the run.json path did not, so `"secs": null` -- exactly what a
    # serialiser writes for a judge that timed out -- raised TypeError out of build() and
    # wrote NO html at all. Three judges found this. The invariant belongs where the
    # record is made, not at each of the ~12 places that read it.
    for name, j in judges.items():
        j.setdefault("name", name)
        if not isinstance(j.get("meta"), dict):
            j["meta"] = {}
        if not isinstance(j.get("status"), str):
            j["status"] = "unknown"
        if not isinstance(j.get("secs"), (int, float)):
            j["secs"] = None            # absent, NOT 0.0 -- see the bench cell

    for name, j in judges.items():
        j["review"] = (d / f"{name}.md").read_text(encoding="utf-8") if (d / f"{name}.md").is_file() else ""
        rb = d / f"{name}.rebuttal.md"
        j["rebuttal"] = rb.read_text(encoding="utf-8") if rb.is_file() else ""
        j["shown"] = ((d / f"{name}.prompt.md").read_text(encoding="utf-8")
                      if (d / f"{name}.prompt.md").is_file() else "")
        j["family"] = FAMILY.get(name, "—")
        j["labels"] = {k: 0 for k in KINDS}
        for p in scan_positions(j["rebuttal"]):
            j["labels"][p["kind"]] += 1

    # "Reviewer A = codex, Reviewer B = ..." is printed in panel.md; prefer run.json.
    letters = meta.get("letters") or {}
    if not letters:
        leg = re.search(r"Reviewer A = .+$", pm, re.M)
        if leg:
            for pair in leg.group(0).split(","):
                mm = re.match(r"\s*Reviewer ([A-Z]) = ([\w.-]+)", pair)
                if mm:
                    letters[mm.group(1)] = mm.group(2)

    prompt = meta.get("prompt") or ((d / "prompt.md").read_text(encoding="utf-8")
                                    if (d / "prompt.md").is_file() else "")
    # Stop at the next heading or the Cost block: with a bare (.*)$ under re.S this ran to
    # EOF and rendered the Cost section as part of the synthesis prose.
    # Stop at the next H2 only. `#{2,3}` also stopped at any `### ` SUBSECTION of the
    # synthesis, and `\n---\n` stopped at an ordinary horizontal rule -- a synthesis
    # written as "Part one / --- / Part two" silently lost Part two. Three judges
    # raised this independently.
    syn = re.search(r"^## Synthesis \(by `([^`]+)`\)\s*\n(.*?)(?=\n## |\Z)",
                    pm, re.M | re.S)
    return {"dir": d, "source": source, "meta": meta, "judges": judges, "prompt": prompt,
            "letters": letters, "roster_gap": gap,
            "synthesis": (syn.group(1), syn.group(2)) if syn else None, "panel_md": pm}


# Module-level so panel-report-controls binds to THE SHIPPED PATTERN. It used to
# keep its own copy, which meant the control could pass while the real regex
# regressed -- a verification that re-implements what it verifies is an echo.
#
# \s* around the separator is load-bearing: the adjacent-only form matched
# A1/B.10/C#3 and silently dropped or-kimi's "A #1" and "Reviewer A #2", 20 of its
# 25 positions -- an entire judge -- into the ungrouped bucket while the page
# reported confident findings. Measured 0 drift on the 111 lines it already matched.
# A BARE SPACE IS NOT A CITATION. The first widening allowed `[A-Z]\s*\d+`, which
# recovered or-kimi's "A #1" -- and also matched "A 3x speedup", "A 2024 study" and
# "A 5% regression", inventing findings A3x/A2024/A5 out of ordinary prose. Caught by
# the panel. A space is now only allowed where something else marks a citation:
#   Reviewer A 2 / Reviewer A #2   explicit "Reviewer" prefix
#   A #1 / A.1 / A. 1              an actual . or # separator
#   A1                             adjacent, no separator needed
TAG_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:Reviewer\s+(?P<rl>[A-Z])\s*[.#]?\s*(?P<rn>\d+[a-z]?)"
    r"|(?P<sl>[A-Z])\s*[.#]\s*(?P<sn>\d+[a-z]?)"
    r"|(?P<al>[A-Z])(?P<an>\d+[a-z]?))"
    r"\b")


# decode_letters used to inline `(?<![A-Za-z0-9])([A-Z])[.#]?(\\d+[a-z]?)\\b` -- the
# ADJACENT-ONLY, pre-fix pattern. So `Reviewer A #2` was grouped under A2 by claims_of and
# left undecoded in the card: the two halves of the page disagreed about what a citation
# is. Bound to TAG_RE here for the same reason the controls are: a second implementation of
# a pattern is a second thing to forget. The spelled-out form is the LAST alternative so
# "Reviewer A #2" is consumed by the tag branch and never annotated twice.
DECODE_RE = re.compile(TAG_RE.pattern + r"|\bReviewer (?P<bare>[A-Z])\b")


# Judge identity had NO visual anchor: with five judges spread over a bench, ~45 claim
# cards and a tab strip, "who said this" was pure text-reading. Colour is already SPOKEN FOR
# by verdict kind (uphold/reject/concede/missed), which is semantic and must keep it -- so
# judge identity gets a small DOT rather than a fill, and never tints a surface that a
# verdict colour is also describing. Two colour systems on one element would make both
# unreadable.
#
# Hues are spaced around the wheel and chosen by a stable hash of the judge name, so the
# same judge keeps its colour across runs and reports can be compared side by side. Emitted
# as a CSS custom property per judge rather than an inline style, because an inline colour
# cannot answer a `prefers-color-scheme` query -- the dark theme needs a lighter, less
# saturated version of the same hue.
JUDGE_HUES = (210, 25, 190, 330, 265, 45, 150, 300, 15, 235)


def judge_slug(name):
    """A CSS-safe class per judge, unique across DIFFERENT judges.

    Sanitising alone collided: `a-b` and `a.b` both became `a-b`, so both emitted `.j-a-b`,
    the later rule won, and two judges wore one colour while judge_hues had correctly given
    them two. A short digest of the ORIGINAL name keeps distinct judges distinct."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "j"
    return f"{base}-{hashlib.sha256(name.encode()).hexdigest()[:4]}"


def judge_hues(names):
    """Hue per judge, spaced evenly around the wheel for the roster AT HAND.

    A fixed palette picked by hash does not bound how close two picks land: the first
    roster it ran on gave claude-opus 235 and or-glm 210, two blues indistinguishable at
    8px. Identity colour you cannot tell apart is worse than none, because it still looks
    like information. Greedy repair on a 10-hue palette only got the minimum separation to
    40 degrees, and to 25 with eight judges.

    Spacing by roster size is optimal by construction -- five judges land 72 degrees apart,
    eight land 45. The cost is honest and worth stating: a judge's hue depends on WHO ELSE
    is on the panel, so it is stable for a given roster and shifts when the roster changes.
    That is the right trade here, because the dot is a within-page grouping aid and the
    judge's NAME is always printed beside it; nothing depends on recognising a colour
    across two different reports.

    The starting offset is hashed from the roster so different panels do not all open on
    the same blue, and sorted iteration keeps one roster deterministic.
    """
    names = sorted(names)
    if not names:
        return {}
    base = int(hashlib.sha256("\0".join(names).encode()).hexdigest()[:8], 16) % 360
    step = 360 / len(names)
    return {n: int((base + i * step) % 360) for i, n in enumerate(names)}


def judge_dot(name):
    return f'<span class="jdot j-{judge_slug(name)}"></span>'


def tag_of(s):
    """The finding tag in `s`, or None. Callers bind to THIS, not to group indices --
    the pattern has three alternatives and a positional group(1)/group(2) read silently
    returns None for two of them."""
    m = TAG_RE.search(s)
    if not m:
        return None
    letter = m.group("rl") or m.group("sl") or m.group("al")
    num = m.group("rn") or m.group("sn") or m.group("an")
    return f"{letter}{num}"


# Judges number their findings in whatever style they like -- `1. **text**` (codex),
# `## 1. text` (opus), `### 1. **text**` (deepseek). All of them put the number at the
# start of a line, optionally behind heading hashes, so one pattern reads all four.
FINDING_NUM = re.compile(r"^#{0,4}\s*(\d{1,2})[.)]\s+(.+?)\s*$", re.M)


def finding_titles(run):
    """`{"A4": "the text of codex's finding 4"}` for every finding a judge numbered.

    The grouped view headed each block with a bare tag -- `A4 · 2 positions` -- which names
    a finding without saying what it IS. Reading the page meant opening a review tab and
    counting to the fourth item, 38 times. The words are already on disk in the round-one
    reviews; this puts them where the reader is.

    Best-effort by construction: a judge that did not number its findings contributes
    nothing here and its blocks keep the bare tag. That is why the tag is KEPT rather than
    replaced -- the reference has to stay resolvable even when the title is missing.
    """
    out = {}
    for letter, judge in (run.get("letters") or {}).items():
        j = run["judges"].get(judge) or {}
        seen = set()
        # Mask fenced lines FIRST. A reproduction block ("```text\n1. Start two workers")
        # claimed A1 before the real `## 1. **Null dereference...**` heading, and `seen`
        # then discarded the genuine one -- every A1 block was titled "Start two workers".
        _lines = (j.get("review") or "").split("\n")
        _mask = _fence_mask(_lines)
        review = "\n".join("" if _mask[i] else l for i, l in enumerate(_lines))
        for m in FINDING_NUM.finditer(review):
            n = m.group(1)
            if n in seen:                 # the FIRST occurrence is the heading; later ones
                continue                  # are cross-references inside the prose
            seen.add(n)
            raw = m.group(2).strip()
            # Most judges BOLD the finding title and continue with the body on the same
            # line (`1. **Title.** Body...`). Stripping the asterisks first threw that
            # boundary away and the headline ran on into the argument, so take the bold
            # span while it is still there.
            b = re.match(r"\*\*(.+?)\*\*", raw)
            t = b.group(1) if b else raw
            t = re.sub(r"\s+", " ", re.sub(r"[*`]", "", t)).strip()
            if not b:
                # No bold: cut at the first sentence end that is followed by a new one.
                cut = re.search(r"(?<=[.:!?])\s+(?=[A-Z`])", t)
                if cut and cut.start() > 24:
                    t = t[:cut.start()]
            t = t.rstrip(" .;:")
            if len(t) > 110:
                t = t[:109].rsplit(" ", 1)[0] + "\u2026"
            if len(t) > 4:
                out[f"{letter}{n}"] = t
    return out


def claims_of(run):
    letters = run.get("letters") or {}
    out = []
    for name, j in run["judges"].items():
        for p in scan_positions(j["rebuttal"]):
            line, text = p["line"], p["text"]
            # The label may sit INSIDE the bold ("**REJECT — ... .**"), which orphans the
            # CLOSER. Removing the FIRST `**` guessed which marker was unpaired and got it
            # wrong whenever the text carries bold of its own: `**REJECT**: A1 is wrong and
            # **B2** is right.` lost B2's OPENER and rendered a literal `B2**`. Count
            # rather than guess -- an odd number of markers means exactly one is unpaired,
            # and the unpaired one is the LAST.
            # Which marker is orphaned depends on where the label sat. For
            # `**REJECT: x.**` the label opened the bold and the CLOSER is orphaned (last).
            # For `**REJECT A1:** **critical** is not enforced.` the label was ITSELF bolded
            # and closed, so what survives into the text is that closer at the FRONT --
            # removing the last marker there produced `** **critical invariant is not
            # enforced.`, breaking both spans. Position tells which: a text that still opens
            # with `**` is carrying the label's closer.
            if line.lstrip().startswith("**") and text.lstrip().startswith("**"):
                text = text.replace("**", "", 1).lstrip()
            elif text.count("**") % 2:
                cut = text.rfind("**")
                text = text[:cut] + text[cut + 2:]
            # The finding TAG (A1, B.10, A1b) is the grouping key: it names which of the
            # original findings this position is about. Searched over the WHOLE line, not
            # the remainder after the label -- the qualifier group happily consumed a tag
            # sitting BEFORE the separator, so "UPHOLD A1: race confirmed" landed
            # ungrouped, including the exact shape the rebuttal prompt asks judges to use.
            tag = tag_of(line)
            # The LETTER alone still answers "who is being argued with" when there is no
            # number to group by.
            answers = tag[0] if tag else None
            if not answers:
                bare = re.search(r"\bReviewer ([A-Z])\b", text)
                answers = bare.group(1) if bare else None
            out.append({"judge": name, "family": j["family"],
                        "kind": p["kind"], "qual": p["qual"],
                        "answers": answers, "tag": tag, "text": text})
    return out


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Panel — {short}</title>
{webfonts}
<style>
:root{{--paper:#F2F4F1;--surface:#FBFCFA;--sunk:#E6EAE4;--ink:#12161A;--ink-2:#4A5566;--ink-3:#77839A;
 --rule:#CFD6CD;--rule-2:#AEB8AC;--accent:#26405F;--accent-soft:#DDE4E9;
 --uphold:#2E6F5E;--reject:#A33A32;--concede:#8A5D12;--missed:#5E4386;
 --uphold-bg:#E2EFEA;--reject-bg:#F7E5E3;--concede-bg:#F7EDDA;--missed-bg:#ECE6F4;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
 --paper:#0E1113;--surface:#161A1D;--sunk:#0A0C0E;--ink:#E7EAE4;--ink-2:#A6AEA8;--ink-3:#79817C;
 --rule:#262C2E;--rule-2:#39423F;--accent:#9DBBD6;--accent-soft:#1B2429;
 --uphold:#6FC3A8;--reject:#E58C83;--concede:#D9AC5C;--missed:#B49BE0;
 --uphold-bg:#16302A;--reject-bg:#33201E;--concede-bg:#332A18;--missed-bg:#251E33;}}}}
:root[data-theme="dark"]{{--paper:#0E1113;--surface:#161A1D;--sunk:#0A0C0E;--ink:#E7EAE4;
 --ink-2:#A6AEA8;--ink-3:#79817C;--rule:#262C2E;--rule-2:#39423F;--accent:#9DBBD6;
 --accent-soft:#1C2637;--uphold:#6FC3A8;--reject:#E58C83;--concede:#D9AC5C;--missed:#B49BE0;
 --uphold-bg:#16302A;--reject-bg:#33201E;--concede-bg:#332A18;--missed-bg:#251E33;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
 font:16px/1.6 "Public Sans",system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px 80px}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}}
header.mast{{border-bottom:2px solid var(--ink);padding:34px 0 16px;margin-bottom:24px}}
h2.sec::before{{content:'';display:block;width:34px;height:2px;background:var(--ink);
 margin-bottom:10px}}
.eyebrow{{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;
 text-transform:uppercase;color:var(--ink-3)}}
h1{{font-family:Newsreader,Georgia,serif;font-size:clamp(1.5rem,3vw,2.3rem);margin:.22em 0 0;
 font-weight:500;letter-spacing:-.01em;text-wrap:balance;line-height:1.14}}
.facts{{display:flex;flex-wrap:wrap;gap:7px 20px;margin-top:14px;
 font-family:"IBM Plex Mono",monospace;font-size:13px;color:var(--ink-2)}}
.facts b{{color:var(--ink);font-size:1.1em}} .facts .hot b{{color:var(--reject)}}
h2.sec{{font-family:Newsreader,Georgia,serif;font-size:1.3rem;font-weight:600;margin:44px 0 4px}}
.sub{{font-size:.85rem;color:var(--ink-3);margin:0 0 16px}}
.tw{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;font-size:.87rem;min-width:560px}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.11em;
 text-transform:uppercase;color:var(--ink-3);font-weight:500}}
td.n{{font-family:"IBM Plex Mono",monospace}}
table.md{{min-width:340px;width:auto;margin:0 0 .9em}}
table.md th,table.md td{{border:1px solid var(--rule)}}
.pill{{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;
 letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:2px}}
.pill.ok{{background:var(--uphold-bg);color:var(--uphold)}}
.pill.incomplete,.pill.unavailable{{background:var(--concede-bg);color:var(--concede)}}
.pill.harness,.pill.refused{{background:var(--reject-bg);color:var(--reject)}}
.bar{{display:flex;height:5px;border-radius:2px;overflow:hidden;background:var(--sunk);min-width:90px}}
/* Judge identity. A DOT, never a fill: verdict colour already owns every surface in the
   claim cards, and two colour systems on one element make both unreadable. */
.jdot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;
 background:hsl(var(--jh,210) 48% 42%);flex:none;vertical-align:baseline}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) .jdot{{
 background:hsl(var(--jh,210) 58% 64%)}}}}
:root[data-theme="dark"] .jdot{{background:hsl(var(--jh,210) 58% 64%)}}
button .jdot{{margin-right:6px}}
/* At a glance: derived, never model-written. */
.glance{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1px;
 background:var(--rule);border:1px solid var(--rule);border-radius:3px;margin:0 0 8px;
 overflow:hidden}}
.gcell{{background:var(--surface);padding:12px 14px;min-width:0}}
/* the contested cell carries finding TITLES, so it needs the width */
.gcell.wide{{grid-column:span 2}}
@media (max-width:720px){{.gcell.wide{{grid-column:span 1}}}}
.gcell dt{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:10px;
 letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0 0 5px}}
.gcell dd{{margin:0;font-size:.92rem;line-height:1.45}}
.gcell dd b{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:1.15rem;
 font-weight:600;letter-spacing:-.01em}}
.gnote{{font-size:.8rem;color:var(--ink-3);margin:0 0 26px}}
.gtag{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.78rem;
 background:var(--sunk);border:1px solid var(--rule);padding:1px 6px;border-radius:2px;
 margin-right:5px;white-space:nowrap;display:inline-block;margin-bottom:3px}}
.groster{{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center}}
.groster span.r{{display:inline-flex;align-items:center;font-size:.86rem}}
.groster span.r.out{{color:var(--ink-3);text-decoration:line-through}}
.ghot{{display:flex;gap:6px;align-items:baseline;margin-bottom:5px;font-size:.82rem}}
.ghotu{{color:var(--uphold);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.74rem}}
.ghotr{{color:var(--reject);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.74rem}}
.ghott{{color:var(--ink-2);line-height:1.3;min-width:0}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;align-items:center}}
button{{font-family:"IBM Plex Mono",monospace;font-size:.75rem;background:var(--surface);
 color:var(--ink-2);border:1px solid var(--rule);border-radius:2px;padding:6px 12px;cursor:pointer}}
button:hover{{color:var(--ink);border-color:var(--rule-2)}}
button[aria-pressed="true"]{{background:var(--accent);border-color:var(--accent);color:var(--paper)}}
:root[data-theme="dark"] button[aria-pressed="true"]{{color:var(--sunk)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]) button[aria-pressed="true"]{{color:var(--sunk)}}}}
button:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.finding{{border-top:1px solid var(--rule-2);margin:0 0 2px;padding:0 0 6px}}
.finding:first-of-type{{border-top-width:2px;border-top-color:var(--ink)}}
.fhead{{display:flex;align-items:baseline;gap:10px;padding:11px 0 9px;flex-wrap:wrap}}
/* The finding's OWN WORDS are the headline; the tag is demoted to a reference. A block
   headed `A4 · 2 positions` names a finding without saying what it is, which meant opening
   a review tab and counting to the fourth item, 38 times over. */
.ftitle{{font-family:Newsreader,Georgia,serif;font-size:1.04rem;font-weight:500;
 line-height:1.34;flex:1 1 300px;min-width:0;color:var(--ink);text-wrap:balance}}
.fmeta{{display:flex;align-items:center;gap:10px;margin-left:auto;flex:none}}
details.quiet{{margin-top:26px;border-top:1px solid var(--rule);padding-top:4px}}
details.quiet>summary{{cursor:pointer;font-family:"IBM Plex Mono",ui-monospace,monospace;
 font-size:.78rem;color:var(--ink-3);padding:9px 0;list-style:none}}
details.quiet>summary::-webkit-details-marker{{display:none}}
details.quiet>summary::before{{content:'▸ ';color:var(--rule-2)}}
details.quiet[open]>summary::before{{content:'▾ '}}
details.quiet>summary:hover{{color:var(--ink-2)}}
.tag{{font-family:"IBM Plex Mono",monospace;font-size:1rem;font-weight:600;color:var(--ink);
 letter-spacing:.02em;min-width:3.4em}}
.tag.none{{font-size:.78rem;font-weight:400;color:var(--ink-3);letter-spacing:.08em;
 text-transform:uppercase;min-width:0}}
.raiser{{font-family:"IBM Plex Mono",monospace;font-size:.74rem;color:var(--accent);
 background:var(--accent-soft);padding:1px 7px;border-radius:2px}}
.fcount{{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--ink-3)}}
.fbar{{display:flex;height:4px;width:120px;border-radius:2px;overflow:hidden;
 background:var(--sunk);margin-left:auto}}
.fbar i{{display:block}}
.contested{{font-family:"IBM Plex Mono",monospace;font-size:9px;letter-spacing:.14em;
 text-transform:uppercase;color:var(--reject);border:1px solid var(--reject);
 padding:1px 6px;border-radius:2px}}
.fbody{{padding-left:3.4em}}
@media (max-width:640px){{.fbody{{padding-left:0}}}}
.claim{{border-left:2px solid var(--rule);padding:8px 0 8px 14px;margin:0 0 8px}}
.claim.k-uphold{{border-left-color:var(--uphold)}} .claim.k-reject{{border-left-color:var(--reject)}}
.jn{{color:var(--ink-2);font-weight:500}} .fam{{color:var(--ink-3)}}
.claim.k-concede{{border-left-color:var(--concede)}} .claim.k-missed{{border-left-color:var(--missed)}}
.who{{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--ink-3);
 margin-bottom:6px;display:flex;gap:9px;align-items:center;flex-wrap:wrap}}
.decode{{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:.75em;
 color:var(--accent);background:var(--accent-soft);padding:0 5px;border-radius:2px;
 margin-left:4px;vertical-align:1px}}
.arrow{{color:var(--ink-3)}}
.ref{{font-family:"IBM Plex Mono",monospace;color:var(--accent);background:var(--accent-soft);
 padding:1px 6px;border-radius:2px}}
.vl{{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;
 letter-spacing:.1em;padding:2px 7px;border-radius:2px}}
.vl-uphold{{background:var(--uphold-bg);color:var(--uphold)}}
.vl-reject{{background:var(--reject-bg);color:var(--reject)}}
.vl-concede{{background:var(--concede-bg);color:var(--concede)}}
.vl-missed{{background:var(--missed-bg);color:var(--missed)}}
.body{{font-size:.94rem;line-height:1.62}}
.body p,.body li,.body blockquote{{max-width:74ch}}
.body p{{margin:0 0 .7em}} .body ul,.body ol{{margin:0 0 .8em;padding-left:1.35em}}
.body h3,.body h4,.body h5,.body h6{{font-family:"Public Sans",sans-serif;font-weight:600;
 margin:1.1em 0 .4em;font-size:1rem}}
.body blockquote{{margin:0 0 .8em;padding-left:.9em;border-left:3px solid var(--rule-2);color:var(--ink-2)}}
code{{font-family:"IBM Plex Mono",monospace;font-size:.86em;background:var(--sunk);
 padding:.1em .35em;border-radius:2px;word-break:break-word}}
pre.code{{margin:0 0 .85em;padding:11px 13px;background:var(--sunk);border:1px solid var(--rule);
 border-radius:3px;overflow-x:auto;max-height:460px}}
pre.code code{{background:none;padding:0;font-size:.8rem;white-space:pre;display:block}}
a{{color:var(--accent);text-underline-offset:2px}}
.rounds{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
@media (max-width:960px){{.rounds{{grid-template-columns:1fr}}}}
.round{{background:var(--surface);border:1px solid var(--rule);border-radius:3px;overflow:hidden}}
.rhead{{background:var(--sunk);border-bottom:1px solid var(--rule);padding:9px 15px;
 font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.13em;text-transform:uppercase;
 color:var(--ink-2);display:flex;justify-content:space-between;gap:10px}}
.rbody{{padding:16px 18px 20px;max-height:620px;overflow-y:auto}}
figure.shot{{margin:0 0 14px;padding:0}}
figure.shot img{{max-width:100%;height:auto;display:block;border:1px solid var(--rule);border-radius:3px}}
details.ask{{background:var(--surface);border:1px solid var(--rule);border-radius:3px;padding:12px 15px}}
details.ask summary{{cursor:pointer;font-size:.85rem;color:var(--ink-2)}}
.empty{{color:var(--ink-3);font-style:italic}}
.hide{{display:none!important}}
footer{{margin-top:52px;padding-top:16px;border-top:1px solid var(--rule);
 font-size:.78rem;color:var(--ink-3)}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
{judge_css}
</style></head><body><div class="wrap">
<header class="mast">
  <div class="eyebrow">llm-panel · {when}{effort}{rebut}</div>
  <h1>{short}</h1>
  <div class="facts">
    <span><b>{n_fam}</b> {famword}</span>
    <span><b>{tok_in}</b> in / <b>{tok_out}</b> out{tok_partial}</span>
  </div>
</header>

{glance}

<h2 class="sec">The question</h2>
<p class="sub">{shownnote}</p>
<details class="ask"><summary>{qlen} characters — click to read in full</summary>
<div class="body">{question}</div></details>

{images}

<h2 class="sec">The bench</h2>
<p class="sub">One judge per vendor is the point: a panel drawn from one family shares its blind spots.</p>
<div class="tw"><table><thead><tr><th>judge</th><th>family</th><th>model</th><th>status</th>
<th>time</th><th>tokens</th><th>cost</th><th>cited</th><th>round 2</th></tr></thead><tbody>{bench}</tbody></table></div>

{claims_sec}

<h2 class="sec">Full reviews</h2>
<p class="sub">Round one is independent — no judge saw another's review. Nothing is summarised away.</p>
<div class="controls" id="tabs">{tabs}</div>
<div class="rounds">
  <div class="round"><div class="rhead"><span>Round 1 · independent</span><span id="m1" class="mono"></span></div>
    <div class="rbody body" id="r1"></div></div>
  <div class="round"><div class="rhead"><span>Round 2 · rebuttal</span><span id="m2" class="mono"></span></div>
    <div class="rbody body" id="r2"></div></div>
</div>

{synthesis}

{gapnote}
<footer>{dirline}<br>Structured data read from <code>{source}</code>. Every review is
reproduced in full and unedited; judges that failed or were cut off are marked, not dropped.</footer>
</div>
<script id="jd" type="application/json">{judges_json}</script>
<script>
const J=JSON.parse(document.getElementById('jd').textContent);
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let sel=0;
const tabs=document.getElementById('tabs');
function paint(){{
  const j=J[sel];
  $('#r1').innerHTML=j.review||'<p class="empty">No round-one review was recorded.</p>';
  $('#r2').innerHTML=j.rebuttal||'<p class="empty">This judge did not take part in the rebuttal round.</p>';
  $('#m1').textContent=j.b1?j.b1.toLocaleString()+' B':'—';
  $('#m2').textContent=j.b2?j.b2.toLocaleString()+' B':'—';
  tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',+b.dataset.i===sel));
}}
tabs.addEventListener('click',e=>{{const b=e.target.closest('button');if(!b)return;sel=+b.dataset.i;paint();}});
paint();
const cf=document.getElementById('cfilters');
if(cf){{
  let active=cf.dataset.start||'ALL';
  const draw=()=>{{
    $$('.claim').forEach(c=>c.classList.toggle('hide',active!=='ALL'&&c.dataset.kind!==active));
    // A claim folded inside a closed <details> is in the DOM but not on screen; counting it
    // as "shown" would make the number disagree with what the reader can see.
    $$('.finding').forEach(f=>f.classList.toggle('hide',
        !f.querySelector('.claim:not(.hide)')));
    cf.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.k===active));
    const n=$$('.claim:not(.hide)').filter(c=>!c.closest('details:not([open])')).length;
    $('#ccount').textContent=n+' shown';
  }};
  cf.addEventListener('click',e=>{{const b=e.target.closest('button');if(!b)return;active=b.dataset.k;draw();}});
  // draw() ran only on load and on a filter click, so opening a folded section revealed
  // claims the counter had already decided not to count and the number went stale.
  $$('details.quiet').forEach(d=>d.addEventListener('toggle',draw));
  draw();
}}
</script></body></html>"""


def build(run, opts):
    esc = html.escape
    js = list(run["judges"].values())
    js.sort(key=lambda j: (j["status"] != "ok", j["name"]))
    billed = sum((j["meta"].get("cost") or 0) for j in js
                 if j["meta"].get("billing") != "subscription")
    quota = sum((j["meta"].get("cost") or 0) for j in js
                if j["meta"].get("billing") == "subscription")
    tin = sum((j["meta"].get("tokens") or {}).get("input", 0) for j in js)
    tout = sum((j["meta"].get("tokens") or {}).get("output", 0) for j in js)
    n_tok = sum(1 for j in js if (j["meta"].get("tokens") or {}).get("input")
                or (j["meta"].get("tokens") or {}).get("output"))
    part_tok = n_tok and n_tok < len(js)
    ok = [j for j in js if j["status"] == "ok"]
    fails = [j for j in js if j["status"] != "ok"]

    # Per-judge citation coverage. This column exists because the grouping FAILED
    # SILENTLY: or-kimi cited every position and the extractor understood none of them,
    # so 25 positions sank into the untagged bucket while the page announced 55 confident
    # findings. A grouping that cannot say how much it grouped is an instrument that
    # cannot report what it is trusted for. A judge at 0/N is now a visible fact.
    cited = {}
    for c in claims_of(run):
        t = cited.setdefault(c["judge"], [0, 0])
        t[1] += 1
        if c.get("tag"):
            t[0] += 1

    # Did round two actually happen? Taken from ANY judge having positions rather than
    # from the run.json flag alone: older runs predate the flag, and a judge that returned
    # a stub must not be excused by a missing field.
    # `run["rebut"]` DOES NOT EXIST -- load_run puts it in `run["meta"]`, so this test was
    # always False and a rebuttal round that produced no parseable positions was reported as
    # "This run had no rebuttal round" while the masthead simultaneously said "rebuttal".
    had_round = bool(run["meta"].get("rebut")) or any(n for _, n in cited.values())

    bench = []
    for j in js:
        tk = j["meta"].get("tokens") or {}
        cost = j["meta"].get("cost")
        # `cost is None` means NO COST WAS RECORDED, yet the cell printed the literal
        # word "subscription" -- asserting a billing mode nobody observed. A local judge
        # and codex both land here and were both reported as spending plan quota. Five of
        # five judges raised this. An absence renders as an absence, exactly as `toks`
        # already does. `cost == 0` with billing=subscription kept its marker too; it
        # used to print a bare "free" and drop the classification.
        sv = j.get("secs")
        secs_cell = f"{sv:.1f}s" if isinstance(sv, (int, float)) else "—"
        qmark = " *" if j["meta"].get("billing") == "subscription" else ""
        money = ("—" if cost is None else ("free" + qmark) if not cost
                 else f"${cost:.4f}{qmark}")
        tot = sum(j["labels"].values())
        # codex reports no token counts at all; printing "0/0" states a measurement that
        # was never taken. An absence should look like an absence.
        toks = (f'{tk.get("input", 0):,}/{tk.get("output", 0):,}'
                if (tk.get("input") or tk.get("output")) else "—")
        colours = {"UPHOLD": "var(--uphold)", "REJECT": "var(--reject)",
                   "CONCEDE": "var(--concede)", "MISSED": "var(--missed)"}
        bar = ("".join(f'<i style="width:{j["labels"][k] / tot * 100:.1f}%;'
                       f'background:{colours[k]}"></i>' for k in KINDS if j["labels"][k])
               if tot else "")
        counts = " ".join(f"{k[:1]}{j['labels'][k]}" for k in KINDS if j["labels"][k]) or "—"
        bench.append(
            f'<tr><td class="n">{judge_dot(j["name"])}{esc(j["name"])}</td>'
            f'<td>{esc(j["family"])}</td>'
            f'<td class="n" style="font-size:.8rem">{esc(j.get("model") or "—")}</td>'
            # The one interpolation in build() that skipped esc(). A status with a space
            # ("no rebuttal") silently became three CSS classes; a quote broke the tag.
            f'<td><span class="pill {esc(str(j["status"]).split()[0] if j["status"] else "unknown")}">'
            f'{esc(str(j["status"]))}</span></td>'
            # `.get("secs", 0)` guards a MISSING key, not a null value: `"secs": null`
            # raised TypeError and wrote no html at all. Absent time is "—", not 0.0s,
            # for the same reason an absent cost is.
            f'<td class="n">{secs_cell}</td>'
            f'<td class="n">{toks}</td>'
            f'<td class="n">{money}</td>'
            + (lambda g, n: '<td class="n" style="color:var(--ink-3)">—</td>' if not n
               else f'<td class="n" title="positions that named which finding they answer"'
                    f'{"" if g else " style=color:var(--reject)"}>{g}/{n}</td>')(
                       *cited.get(j["name"], [0, 0]))
            # With no rebuttal round there is nothing to chart; an empty bar plus a dash
            # renders as a stray artifact rather than as "not applicable".
            #
            # But "—" must NOT be reused for a judge that WAS asked to rebut and returned
            # nothing usable. or-kimi once answered a rebuttal round with a single
            # sentence -- "I'll verify the load-bearing claims before taking positions" --
            # and stopped: 206 bytes, zero positions, status `ok`. Rendered as "—" that is
            # indistinguishable from a run with no round two at all, which is precisely the
            # confusion this table exists to prevent. Silence from a judge that was asked
            # is a RESULT, not a blank.
            + (f'<td><div class="bar">{bar}</div><span class="mono" '
               f'style="font-size:.68rem;color:var(--ink-3)">{counts}</span></td></tr>'
               if tot else
               '<td class="n" style="color:var(--reject)" title="this judge was asked to '
               'rebut and produced no positions">no positions</td></tr>'
               if had_round else '<td class="n" style="color:var(--ink-3)">—</td></tr>'))

    claims = claims_of(run)
    ordered = []
    if claims:
        counts = {k: sum(1 for c in claims if c["kind"] == k) for k in KINDS}
        # GROUP BY FINDING, not by judge. A position is an answer to one of the original
        # findings; listing them per judge scatters the argument about a single defect
        # across five places. Most-contested first: the findings people actually fought
        # over are the ones worth adjudicating.
        groups = {}
        for c in claims:
            groups.setdefault(c.get("tag") or "\u2014", []).append(c)
        ordered = sorted(groups.items(),
                         key=lambda kv: (kv[0] == "\u2014", -len(kv[1]), kv[0]))

        def card(c):
            return (
                f'<div class="claim k-{c["kind"].lower()}" data-kind="{c["kind"]}">'
                f'<div class="who"><span class="vl vl-{c["kind"].lower()}">{c["kind"]}'
                f'{" " + esc(c["qual"]) if c["qual"] else ""}</span>'
                f'<span class="jn">{judge_dot(c["judge"])}{esc(c["judge"])}</span>'
                f'<span class="fam">{esc(c["family"])}</span></div>'
                f'<div class="body">{decode_letters(_inline(c["text"]), run["letters"])}</div>'
                f'</div>')

        titles = finding_titles(run)
        blocks, quiet = [], []
        for tag, cs in ordered:
            mix = {k: sum(1 for c in cs if c["kind"] == k) for k in KINDS}
            colours = {"UPHOLD": "var(--uphold)", "REJECT": "var(--reject)",
                       "CONCEDE": "var(--concede)", "MISSED": "var(--missed)"}
            bar = "".join(f'<i style="width:{mix[k] / len(cs) * 100:.1f}%;'
                          f'background:{colours[k]}"></i>' for k in KINDS if mix[k])
            raiser = run["letters"].get(tag[0], "") if tag != "\u2014" else ""
            # DESCRIPTIVE only. "contested" means both uphold and reject are present -- it
            # is not a verdict, and no survived/killed is computed: the panel itself ruled
            # that turning positions into a tally manufactures a vote over incommensurable
            # essays. The mix is shown; the reader adjudicates.
            contested = ' <span class="contested">contested</span>' if mix["UPHOLD"] and mix["REJECT"] else ""
            title = titles.get(tag, "") if tag != "\u2014" else ""
            label = (f'<span class="tag">{esc(tag)}</span>'
                     + (f'<span class="raiser">{esc(raiser)}</span>' if raiser else "")
                     + (f'<span class="ftitle">{esc(title)}</span>' if title else "")
                     ) if tag != "\u2014" else (
                         # Named for what it IS. "no finding cited" invited the reading that
                         # these were stray remarks; they are ordinary positions whose author
                         # described the finding instead of referencing it, so they cannot be
                         # grouped -- and this is routinely the LARGEST block on the page.
                         '<span class="tag none">ungrouped &mdash; described, '
                         'not referenced</span>')
            block = (
                f'<section class="finding" data-tag="{esc(tag)}">'
                f'<header class="fhead">{label}'
                f'<span class="fmeta">'
                f'<span class="fcount">{len(cs)} position{"s" if len(cs) != 1 else ""}</span>'
                f'<span class="fbar">{bar}</span>{contested}</span></header>'
                f'<div class="fbody">{"".join(card(c) for c in cs)}</div></section>')
            # A finding one judge raised and nobody answered is a different KIND of thing
            # from one two judges argued over, and on this corpus the first outnumbers the
            # second four to one (31 vs 7). Given equal weight they bury it. Argued findings
            # stay open; the rest fold away, still present and still filterable.
            (blocks if len(cs) > 1 or tag == "\u2014" else quiet).append(block)

        start = "ALL"
        btns = "".join(f'<button data-k="{k}">{k} · {counts[k]}</button>' for k in KINDS)
        claims_sec = (
            '<h2 class="sec">The findings, and what happened to them</h2>'
            f'<p class="sub">{len(blocks)} finding{"s" if len(blocks) != 1 else ""} drew '
            f'more than one position, most-contested first; each block gathers every '
            f'position taken on that finding. &ldquo;Contested&rdquo; marks disagreement, '
            f'not a verdict &mdash; a concession may be evidence or deference, and only '
            f'reading it tells you which.</p>'
            f'<div class="controls" id="cfilters" data-start="{start}">{btns}'
            f'<button data-k="ALL">all · {len(claims)}</button>'
            f'<span class="mono" id="ccount"></span></div>'
            + "".join(blocks)
            + (f'<details class="quiet"><summary>{len(quiet)} finding'
               f'{"s" if len(quiet) != 1 else ""} drew exactly one position &mdash; nobody '
               f'argued the other side</summary>{"".join(quiet)}</details>'
               if quiet else ""))
    else:
        claims_sec = ('<h2 class="sec">The findings</h2><p class="sub">This run had no '
                      'rebuttal round — re-run with <code>--rebut</code> to have judges answer '
                      "each other's findings.</p>")

    imgs, dropped = "", []
    for i, path in enumerate(run["meta"].get("images") or []):
        p = pathlib.Path(path)
        # A relative path used to resolve against panel-report's CWD, so the same run
        # rendered differently depending on where it was invoked from -- silently dropping
        # the image, or embedding a same-named file from an unrelated directory. The run
        # directory is the only meaningful base.
        if not p.is_absolute():
            p = run["dir"] / p
        if not p.is_file():
            dropped.append((path, "not found")); continue
        kb = p.stat().st_size / 1024
        if kb > opts.max_image_kb:
            dropped.append((path, f"{kb:.0f} KB exceeds --max-image-kb {opts.max_image_kb}"))
            continue
        import base64
        b = base64.b64encode(p.read_bytes()).decode()
        # Whitelist, never interpolate: the subtype used to come straight from the
        # filename, so `shot.p" onerror="alert(1)` closed the src attribute.
        ext = p.suffix.lower().lstrip(".")
        mt = IMG_TYPES.get(ext)
        if mt is None:
            # `.get(ext, "png")` served a BMP/TIFF/SVG as image/png: a silently broken
            # <img> rather than a diagnosable one. Say what it was.
            dropped.append((path, f"unsupported image type {ext or '(none)'}")); continue
        imgs += (f'<figure class="shot"><img alt="image {i + 1} shown to the judges" '
                 f'src="data:image/{mt};base64,{b}"></figure>')
    # An image the judges WERE shown but the report could not embed must not vanish: with
    # every image dropped the whole section disappeared and the page read as a run with no
    # images at all, leaving every `unavailable` verdict unexplainable.
    if dropped:
        imgs += ('<p class="sub" style="color:var(--reject)">'
                 + esc(f"{len(dropped)} image(s) shown to the judges could not be embedded: ")
                 + "; ".join(esc(f"{pathlib.Path(n).name} ({why})") for n, why in dropped)
                 + "</p>")
    images = (f'<h2 class="sec">What the judges were shown</h2>'
              f'<p class="sub">Only vision-capable judges received these; the rest reported '
              f'<code>unavailable</code> rather than answering blind.</p>{imgs}') if imgs else ""

    syn = ""
    if run["synthesis"]:
        who, text = run["synthesis"]
        syn = (f'<h2 class="sec">Synthesis</h2><p class="sub">Written by <code>{esc(who)}</code>. '
               f'It sits below the full reviews on purpose — it is an additional opinion, not a '
               f'replacement for them.</p><div class="body">{md(text)}</div>')

    L = run.get("letters") or {}
    payload = [{"name": j["name"],
                "review": decode_letters(md(j["review"]), L),
                "rebuttal": decode_letters(md(j["rebuttal"]), L),
                # CHARACTER counts were displayed with the unit "B". One `é` reported 1 B
                # against a 2-byte file; an emoji 1 B against 4. Measure what the label says.
                "b1": len((j["review"] or "").encode("utf-8")),
                "b2": len((j["rebuttal"] or "").encode("utf-8"))} for j in js]
    tabs = "".join(f'<button data-i="{i}">{judge_dot(j["name"])}{esc(j["name"])}</button>'
                   for i, j in enumerate(js))
    q = run["prompt"] or ""
    first = (q.strip().splitlines() or ["(no prompt recorded)"])[0]
    short = first if len(first) <= 90 else first[:89].rsplit(" ", 1)[0] + "…"
    # AT A GLANCE. Every number here is DERIVED from the run -- none of it is written by a
    # model. That is deliberate and is the same rule the consensus table follows: asking a
    # model to summarise the panel puts a thirteenth opinion between the reader and the
    # twelve, and it is the step most likely to quietly drop a minority finding. What a
    # reader cannot get by scanning is the SHAPE of the round -- how much was contested,
    # what could not be grouped, and which findings drew a real split -- so that is what
    # this computes and nothing more.
    n_pos = len(claims)
    contested = [(t, cs) for t, cs in ordered if t != "\u2014"
                 and any(c["kind"] == "UPHOLD" for c in cs)
                 and any(c["kind"] == "REJECT" for c in cs)]
    ungrouped = sum(len(cs) for t, cs in ordered if t == "\u2014")
    n_findings = sum(1 for t, _ in ordered if t != "\u2014")
    # Name the contested findings by what they SAY, not by tag. "C1 · 1u/1r" is a label a
    # reader has to go and resolve; the title is the thing they actually wanted.
    _titles = finding_titles(run) if claims else {}
    hot = "".join(
        f'<div class="ghot"><span class="gtag">{esc(t)}</span>'
        f'<span class="ghotu">{sum(1 for c in cs if c["kind"] == "UPHOLD")}u</span>'
        f'<span class="ghotr">{sum(1 for c in cs if c["kind"] == "REJECT")}r</span>'
        f'<span class="ghott">{esc(_titles.get(t, ""))}</span></div>'
        for t, cs in contested[:5])
    roster = "".join(
        f'<span class="r{"" if j["status"] == "ok" else " out"}" '
        f'title="{esc(j["status"])}">{judge_dot(j["name"])}{esc(j["name"])}</span>'
        for j in js)
    phases = (run["meta"].get("phases") or {})
    phase_bits = [p for p in ("rebuttal", "synthesis") if phases.get(p)]
    dead = [j for j in fails if j["status"] not in ("incomplete", "unlisted")]
    # `unlisted` means run.json never mentioned this judge and it was recovered from disk.
    # That is a METADATA gap, not evidence the judge was cut off -- its complete review is
    # rendered in the tab while the summary said "1 answered but was cut off".
    part = [j for j in fails if j["status"] == "incomplete"]
    unlisted = [j for j in fails if j["status"] == "unlisted"]
    why = ("".join([f'<div style="margin-top:6px;font-size:.8rem;color:var(--reject)">'
                    f'{len(dead)} did not answer</div>'] if dead else [])
           + "".join([f'<div style="margin-top:4px;font-size:.8rem;color:var(--concede)">'
                      f'{len(part)} answered but was cut off</div>'] if part else [])
           + "".join([f'<div style="margin-top:4px;font-size:.8rem;color:var(--ink-3)">'
                      f'{len(unlisted)} recovered from disk, absent from run.json</div>']
                     if unlisted else []))
    cells = [("the panel", f'<b>{len(ok)}</b> of {len(js)} answered{why}'
              f'<div class="groster" style="margin-top:8px">{roster}</div>')]
    if claims:
        cells += [("round two", f'<b>{n_pos}</b> positions on <b>{n_findings}</b> findings'),
                  ("contested", (f'<b>{len(contested)}</b> drew both an uphold and a reject'
                                 f'<div style="margin-top:7px">{hot}</div>') if contested
                   else "<b>0</b> findings drew a split")]
        if ungrouped:
            cells.append(("not grouped",
                          f'<b>{ungrouped}</b> position{"s" if ungrouped != 1 else ""} '
                          f'described a finding instead of citing it, so nothing could be '
                          f'matched to them'))
    # A run with a rebuttal round but NO per-phase record predates the fix that counted
    # round two, so its figure is round-one spend only. Measured live on two runs, the
    # rebuttal came to 63% and 65% of the total -- it ships every review to every judge, so
    # it routinely costs MORE than round one. That makes the number a FLOOR, and a floor
    # printed as a total is the same defect as calling an absence zero. Derivable, so said.
    # A panel.md-only run has no `meta.rebut` at all, so keying the caveat on that flag hid
    # it from exactly the runs that predate per-phase accounting. Rebuttal FILES on disk are
    # the evidence a second round happened, whatever the metadata says.
    _rebutted = bool(run["meta"].get("rebut")) or any(
        (j.get("rebuttal") or "").strip() for j in run["judges"].values())
    floor = _rebutted and not phase_bits
    cells.append(("spend", f'<b>${billed:.4f}</b> billed'
                  + (f' &middot; ${quota:.4f} quota' if quota else "")
                  + (f'<div style="margin-top:7px;font-size:.8rem;color:var(--ink-3)">'
                     f'over round 1 + {" + ".join(phase_bits)}</div>' if phase_bits else "")
                  + ('<div style="margin-top:7px;font-size:.8rem;color:var(--concede)">'
                     'round one only &mdash; this run predates per-phase accounting, and the '
                     'rebuttal round typically costs more than round one, so treat this as a '
                     'floor</div>' if floor else "")))
    glance = ('<div class="glance">'
              + "".join(f'<div class="gcell{" wide" if t == "contested" and hot else ""}">'
                        f'<dt>{t}</dt><dd>{v}</dd></div>' for t, v in cells)
              + "</div><p class="
              + '"gnote">Counted from the run, not written by a model: a summary is one more '
                'opinion, and the one most likely to drop a minority finding.</p>')
    _hues = judge_hues([j["name"] for j in js])
    judge_css = "\n".join(f".j-{judge_slug(n)}{{--jh:{h}}}" for n, h in _hues.items())

    m = run["meta"]
    return TEMPLATE.format(
        glance=glance, judge_css=judge_css,
        short=esc(short), when=esc(m.get("when") or run["dir"].name),
        effort=f" · effort {esc(m['effort'])}" if m.get("effort") else "",
        rebut=" · rebuttal" if m.get("rebut") else "",
        tok_partial=(f' <span class="hot">({n_tok} of {len(js)} judges reported)</span>'
                     if part_tok else ""),
        n_ok=len(ok), n_all=len(js), n_fam=len({j["family"] for j in js} - {"—"}),
        famword="family" if len({j["family"] for j in js} - {"—"}) == 1 else "families",
        billed=f"{billed:.4f}", quota=f"{quota:.4f}",
        # Missing counts summed to 0 and printed "0 in / 0 out" as though measured; a run
        # where only some judges report was presented as a complete total. codex reports no
        # counts at all, so this fires on every panel it sits on.
        tok_in=f"{tin:,}" if n_tok else "—", tok_out=f"{tout:,}" if n_tok else "—",
        failnote=(lambda dead, part: "".join(
            ([f'<span class="hot"><b>{len(dead)}</b> did not answer</span>'] if dead else [])
            + ([f'<span class="hot"><b>{len(part)}</b> answered but was cut off</span>']
               if part else [])))(
            [j for j in fails if j["status"] not in ("incomplete", "unlisted")],
            [j for j in fails if j["status"] in ("incomplete", "unlisted")]),
        qlen=f"{len(q):,}", question=md(q),
        images=images, bench="".join(bench), claims_sec=claims_sec, tabs=tabs,
        synthesis=syn, judges_json=json.dumps(payload).replace("</", "<\\/"),
        # "Exactly what every judge was shown" was false whenever a rebuttal round ran:
        # each judge additionally saw the other reviews. The per-judge prompts that would
        # make the claim checkable are read into j["shown"] and then never used -- codex
        # and or-kimi both noticed the page asserts something it discarded the evidence for.
        shownnote=("This is the round-one prompt. Judges that rebutted were additionally "
                   "shown the other reviews, so it is not the whole of what they saw."
                   if any((j.get("rebuttal") or "").strip() for j in run["judges"].values())
                   or any((j.get("shown") or "") != run["prompt"]
                          for j in run["judges"].values())
                   else "Exactly what every judge was shown."),
        gapnote=('<p class="sub" style="color:var(--reject)">'
                 + esc(f'{len(run["roster_gap"])} judge(s) present in the run directory but '
                       f'absent from run.json, recovered from disk: '
                       + ", ".join(run["roster_gap"]))
                 + "</p>") if run.get("roster_gap") else "",
        # The page called itself "self-contained" while issuing three requests to
        # fonts.googleapis.com/gstatic on open -- so viewing a report about private source
        # code announced it to a third party, and offline it rendered in fallback fonts
        # anyway. Two judges raised it. Default to no external requests; --webfonts opts in.
        webfonts=('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                  'family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;'
                  '1,6..72,400&family=Public+Sans:wght@400;500;600&'
                  'family=IBM+Plex+Mono:wght@400;500;600&display=swap">'
                  if getattr(opts, "webfonts", False) else
                  '<!-- no external requests: this page is about private code. --webfonts opts in. -->'),
        dirline=esc(str(run["dir"])), source=esc(run["source"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rundir", nargs="?", help="run directory (default: most recent)")
    ap.add_argument("--list", action="store_true", help="list recent runs and exit")
    ap.add_argument("--repo", help="only consider runs whose repo key contains this")
    ap.add_argument("--out", help="output html path")
    ap.add_argument("--open", action="store_true", help="open it in a Windows browser (WSL)")
    ap.add_argument("--webfonts", action="store_true",
                    help="load Newsreader/Public Sans/IBM Plex Mono from Google Fonts. Off "
                         "by default: a report about private code should not announce "
                         "itself to a third party the moment it is opened.")
    ap.add_argument("--max-image-kb", type=int, default=1500)
    a = ap.parse_args()

    if a.list:
        # Counts only -- do NOT call load_run(), which reads every judge's review, rebuttal
        # and prompt file just to print a number. That is an I/O storm on a large cache.
        for d in find_runs(20, a.repo):
            rj = d / "run.json"
            if rj.is_file():
                try:
                    m = json.loads(rj.read_text(encoding="utf-8"))
                    when, n = m.get("when") or d.name[:15], len(m.get("judges", []))
                except ValueError:
                    when, n = d.name[:15], "?"
            else:
                pm = (d / "panel.md")
                head = pm.read_text(encoding="utf-8")[:400] if pm.is_file() else ""
                first = head.split("\n")[0].replace("# Panel — ", "").strip()
                jl = re.search(r"^Judges: (.+)$", head, re.M)
                when = first or d.name[:15]
                n = len(jl.group(1).split(",")) if jl else "?"
            print(f"{when:<28} {n} judges  {d.parent.name:<26} {d}")
        return 0

    d = pathlib.Path(a.rundir).expanduser() if a.rundir else (find_runs(1, a.repo) or [None])[0]
    if d is None:
        sys.exit(f"no panel runs found under {RUNS}")
    if not d.is_dir():
        sys.exit(f"not a directory: {d}")
    run = load_run(d)
    if not run["judges"]:
        sys.exit(f"no judges found in {d} — is this a panel run directory?")

    out = pathlib.Path(a.out).expanduser() if a.out else \
        pathlib.Path.home() / "reports" / f"panel-{d.parent.name}-{d.name[:15]}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(run, a), encoding="utf-8")
    print(f"{out}  ({out.stat().st_size / 1024:.0f} KB, {len(run['judges'])} judges, "
          f"{len(claims_of(run))} round-2 positions)")

    if a.open:
        dl = pathlib.Path("/mnt/c/Users/user/Downloads")
        if not dl.is_dir():
            print(f"--open: {dl} not found; open {out} yourself", file=sys.stderr)
            return 0
        shutil.copy2(out, dl / out.name)
        win = f"C:\\Users\\user\\Downloads\\{out.name}"
        for exe, label in [
            (r"/mnt/c/Program Files/Mozilla Firefox/firefox.exe", "Firefox"),
            (r"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe", "Chrome"),
            (r"/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "Edge")]:
            if pathlib.Path(exe).is_file():
                # Opens a TAB in the running instance. Never kill the browser to refresh.
                subprocess.Popen([exe, win], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"opened in {label}: {win}")
                return 0
        print("no known browser found; open it yourself:", win, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
