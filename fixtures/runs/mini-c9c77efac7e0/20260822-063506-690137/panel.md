# Panel — 2026-08-22 06:46:10 EDT

Judges: codex, codex~2, claude-opus, claude-opus~2

| judge | status | time | tokens | cost |
|---|---|---|---|---|
| codex | ok | 648.2s | — | — |
| codex~2 | ok | 621.2s | — | — |
| claude-opus | ok | 640.4s | 204,559/47,948 | $2.2948 * |
| claude-opus~2 | ok | 663.5s | 79,555/47,859 | $1.8014 * |

`*` = charged against a subscription plan, not invoiced.


## Question

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



---

## codex  (`gpt-5.6-sol`) — 648.2s

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


---

## codex~2  (`gpt-5.6-sol`) — 621.2s

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


---

## claude-opus  (`opus`) — 640.4s, 204559 in / 47948 out, $2.2948

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

## claude-opus~2  (`opus`) — 663.5s, 79555 in / 47859 out, $1.8014

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


---

### Cost

- billed: **$0.0000** (4 of 8 judges reported, and reported zero)
- on subscription plans (notional, no invoice): $7.9253
- tokens: 1,100,766 in / 157,905 out across 4 judges, over 2 phases (round 1, rebuttal)

  - by phase: round 1 $0.0000 billed / $4.0962 quota; rebuttal $0.0000 billed / $3.8291 quota

  - codex: no cost reported, 648.2s, ok
  - codex~2: no cost reported, 621.2s, ok
  - claude-opus: $2.2948 (plan quota), 640.4s, ok
  - claude-opus~2: $1.8014 (plan quota), 663.5s, ok

**4 of 4 judges answered.**

---

## Rebuttal round

Round 1 above is untouched. Here each judge answers the others' findings, having been shown them anonymously.

Legend (withheld from the judges, shown to you): Reviewer C = codex, Reviewer D = codex~2, Reviewer B = claude-opus, Reviewer A = claude-opus~2


### codex (Reviewer C) responds — 293.8s

I’m reopening the complete source and tracing each overlapping reviewer claim against the actual control flow. I’ll answer only with the required verdict lines and concrete code evidence.
The overlap is now mostly settled. One important disagreement is concrete: both slug clearances missed an actual same-base/same-16-bit-prefix pair; I verified the two SHA-256 prefixes directly. I’m finishing the remaining source boundaries before giving the verdicts.
MISSED: A1 — A finding-first verdict table never puts a verdict at `LABEL`’s start offset, so valid table positions disappear. The verdict-first partial-match variant also demonstrably misassigns table cells to `qual` and `text`.

UPHOLD: A2 — `claims_sec` branches solely on `if claims`; neither `had_round`, `meta.rebut`, nor rebuttal-file presence prevents the false “no rebuttal round” message.

UPHOLD: A3 — `tag_of()` never validates the captured letter against `run["letters"]`; `REJECT: this is a P0 concern` therefore creates a phantom P0 finding and counts it as cited.

MISSED: A4 — `md()` recognizes only backtick fences. A `~~~python` block reaches `_inline()`, whose `~~…~~` rule renders most of it as strikethrough prose.

UPHOLD: A5 — This is another execution of the bold-repair defect. Here the label’s closer is the first surviving marker, but `rfind()` deletes the final legitimate closer and pairs unrelated spans.

MISSED: A6 — Continuation lines are preserved in `c["text"]`, but `card()` sends them only through `_inline()`. HTML collapses their newlines, leaving lists and fenced samples as run-on literal markup.

MISSED: A7 — The bold-span heuristic extracts `Critical` instead of the actual title from `**Critical:** …`. The short-first-sentence case also bypasses the sentence cut solely because `cut.start() <= 24`.

MISSED: A8 — With a truthy synthesis phase but no rebuttal phase, `phase_bits` is nonempty, so a present rebuttal file cannot trigger `floor`; the page falsely labels the spend as covering “round 1 + synthesis” without warning that round two is missing.

MISSED: A9 — The em-dash bucket is forced into `blocks`, and `len(blocks)` is then called a count of findings drawing multiple positions. One ungrouped position alone produces the false count of one such finding.

MISSED: A10 — `_fence_mask()` accepts a fence prefix without validating the rest of the line. A line beginning with an inline triple-backtick span opens a phantom fence and can invert masking across the following real fence.

MISSED: A11 — The verified first branch is sufficient: a roster-backed failed-judge heading without `N.Ns` is seen by `hdr` but not by the judge constructor, then added only after status scanning as `unlisted`.

UPHOLD: A12 — `unlisted` remains outside `ok` and receives the `.out` class, so a complete recovered review is excluded from “answered” and struck through.

REJECT: A13 — An unterminated Markdown fence semantically extends to EOF. `_fence_mask()` and `md()` consistently treat the tail as code; absorbing that code into the position which introduced it is not a separate misclassification.

MISSED: A14 — `cells()` does not recognize `\|`; it splits at the escaped pipe, adding a cell and shifting later columns.

REJECT: A15 — `JUDGE_HUES` is unused, but that produces no incorrect output because `judge_hues()` supplies every emitted hue independently.

UPHOLD: A16 — The `judge_slug` clearance is disproved by `a.___b` and `a__---b`: both normalize to `a-b`, and both SHA-256 digests begin `1da7`. Both emit `a-b-1da7`, so the later CSS rule controls both dots.

UPHOLD: B1 — With list markup, `line.lstrip()` still begins with `-`, so the front-marker branch is skipped and `rfind()` removes a legitimate final marker.

UPHOLD: B2 — Parser silence is not evidence that round two did not occur; the empty-claims branch ignores both the metadata flag and visible rebuttal files.

UPHOLD: B3 — `status == "ok"` is used as a proxy for answering, although `unlisted` records are recovered precisely because their answer file exists.

MISSED: B4 — The ungrouped bucket increments `len(blocks)` despite not being a finding, making the section’s multi-position-finding count false.

UPHOLD: B5 — `## Defect 1:` cannot match `FINDING_NUM`. A subsequent ordinary numbered reproduction list consequently supplies A1/A2 titles before any recognizable finding headings.

MISSED: B6 — The absorber preserves multiline content, but card rendering neither parses Markdown nor converts newlines. Fence markers and code `**` can additionally participate in `_inline()`’s emphasis matching.

MISSED: B7 — Any truthy recorded phase suppresses `floor`, even when a rebuttal demonstrably ran but has no phase record. The provenance claim is therefore incomplete.

REJECT: B8 — `len(contested)` remains exact, and the five rendered entries are not described as an exhaustive enumeration. The cap alone does not make a displayed number or stated property false.

UPHOLD: B9 — The slug clearance overlooks a real 16-bit collision: `a.___b` and `a__---b` both produce `a-b-1da7`.

UPHOLD: D1 — `sum(cost or 0)` converts unknown non-subscription costs to zero, so an all-null run reports an exact `$0.0000 billed`, and mixed data appears complete.

MISSED: D2 — The synthesis search is unscoped and selects the first matching heading anywhere in `panel.md`; judge prose can therefore replace the genuine synthesis. Its next-H2 terminator also truncates a genuine synthesis at `## Risks`.

UPHOLD: D3 — Four-space-indented Markdown code is unmasked, while `MARKUP` consumes its indentation; the sample verdict becomes a real position.

UPHOLD: D4 — `_fence_mask()` treats a matching delimiter prefix plus an info suffix as a closer, although `md()` requires a whitespace-only closing line. The enclosed sample verdict is consequently counted.

MISSED: D5 — After `- ` is consumed, `[x]` remains before the verdict. `LABEL.match()` starts at `[`, fails, and drops the task-list position from every derived total.

UPHOLD: D6 — A true rebuttal flag plus prose-only rebuttal still reaches the empty-claims message claiming no round occurred.

MISSED: D7 — One untagged position creates the mutually incompatible “1 finding drew more than one position” and “1 positions on 0 findings.”

UPHOLD: D8 — The numerator excludes both a nonempty incomplete answer and a complete recovered `unlisted` answer, despite the adjacent text acknowledging each answer.

UPHOLD: D9 — `seen` makes the ordinary preamble’s first `1.` permanent, so the later genuine `## 1.` title cannot replace it.

UPHOLD: D10 — The bullet prevents the position-aware repair branch from running; the last legitimate marker is deleted and `critical` loses its intended emphasis.

UPHOLD: D11 — The supplied names normalize identically and share the verified digest prefix `1da7`; the duplicate selector makes both judges use the later hue.


### codex~2 (Reviewer D) responds — 313.6s

I’ll re-trace each overlap against the actual source, including any reviewer finding that is the same mechanism as one of mine or directly disproves it.
MISSED: A1 — A verdict-first table row without a colon or dash cannot satisfy `LABEL`; a row containing a later colon instead misuses the intervening cells as `qual`. Thus present rebuttal positions can become zero positions or malformed cards.

UPHOLD: A2 — `claims_sec` depends only on `claims`. With `meta.rebut = true` and a prose-only rebuttal, `claims` is empty while `had_round` is true, producing both “no positions” and “no rebuttal round.”

MISSED: A3 — `tag_of()` never validates the matched letter against `run["letters"]`. With only reviewers A/B, `REJECT: this is a P0 concern` creates a phantom P0 finding and inflates `n_findings`.

MISSED: A4 — `md()` recognizes only backtick fences. A `~~~python` block reaches `_inline()`, where the paired tildes become `<del>` and its code is rendered as prose.

MISSED: A5 — The bold repair also fails without list markup. In `**REJECT: A1 is wrong.** But **B2** stands.`, the orphan is the first marker remaining in `text`, but `rfind()` removes B2’s legitimate closer.

MISSED: A6 — Continuation lines are deliberately absorbed with newlines, but `card()` passes them only through `_inline()`. Lists collapse into literal hyphenated prose, and fenced code loses block structure and indentation.

MISSED: A7 — For `## 1. **Critical:** null dereference`, the first bold span is only a severity label, yet it becomes the finding title “Critical.” The short-first-sentence guard also leaves short titles joined to their argument.

MISSED: A8 — With rebuttal files present and `phases={"synthesis": ...}`, `phase_bits` is nonempty, so `floor` is false even though rebuttal spend is unaccounted. The page presents round-one-plus-synthesis spend without the missing-rebuttal caveat.

UPHOLD: A9 — The em-dash bucket is forced into `blocks`, and `len(blocks)` is then labelled as a number of multi-position findings. One ungrouped position alone therefore produces “1 finding drew more than one position.”

MISSED: A10 — `_fence_mask()` accepts any line beginning with three delimiters as a fence boundary. An inline `````REJECT``` is …`` line opens a phantom fence and can invert masking around the next real fence.

MISSED: A11 — The verified first branch is sufficient: a legacy failed-judge heading without `N.Ns` is visible to the status scanner but never enters `judges`; the later filesystem recovery labels it `unlisted`, so its explicit failure status is lost.

UPHOLD: A12 — `unlisted` records are excluded by `status == "ok"` and receive the `.out` class. A complete recovered review is therefore counted as unanswered and struck through despite being rendered.

REJECT: A13 — An unterminated fence semantically extends to EOF. Lines after it, including apparent headings or verdicts, remain code in `md()` as well; treating them as later positions would be the false-positive behavior.

REJECT: A15 — An unused constant produces no incorrect report behavior. `judge_hues()` intentionally computes roster-spaced hues independently; dead `JUDGE_HUES` is not itself a user-visible defect.

UPHOLD: B1 — For the bulleted examples, `line.lstrip()` begins with `-`, so the front-marker branch is unreachable. The odd-parity fallback removes the final legitimate marker exactly as claimed.

UPHOLD: B2 — The blockquote example is intentionally excluded as a position, but that does not rescue the section text: `meta.rebut`, nonempty rebuttal files, and visible round-two tabs still prove a round occurred while `claims_sec` says otherwise.

UPHOLD: B3 — `len(ok)` excludes `unlisted`, although that status means only “missing from metadata.” The displayed complete review and struck-through “unanswered” roster entry directly contradict one another.

UPHOLD: B4 — `tag == "—"` places the bucket in `blocks` regardless of cardinality, after which `len(blocks)` is described as a count of findings with multiple positions.

UPHOLD: B5 — `## Defect 1:` cannot match `FINDING_NUM`. Its numbered reproduction steps do match, and first-occurrence-wins permanently assigns those steps to A1/A2.

MISSED: B6 — The absorbed fence contributes both newlines and `**kw` to `c["text"]`; `_inline()` can then pair the label’s orphaned marker across the code sample while collapsing the entire block into flowed text.

MISSED: B7 — A truthy synthesis phase suppresses `floor` even when rebuttal files prove that an unrecorded rebuttal phase ran. Falsy recorded phase values also generate the opposite, false provenance claim.

MISSED: B8 — With nine contested findings, the derived count says nine while the adjacent apparent enumeration silently stops at five. There is no truncation marker identifying the four omitted entries.

MISSED: C1 — The roster gate does not stop one real judge from forging another real judge’s heading. Because both metadata extraction and `sections.setdefault()` take the first beta heading, alpha’s embedded beta header can replace beta’s genuine metadata and status section.

MISSED: C2 — `{"judges": null}` reaches a comprehension over `None` before normalization. The valid `panel.md` fallback is therefore bypassed by a `TypeError`.

UPHOLD: C4 — `cost=None` renders as absent in the bench but contributes zero to `billed`. One unknown cost yields a falsely exact `$0.0000`; mixed known/unknown costs yield an unlabeled subtotal.

UPHOLD: C5 — `meta.rebut=true` makes the masthead and bench recognize round two, but empty `claims` independently selects the literal “no rebuttal round” branch.

UPHOLD: C6 — An incomplete nonempty review is excluded from `len(ok)` while `why` calls it “answered but was cut off.” `unlisted` complete reviews suffer the same exclusion and strike-through.

UPHOLD: C7 — Four-space-indented code is not masked, and `MARKUP` consumes its indentation. `REJECT A7:` inside that code consequently becomes a real position.

UPHOLD: C8 — `_fence_mask()` treats `````python`` as a closer despite its suffix, whereas `md()` requires a whitespace-only closing line. The following fenced sample is therefore tallied as rebuttal prose.

MISSED: C9 — `C3` is accepted without checking that reviewer C exists. The technical identifier becomes a cited finding and falsely improves citation coverage.

UPHOLD: C10 — An early reproduction list claims number 1 before the genuine `## 1.` heading; `seen` then discards the correct title.

MISSED: C11 — `tag_of()` returns only the first `TAG_RE.search()` match. `UPHOLD A1 and B2:` therefore creates one A1 card and leaves B2 absent from grouping and finding counts.

MISSED: C12 — `head.startswith("**INCOMPLETE")` has no marker boundary. A complete review beginning `**INCOMPLETE handling …**` is misclassified as cut off and excluded from “answered.”

UPHOLD: C13 — The list prefix prevents the front-orphan branch, so the last legitimate bold marker is removed and “Critical” loses its intended emphasis.

UPHOLD: C14 — Both names sanitize to `a-b`, and both SHA-256 prefixes are demonstrably `1da7`; each emits `a-b-1da7`. The duplicate CSS selector makes the later hue rule govern both judges.


### claude-opus (Reviewer B) responds — 462.6s

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


### claude-opus~2 (Reviewer A) responds — 398.1s

Positions below are grounded in a fresh read of the full source in `.llm-panel-material/material-bd56dbc187dd.md` (I re-traced every line I cite; I have no execution tool in this session, so where a claim rests on measurement rather than control flow I say so).

---

## Things they caught that I did not

**MISSED: D2** — the synthesis parse is unscoped and runs on *every* run, not just legacy ones. `syn = re.search(r"^## Synthesis \(by `([^`]+)`\)\s*\n(.*?)(?=\n## |\Z)", pm, re.M|re.S)` is a bare `re.search` over the whole of panel.md, and panel.md embeds every review verbatim *above* the real synthesis. So the first occurrence wins and a judge that quotes that header line — in a corpus of judges reviewing this very tool, a near-certainty — supplies both `who` (rendered as `Written by <code>attacker</code>`) and the body, and the genuine synthesis is never reached. This is not covered by the fixed item "panel.md prose forging a judge": that gate is `if name not in roster: continue`, and there is no roster equivalent for the synthesis author — `who` is interpolated straight from the backtick group. The second half is live too: the lookahead is `(?=\n## )`, so a synthesis containing `## Risks` silently loses everything from that line on. The comment says they narrowed from `#{2,3}` to `## ` deliberately to stop cutting at `### ` subsections, but that trade leaves H2 subsections cutting the essay, and the fixed item ("synthesis truncated at `---`") only removed the horizontal-rule terminator. I did not examine the synthesis path at all.

**MISSED: C1** — the first-occurrence-wins defence protects a judge against forging *itself* and leaves cross-forgery open. `if name in judges: continue` and `sections.setdefault(...)` both mean the earliest heading wins, and the comment justifies that with "The panel's own header is the FIRST occurrence; everything after it is review body" — true only when the forged heading is *below* the real one, i.e. self-forgery. `alpha.md` containing `## beta (\`fake-model\`) — 999.0s, $999` sits above beta's genuine section in the concatenation, passes the roster gate because `beta.md` exists, wins the fallback `finditer`, wins `sections.setdefault`, and `head.startswith("**DID NOT ANSWER")` then sets `status="harness"` — while beta's real review is read from `beta.md` and rendered in the tab. Legacy-only (both loops are gated on `not meta.get("judges")`), which is the one thing that caps its severity below D2.

**MISSED: C4 / D1** — `billed = sum((j["meta"].get("cost") or 0) for j in js if ...)`. The fix for exactly this class was applied to tokens thirty lines away — `tok_in=f"{tin:,}" if n_tok else "—"` plus the `part_tok` "(n of N judges reported)" marker — and not to cost. With every `cost` null the bench correctly prints `—` per row and the glance prints `$0.0000 billed`; with one known and one null it prints the known subtotal as the run's spend, with no analogue of `part_tok`. The already-fixed items cover the *bench cell* ("cost None as `subscription`") and *tokens* ("token totals as measured zero"), not this. This is the same class as my #8 — a derived number asserted as measured — and it is the cleaner instance of it. I checked the bench cell and did not follow `billed` up into the glance.

**MISSED: B5 / C10 / D9** — `FINDING_NUM = r"^#{0,4}\s*(\d{1,2})[.)]\s+(.+?)\s*$"` requires the digit to be the first token after the hashes, so `## Defect 1: ...` cannot match (`#{0,4}` then `\s*` then `\d` hits `D`). The file's *own* comment in `load_run` names that shape as what the corpus contains: "A real panel.md is full of judge-written `## ` headings (`## Defect 1: ...`)". The fence mask removed the fenced instance of the steal; an ordinary unfenced numbered list — a repro list, a preamble checklist — still matches first, `seen` makes it final, and the title propagates to both the block headline and the contested glance cell via `_titles.get(t, "")`. B5's input is the strongest form because the same file documents the heading grammar the pattern can't read. My #7 found two *mis-titles* inside the bold/no-bold branches; I never questioned whether `FINDING_NUM` matches the corpus's dominant heading form at all.

**MISSED: C8 / D4** — `_fence_mask` closes on any line whose *prefix* is a long-enough run of the same character: `re.match(r"^\s*(?:>\s?)*\s*(`{3,}|~{3,})", ln)` has no `$` anchor and no `[^`]*` info-string guard, while `md()`'s closer is `^\s*`{openlen,}\s*$`. So a nested ` ```python ` inside an open fence closes the mask but not the render: `md()` keeps the block as code, `scan_positions` scans it, and a `REJECT A1:` sample line becomes a real card. Confirmed against both patterns. This is the same root as my #10 (which is the *opening* direction: ` ```REJECT``` is a tag I never wrote` opens a phantom fence because of the same two missing guards). Worth flagging: **Reviewer B cleared this exact function** — "Traced ```` closing ```, ``` failing to close ````, and ~~~ vs ```. No finding." — and that clearance traced only the character/length rule, which is the part that is correct. Two of the three defects in `_fence_mask` live in the part that clearance never examined: what counts as a fence *line*.

**MISSED: C3** — the quadratic link scan is only half-fixed. The bound landed on the label (`[^\]\n]{1,300}`) and not on the URL (`[^)\s]+`). On `"[x](https://a" * 8000` the input contains no `)` and no whitespace, so at each of the ~8000 `[` starts the engine matches `https://` and then runs `[^)\s]+` to end-of-string before failing on `\)` and backtracking one character at a time — an O(remaining) failure scan per start position, so O(n²) overall. I traced the control flow; I did not reproduce their 6.1s measurement and have no execution tool here, so I endorse the mechanism and not the number.

**MISSED: C2** — `judges = {j["name"]: j for j in meta.get("judges", [])}` is the one place in the file that reads a run.json value without an `or` default. Every sibling read is null-safe (`meta.get("letters") or {}`, `meta.get("images") or []`, `meta.get("phases") or {}`, and `meta.get("judges")` used as a truthiness test at three later sites). `{"judges": null}` therefore raises `TypeError: 'NoneType' is not iterable` out of `load_run` before the panel.md fallback can run — a crash where the file's own doctrine is "A number we cannot read is an absence, not a crash". The input shape is hypothetical rather than observed, but the asymmetry against every other read in the same function is what makes it an oversight rather than a design choice.

**MISSED: C7 / D3** — a four-space-indented code block is not masked (`_fence_mask` knows only ` ``` ` and `~~~`), and `MARKUP`'s trailing `\s*` consumes the indentation with zero repetitions of the bullet group, so `label_at` finds the verdict at offset 4 and a sample line becomes a card, a scoreboard increment, a filter count and a citation-coverage numerator. Severity is below the fenced case because `md()` also lacks indented-code support, so the *rendered* review shows the same text as prose — the page is at least self-consistent about what it thinks the text is. The fabricated position is still fabricated.

**MISSED: B1 / C13 / D10** — the bold-repair selector reads `line.lstrip().startswith("**")`, which is false for every list-prefixed line even though `MARKUP` was specifically written so those lines *do* produce positions. Traced B1's Input B: `- **REJECT A1:** **critical** is not enforced.` → `MARKUP.match` ends at 4, `LABEL` consumes through the `:`, `text = "** **critical** is not enforced."`, `line.lstrip()[0] == '-'` so the position branch is skipped, `text.count("**") == 3` is odd, `rfind` removes the closer after "critical", and `_inline` emits `<strong> </strong>critical is not enforced.` — verbatim the output the in-code comment claims the position test prevents. My #5 is the same defect reached from the other side (`**REJECT: A1 is wrong.** The \`foo\` path **never** runs.` at column 0, where `line` starts with `**` but `text` does not), so the class is broader than either input alone: the guard fails whenever the label's bold *closes* inside the line, with or without a bullet. One correction to B1's proposed mechanism — testing at `MARKUP.match(line).end()` would not fix its own Input B, since `MARKUP` consumes the `- **` and what remains starts with `REJECT`, not `**`. The defect stands; that particular repair does not.

**MISSED: D5** — `MARKUP` is still an enumerated set (`[-*+]`, `\d+[.)]`, `\|`) under a comment asserting "A LIST OF NAMES CANNOT GUARD AN OPEN SET". `- [x] **UPHOLD A1:** confirmed` ends the repeat group at offset 2 (`[` matches no alternative), `\**` matches nothing because the next char is `[`, and `LABEL.match(line, 2)` fails against `[x] **UPHOLD...`. The position vanishes from the cards, the tally, `cited`, the filter totals and every derived glance number. Same root as my #1 (where the survivor is the `[:—–]` separator requirement rather than the markup set), and together they show the structural strip closed one end of the open set and left the other two.

**MISSED: C11** — `tag_of` returns `TAG_RE.search`'s leftmost match only, so `UPHOLD A1 and B2: both describe the same loss of data.` is filed under A1 and B2's block never shows that someone upheld it. Low severity — one key per position is the data model — but the page's headline feature is "each block gathers **every** position taken on that finding", and for a multi-cited position that sentence is false.

**MISSED: C12** — `head.startswith("**INCOMPLETE")` on `sec.lstrip()`. The move from substring-anywhere to position-anchored fixed the "defect reported itself into existence" case; it does not survive a legacy review whose *first* bold span opens with the marker word, e.g. `**INCOMPLETE handling of null costs is the critical defect.**`. That judge gets `status="incomplete"`, the amber pill, exclusion from `ok`, and a line through its name in the roster. Narrow (legacy runs only, and it needs the marker word in first position), but reachable, and it compounds directly with B3/C6/D8 below.

**MISSED: B8** — `hot` is built from `contested[:5]` while the cell prints `len(contested)`. Nine contested findings render as "**9** drew both an uphold and a reject" above five titles with no truncation marker, so the count and the enumeration answer the same question differently. Low severity as they say; it is the same "no silent caps" class as the rest of the glance.

---

## Where I stand by my own finding

**UPHOLD: B2** (and **UPHOLD: C5**, **UPHOLD: D6**) — same defect as my #2, and B2's secondary point sharpens it correctly: `had_round = bool(run["meta"].get("rebut")) or any(n for _, n in cited.values())` and `_rebutted = bool(run["meta"].get("rebut")) or any((j.get("rebuttal") or "").strip() ...)` are two different definitions of "did round two happen" in one function, and the file-based one is the correct evidence. The `claims_sec` else-branch consults neither — it is keyed on `if claims:` alone — so zero parsed positions prints "This run had no rebuttal round — re-run with `--rebut`" against a masthead reading `· rebuttal`, a bench full of red `no positions` cells whose `title` says "this judge **was asked** to rebut", and a `shownnote` (file-based, so correct) saying judges were shown the other reviews. Every input above that produces a whole-judge parse miss — B2's blockquoted rebuttals, my table-shaped ones, D5's task lists — reaches it.

**UPHOLD: B3** (and **UPHOLD: C6**, **UPHOLD: D8**) — my #12. `ok = [j for j in js if j["status"] == "ok"]` is the numerator, and `unlisted` is assigned purely from `roster - set(judges)`, a metadata gap; the judge's review, rebuttal, positions, cost and tab are all rendered. So the glance headline denies what the page below it displays, and `f'<span class="r{"" if j["status"] == "ok" else " out"}"'` with `.groster span.r.out{text-decoration:line-through}` strikes the name through beside the note saying it was recovered intact. On the `incomplete` half that C6 and D8 add: weaker, since a truncated answer arguably is not a full answer — but "**1** of 2 answered" printed directly above "1 answered but was cut off" is a contradiction on the face of one cell, so I take it as real at lower severity.

**UPHOLD: B4** (and **UPHOLD: D7**) — my #9. `(blocks if len(cs) > 1 or tag == "\u2014" else quiet)` puts the bucket in `blocks` unconditionally, and `len(blocks)` is then reported as the count of findings that drew more than one position. B4's arithmetic checks out: A1×3, A2×1, B1×1 plus 6 ungrouped gives `blocks == [A1, "—"]` → "2 findings drew more than one position" when one did, against `n_findings == 3` in the glance from the same data. D7's degenerate input is the sharper one — a single untagged position yields "1 finding drew more than one position" in the section head and "**1** positions on **0** findings" in the glance, two sentences that cannot both be about the same run.

**UPHOLD: B6** — my #6, and B6 is the more complete trace: `card()` calls `decode_letters(_inline(c["text"]), …)` with no `md()`, no `<br>` and no fence handling, while `scan_positions`'s absorber appends fenced lines unconditionally (the break tests sit inside `if not fenced[k]`) after `.strip()`ing each one. I re-checked its three sub-claims and all three hold: on `- **REJECT: A2.** The signature is:` + a fenced `def f(a, **kw)` block, `text.count("**")` is 2 (the label's orphaned closer plus `**kw`), so the parity repair does *not* fire and code content is voting in the emphasis arithmetic; `` (`{1,3})(.+?)\1 `` backtracks to a single-backtick match inside the ` ```python ` line, emitting a `<code>`-wrapped backtick followed by loose `python`; and `\*\*(.+?)\*\*` under `re.S` then pairs `A2.**` with `**kw` across the whole block. The same rebuttal renders correctly in the round-2 tab, which goes through `md()`.

**UPHOLD: B7** — my #8, both halves. `phase_bits = [p for p in ("rebuttal", "synthesis") if phases.get(p)]` then `floor = _rebutted and not phase_bits` asks whether *any* phase is recorded, not whether the *rebuttal* is, so a `phases` carrying only `synthesis` prints "over round 1 + synthesis" with no caveat while omitting the round the comment above measures at 63–65% of spend; and because the test is truthiness, a recorded rebuttal phase of `0`/`0.0`/`{}` (an all-subscription round two, or a serialiser writing an empty object for a no-cost phase) makes the page assert "this run predates per-phase accounting" about a run that has it. The cell that exists to prevent a false provenance claim makes one.

**UPHOLD: C9** — my #3. `TAG_RE`'s third alternative is bare `[A-Z]\d+[a-z]?` and `tag_of`'s letter is never checked against `run["letters"]`, which `claims_of` holds in the same scope. C9's `REJECT: C3 linearization…` on an A/B-only panel confirms: `(?<![A-Za-z0-9])` is satisfied by the preceding space, `\b` by the following one, so the position is grouped under a phantom finding `C3` with an empty `raiser` and empty title, `n_findings` gains one, and the position is stolen from the "ungrouped — described, not referenced" bucket, which is the one place the page reports its own grouping failures.

---

## Where I think they are wrong

**REJECT: C14** (and **REJECT: D11**) — the sanitisation half is right and the load-bearing half is unverifiable. `a.___b` and `a__---b` both collapse to `a-b` under `re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")` — I traced that and it holds. But the finding only becomes a defect if `sha256(b"a.___b").hexdigest()[:4] == sha256(b"a__---b").hexdigest()[:4] == "1da7"`, and that is asserted with no derivation. No language model can compute SHA-256 by inspection, and I have no execution tool in this session to check it either — so I can neither confirm it nor let it stand as verified. That two "independent" reviewers produced the identical exotic name pair *and* the identical four hex digits is itself evidence of convergent confabulation rather than of two independent computations agreeing. What I traced when I cleared this: a collision now requires the sanitised base *and* the 16-bit digest prefix to agree, both judge names come from `d.glob("*.md")` filenames, and for a real five-to-ten-name roster the birthday probability is ~n²/131072, i.e. negligible. The honest residual, which neither finding states: 16 bits is a *probabilistic* guarantee, so `judge_slug`'s docstring claim of a class "unique across DIFFERENT judges" is stronger than the code delivers. That is a docstring overstatement, not the demonstrated collision C14 and D11 present.

---

## Unchanged from my own list, untouched by anyone

Nobody addressed my #4 (`~~~` fences unhandled in `md()` — `re.match(r"^\s*(`{3,})\s*([^`]*)$", ln)` is backtick-only while `_fence_mask` and the list-continuation absorber both recognise `~{3,}`, so a tilde-fenced block lands in `para` and `~~([^~]+)~~` renders it struck through), #11 (the fallback judge parser requires `([\d.]+)s` while the status scanner does not, so a legacy `## or-kimi (\`kimi-k2\`) — **DID NOT ANSWER**` heading never enters `judges`, falls to `roster_gap`, and is labelled `unlisted`/"absent from run.json" on a run with no run.json), or the unterminated-fence tail-swallow in `scan_positions`'s absorber. I still hold all three.


**Positions taken** (labels the judges used; a concession may be evidence OR deference — read the text to tell which):

- codex: uphold 18, reject 3, missed 15
- codex~2: uphold 16, reject 2, missed 17
- claude-opus: uphold 14, reject 4, concede 3, missed 20
- claude-opus~2: uphold 6, reject 1, missed 13