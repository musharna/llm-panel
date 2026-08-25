#!/usr/bin/env python3
"""Span-grounded claim extraction: one instrument, shared by the grader and the renderer.

WHY THIS EXISTS
---------------
Two places independently guessed where one judge's finding ended and the next began:
`blocks_of()` in recall/panel-recall (splitting reviews to score them) and `claims_of()`
in panel-report (parsing rebuttal positions to render them). Neither knew what the other
had decided, and both were regexes over arbitrary model Markdown. The failures were not
theoretical:

  * A bold line alone at column 0 matched none of the three header patterns, so two
    reviews counted as ZERO findings -- and were scored as abstentions IN THE EXPERIMENT
    MEASURING ABSTENTION.
  * `\\s` matched a newline, so a `## Reproduction` heading paired with the next line's
    `1. Run it` and swallowed it.
  * Symbol-and-description matching that was not local to one finding credited a judge
    for a defect it never reported, by combining two correct findings about other things.

The lesson from all three is the same: THE MEASUREMENT BOUNDARY WAS A GUESS, and a
different guess in each consumer. This module makes it one guess, versioned, and testable.

WHAT IT DOES AND DOES NOT DO
----------------------------
It ATOMIZES what a judge said. It does not decide whether any of it is TRUE, and it does
not cluster equivalent claims -- those are separate steps with separate failure modes, and
fusing them is how a parser starts adjudicating.

The raw prose stays authoritative. Every observation carries byte offsets into the original
text, so anything downstream can go back and read what was actually written. Crucially,
material the extractor could not attribute to any finding is REPORTED as `unextracted`,
never dropped: an extraction failure must be visible as "I could not parse this", because
the alternative is that it silently becomes "the judge found nothing" -- which is exactly
the bug that corrupted the abstention experiment.

IDENTITY
--------
Two ids, deliberately separate:
  observation_id  immutable: judge + run + span. Survives re-clustering.
  cluster_id      versioned: the current semantic grouping. May change; must never be the
                  thing provenance hangs off.
"""

import hashlib
import re

EXTRACTOR_VERSION = "1"

# The union of every finding-header form this project has been burned by, each earned.
# Order matters only for readability; the scan takes the leftmost match of any of them.
#
#   1.  / 1)            numbered, the common case
#   ## / ### / ####     a Markdown heading
#   - ** / * ** / + **  a bolded bullet
#   **text**            a bold line ALONE at the margin -- the form whose absence scored
#                       two real reviews as abstentions
#   #### **text**       heading and bold together
#
# [ \t] never \s: `\s` matches a newline, which is how a heading swallowed the following
# line and reported its content as the heading's own.
FINDING_START = re.compile(
    r"""^(?:
          [ \t]{0,3}\d{1,2}[.)][ \t]+            # 1.  /  1)
        | [ \t]{0,3}\#{1,4}[ \t]+                # ## heading
        | [ \t]{0,3}[-*+][ \t]+\*\*              # - **bold bullet
        | [ \t]{0,3}\*\*[^\n*][^\n]*\*\*[ \t]*$  # **a bold line alone**
      )""",
    re.M | re.X,
)

# A bold BULLET is a finding only when bullets are the document's TOP LEVEL.
#
# Why this exists: asked for file and line, a judge answered in exactly the shape the
# prompt requested --
#     **Defect 1: `windows_os()` is undefined**
#     - **File:** `src/.../MigrateMakeCommand.php`
#     - **Line:** 114
#     - **Failure scenario:** ...
# -- and the bullet rule tore one finding into four, so the path landed in one observation
# and the line in another and they never co-occurred. The matcher needs both, so a
# correctly-formatted review scored zero. The same locality defect as the `detected()` bug,
# reproduced inside the instrument built to remove it.
#
# The obvious fix -- "a bold span ending in ':' is an attribute label" -- was MEASURED
# against 376 bold bullets in 351 real reviews and REFUTED: colon-terminated spans include
# real findings (`High — \`Index.summarise\`:`), and non-colon spans include real attribute
# labels (`Function`, `Defect`, `Concrete failure scenario`). Neither side is clean, which
# is the open-set failure this project keeps hitting. A vocabulary of labels would not have
# worked either.
#
# What DOES separate them is HIERARCHY, not wording. If a document already carries a
# stronger header form -- numbered, `##`, or a bold line alone -- then its bullets are
# subordinate to those headers, which is what a Markdown outline means. Bullets are
# promoted to findings only when nothing stronger is present.
_STRONG = re.compile(
    r"""^(?:
          [ \t]{0,3}\d{1,2}[.)][ \t]+
        | [ \t]{0,3}\#{1,4}[ \t]+
        | [ \t]{0,3}\*\*[^\n*][^\n]*\*\*[ \t]*$
      )""",
    re.M | re.X,
)

# Opportunistic location parsing. Absence is recorded as absence -- a missing file or line
# is None, never a guess, because a fabricated location is worse than no location.
# Extensions are ordered LONGEST-FIRST and closed with \b. Python alternation is
# leftmost-first, not longest-match, so `c` ahead of `cc`/`cpp`/`cs` made `Foo.cs:20` parse
# as path `Foo.c` -- CORRUPTING THE PATH, not merely losing the line, and leaving `s:20`
# so the line group never matched either. C/C++/C# are 766 of AACR-Bench's 2145 items.
_EXT = r"(?:cpp|cc|cs|php|java|py|js|ts|go|rs|rb|c|h)"
_PATH_LINE = re.compile(r"`?([\w./-]+\." + _EXT + r")\b`?(?::(\d{1,6}))?")
# A diff hunk header names the line the change starts at, and this project's own diff
# prompt tells judges to take line numbers from exactly here. `@@ -112,6 +112,10 @@` -> 112,
# reading the NEW-file side, which is what a reviewer is looking at.
_HUNK = re.compile(r"@@[^@\n]*?\+(\d{1,6})")
# `Foo.py L42` / `L42` -- a common shorthand the prose form does not cover.
_L_PREFIX = re.compile(r"\bL(\d{1,6})\b")
_BACKTICK = re.compile(r"`([^`\n]{1,80})`")
# `line 114`, `Line: 114`, `- **Line:** 114` -- the last is the shape this project's
# own prompt ASKS for, and the original `line[ \t]+\d` could not read it because of the
# markup and colon in between. Bounded to 12 non-digit chars so it cannot leap a sentence.
_LINE_ONLY = re.compile(r"\bline[s]?\b[^\d\n]{0,12}?(\d{1,6})\b", re.I)


def _fence_spans(text):
    """Character ranges inside fenced code blocks.

    Headers inside a fence are DISPLAYED code, not findings. A judge quoting
    "## 1. Not a real heading" in an example must not have it counted as a finding --
    a mistake this project has made and fixed once already in the renderer.
    """
    spans, opener = [], None
    for m in re.finditer(r"^[ \t]*(`{3,}|~{3,})[^\n]*$", text, re.M):
        if opener is None:
            opener = (m.end(), m.group(1)[0], len(m.group(1)))
        elif m.group(1)[0] == opener[1] and len(m.group(1)) >= opener[2]:
            spans.append((opener[0], m.start()))
            opener = None
    if opener is not None:  # unclosed fence: everything after it is displayed
        spans.append((opener[0], len(text)))
    return spans


def _in_spans(pos, spans):
    return any(a <= pos < b for a, b in spans)


def observation_id(judge, run, start, end):
    """Immutable identity: who said it, in which run, at which span."""
    key = f"{judge}\x00{run}\x00{start}\x00{end}\x00{EXTRACTOR_VERSION}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _location(chunk):
    """File / line / symbol, when the judge actually stated them."""
    loc = {"path": None, "line": None, "symbol": None}
    m = _PATH_LINE.search(chunk)
    if m:
        loc["path"] = m.group(1)
        if m.group(2):
            loc["line"] = int(m.group(2))
    if loc["line"] is None:
        for pat in (_LINE_ONLY, _HUNK, _L_PREFIX):
            m2 = pat.search(chunk)
            if m2:
                loc["line"] = int(m2.group(1))
                break
    for m3 in _BACKTICK.finditer(chunk):
        cand = m3.group(1).strip()
        # a symbol, not a path and not a sentence
        if cand and cand != loc["path"] and " " not in cand and "/" not in cand:
            loc["symbol"] = cand
            break
    return loc


def extract(text, judge="?", run="?"):
    """Atomize one review into span-grounded observations.

    Returns {"observations": [...], "unextracted": [...], "extractor": VERSION}.

    `unextracted` holds every run of non-whitespace material that no observation covers,
    with its span. It is normally the preamble before the first finding. It exists so that
    a review the extractor could not parse is VISIBLE as unparsed rather than silently
    equal to a review with nothing in it.
    """
    text = text or ""
    fences = _fence_spans(text)
    # Bullets are boundaries only when nothing stronger is present -- see _STRONG above.
    strong_present = any(
        not _in_spans(m.start(), fences) for m in _STRONG.finditer(text)
    )
    pattern = _STRONG if strong_present else FINDING_START
    starts = [
        m.start() for m in pattern.finditer(text) if not _in_spans(m.start(), fences)
    ]

    obs = []
    for i, st in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[st:end]
        if not chunk.strip():
            continue
        head = chunk.lstrip().splitlines()[0].strip() if chunk.strip() else ""
        obs.append(
            {
                "observation_id": observation_id(judge, run, st, end),
                "judge": judge,
                "run": run,
                "start": st,
                "end": end,
                "verbatim": chunk,
                "heading": head[:200],
                "location": _location(chunk),
                "extractor": EXTRACTOR_VERSION,
            }
        )

    covered = [(o["start"], o["end"]) for o in obs]
    unextracted = []
    cursor = 0
    for a, b in covered + [(len(text), len(text))]:
        if a > cursor and text[cursor:a].strip():
            unextracted.append({"start": cursor, "end": a, "verbatim": text[cursor:a]})
        cursor = max(cursor, b)
    return {
        "observations": obs,
        "unextracted": unextracted,
        "extractor": EXTRACTOR_VERSION,
    }


def coverage(result, text):
    """Fraction of non-whitespace characters attributed to some observation.

    Reported rather than asserted: a low number is not necessarily wrong (a long preamble
    is genuinely not a finding), but a number that DROPS is a regression in the instrument.
    """
    total = len("".join((text or "").split()))
    if not total:
        return 1.0
    got = sum(len("".join(o["verbatim"].split())) for o in result["observations"])
    return min(1.0, got / total)
