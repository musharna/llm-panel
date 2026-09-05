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

# "2": headings at all six levels are boundaries (were four). Bumped so a result file says
# which extractor produced it and the span cache does not serve v1 parses as v2.
EXTRACTOR_VERSION = "3"

# An explicit ABSTENTION, and why it is a sentinel rather than a phrase list.
#
# A judge that finds nothing writes prose -- "**No real defect found.**" followed by a
# numbered list of REASONS. Structurally that is byte-identical to a numbered list of
# findings, so this extractor turned one abstention into three false defects. Markdown
# shape cannot observe whether a chunk asserts a defect; the information was never in the
# text. That is the same class as this project's guards-that-cannot-discriminate frontier.
#
# The rejected fix was matching negative phrasings ("no issues", "LGTM", "looks good").
# That is A LIST OF NAMES GUARDING AN OPEN SET -- the mistake recorded more times here
# than any other -- because the ways a model can phrase "nothing found" are unbounded.
#
# A sentinel is not that. The open set is the set of phrasings a judge might INVENT; this
# is one exact string that the prompt ASKS for, so both sides of the protocol are mine.
# Compliance is not assumed: a judge that ignores the instruction simply falls through to
# normal extraction, and `aacr-upstream` REPORTS the compliance rate rather than trusting
# it -- routing is not compliance.
ABSTAIN = "NO DEFECTS FOUND"
_ABSTAIN_LINE = re.compile(
    r"^[ \t]{0,3}\**[ \t]*" + ABSTAIN + r"[ \t]*\**[ \t]*$", re.M
)


# The union of every finding-header form this project has been burned by, each earned.
# Order matters only for readability; the scan takes the leftmost match of any of them.
#
#   1.  / 1)            numbered, the common case
#   # .. ######         a Markdown heading, all six levels. This stopped at four while
#                       panel-report rendered six, so a `##### Finding` was a heading to
#                       the reader and body text to the extractor -- the same boundary,
#                       guessed differently in each consumer, which is the defect this
#                       file's header says it exists to end. Found by nemotron, 2026-08-26.
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
        | [ \t]{0,3}\#{1,6}[ \t]+                # ## heading
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
        | [ \t]{0,3}\#{1,6}[ \t]+
        | [ \t]{0,3}\*\*[^\n*][^\n]*\*\*[ \t]*$
      )""",
    re.M | re.X,
)

# Opportunistic location parsing. Absence is recorded as absence -- a missing file or line
# is None, never a guess, because a fabricated location is worse than no location.
# A path is recognised STRUCTURALLY, not from a list of extensions.
#
# The previous version enumerated (cpp|cc|cs|php|java|py|js|ts|go|rs|rb|c|h). Two faults:
# leftmost-first alternation made `Foo.cs` parse as `Foo.c` (corrupting the path, not just
# losing the line), and the list missed 166 of AACR-Bench's 2145 annotated paths --
# .tsx (19), .mts (16), .xml (13), .jsx (13), .sql (11), .hpp (8), 8 extensionless.
# That is this project's most-repeated mistake: A LIST OF NAMES CANNOT GUARD AN OPEN SET,
# and I built one anyway in a fresh instrument.
#
# Structural rule instead: a token containing "/" is a path whatever its suffix (which
# covers Dockerfile, Makefile and every extension nobody thought of), otherwise a bare
# filename needs a dotted ALPHABETIC suffix of 1-5 chars, with a stem of >=2 characters.
# The suffix being alphabetic rejects `1.2` and `3.14`; the stem length rejects `e.g`/`i.e`.
# Measured against all 2145 real annotated paths: 2139 (99.7%). The one miss is a bare
# `Makefile` with no directory, which is genuinely ambiguous with an English word.
#
# `Node.js` and `and/or` DO match, and that is accepted: a spurious path is harmless here
# because a match additionally requires a line number AND agreement with a real
# annotation's path, so a stray token has nothing to pair with.
_PATH = (
    r"(?:[@\w.-]+/)+[@\w.-]+"  # any token with a separator
    r"|[\w-]{2,}(?:[.\-][\w-]+)*\.[A-Za-z][A-Za-z0-9]{0,4}(?![\w-])"
)  # bare filename.ext
# The trailing `(?![\w-])` is load-bearing. Without it the bounded 1-5 char suffix matches a
# PREFIX of any longer dotted identifier, so ordinary JavaScript turned into file paths:
# `assistant.enableWebSearch` -> `assistant.enabl`, `delta.content` -> `delta.conte`,
# `chunk.textDelta` -> `chunk.textD`. One AACR instance produced 18 findings of which ZERO
# had a usable location, every claimed path being a truncated expression. This is the same
# mechanism as the `Foo.cs` -> `Foo.c` bug already fixed here: a bound that silently yields
# a prefix instead of declining to match. I fixed the alternation ordering then and left
# the bound, so the class survived the fix to its first instance.
# Measured against all 2145 real annotated paths: 2143 before, 2143 after -- zero drift.
# It converts a silently-wrong path into an honest absence, which is the whole rule here.
_PATH_LINE = re.compile(r"`?(" + _PATH + r")`?(?::(\d{1,6}))?")
# A PLAIN bullet whose first token is a `path:line` location is a finding.
#
# FINDING_START admits numbered items, headings, BOLD bullets and bold lines. A plain
# bullet was left out deliberately (a bullet under a bold header is an attribute, not a
# finding). But the prompt asks for FILE and LINE per item, and codex's house style
# answers in exactly that shape with no bold at all:
#     - `misc/random.c:60` -- If `mp_rand_seed(0)` is called before ...
# Every such review parsed to ZERO observations. Measured 2026-08-28 over the finished
# arms: clean 13 reviews fully lost (37 located tokens), checkout 12 (45), broad 0 --
# the loss fell on two arms and not the third, so it biased a published comparison.
# The rule is structural and hierarchy-independent: a location in first position is the
# protocol's own marker for "one item", whatever surrounds it. Extractor version 2 -> 3.
_LOCATED_BULLET = re.compile(
    r"^[ \t]{0,3}[-*+][ \t]+`?(?:" + _PATH + r")`?:\d{1,6}\b", re.M
)
# A diff hunk header names the line the change starts at, and this project's own diff
# prompt tells judges to take line numbers from exactly here. `@@ -112,6 +112,10 @@` -> 112,
# reading the NEW-file side, which is what a reviewer is looking at.
_HUNK = re.compile(r"@@[^@\n]*?\+(\d{1,6})")
# `Foo.py L42` / `foo.py:L42` / `at L42` / `- L42:` -- a common shorthand the prose form
# does not cover. Anchored to a location cue: a bare `\bL\d+\b` scan read "the L2 cache"
# and "L1 regularization" as lines 2 and 1 for findings that named no location at all.
_L_PREFIX = re.compile(r"(?:(?:" + _PATH + r")`?[ \t]*:?[ \t]*|\bat[ \t]+|^[ \t]*(?:[-*+][ \t]+)?)L(\d{1,6})\b", re.M)
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
    # An explicit abstention yields NO observations -- see ABSTAIN above. The whole review
    # is returned as `unextracted` so an abstention is still visible as material that was
    # read and deliberately not turned into findings, never as an empty parse.
    if any(not _in_spans(m.start(), fences) for m in _ABSTAIN_LINE.finditer(text)):
        return {
            "observations": [],
            "abstained": True,
            "unextracted": (
                [{"start": 0, "end": len(text), "verbatim": text}]
                if text.strip()
                else []
            ),
            "extractor": EXTRACTOR_VERSION,
        }
    # Bullets are boundaries only when nothing stronger is present -- see _STRONG above.
    strong_present = any(
        not _in_spans(m.start(), fences) for m in _STRONG.finditer(text)
    )
    pattern = _STRONG if strong_present else FINDING_START
    starts = sorted(
        {m.start() for m in pattern.finditer(text) if not _in_spans(m.start(), fences)}
        | {m.start() for m in _LOCATED_BULLET.finditer(text)
           if not _in_spans(m.start(), fences)}
    )

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
        "abstained": False,
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
