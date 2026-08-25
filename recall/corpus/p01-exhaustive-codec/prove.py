#!/usr/bin/env python3
"""Exhaustive proof that code.py has no defect WITHIN ITS STATED DOMAIN.

This is the point of the fixture. Every other corpus case has *verified scope* --
its planted defects are known to misbehave, but nothing rules out an unplanted one.
On such a fixture "the judge abstained" and "the judge missed something" are the same
observation, so no false-positive rate can be computed from it.

Here the domain is finite (18278 indices, 18278 labels) and enumerated COMPLETELY.
The oracle is built by a different construction from the implementation -- itertools
lexicographic enumeration versus divmod -- so agreement is not two copies of one
mistake. Rejection of everything outside the domain is likewise enumerated rather
than sampled.

What this does and does not establish:
  DOES  -- for every input in the stated domain, the output is the specified one;
           for a large, systematically generated set of inputs outside it, the
           function raises ValueError rather than returning a wrong answer.
  DOES NOT -- say anything about performance, style, API taste, or behaviour under
           concurrency/IO, because the module has none of those.

A finding against this file is therefore either (a) about something outside the
stated domain, which is informative and should be read, or (b) a false positive.
That distinction is what makes a false-positive rate reportable at all.

    python3 prove.py        # exit 0 = proven, non-zero = the fixture is NOT clean
"""

import itertools
import types
import pathlib
import sys

# Compile the SOURCE TEXT directly instead of importing. An import consults
# __pycache__, which is validated on (mtime, size) -- and a mutation harness routinely
# produces two different mutants of identical size within the same mtime tick. Measured
# here: `divmod(index - 1, 26)` -> `divmod(index, 26)` and `... + position + 1` ->
# `... + position` both delete exactly four characters, so the second mutant silently ran
# the FIRST one's bytecode and the prover reported a defect in encode for a decode-only
# edit. The two runs were byte-identical, which is what made it invisible: the instrument
# could not distinguish two states it was trusted to distinguish. exec of freshly
# compiled source has no cache to be stale.
CODE = pathlib.Path(__file__).parent / "code.py"
codec = types.ModuleType("codec")
codec.__file__ = str(CODE)
exec(compile(CODE.read_text(encoding="utf-8"), str(CODE), "exec"), codec.__dict__)

FAIL = []


def guard(label, fn, detail=""):
    """Run a check that CALLS the module, recording an unexpected exception as a failure.

    Bare `check("span basic", codec.span("Y","AB") == [...])` evaluates the call before
    check() ever runs, so a module that raises there kills the whole prover: it exits
    non-zero -- which scores as "defect detected" -- while every later check goes unrun
    and unreported. Verified against a decode off-by-one mutant, which crashed the prover
    at the first span assertion instead of failing the decode assertion that names the
    bug. An aborted prover and a thorough one are not the same evidence.
    """
    try:
        check(label, fn(), detail)
    except Exception as e:  # noqa: BLE001
        FAIL.append(f"{label} raised {type(e).__name__}: {str(e)[:80]}")


def check(label, cond, detail=""):
    if not cond:
        FAIL.append(f"{label} {detail}".strip())


# --- the oracle: every label in column order, built lexicographically ----------------
# itertools.product in ALPHABET order yields A..Z, AA..ZZ, AAA..ZZZ -- which IS column
# order for a bijective base-26 of fixed width, concatenated by ascending width. Nothing
# here divides or takes a remainder, so it cannot share an off-by-one with the divmod
# implementation under test.
ORACLE = []
for width in (1, 2, 3):
    for combo in itertools.product(codec.ALPHABET, repeat=width):
        ORACLE.append("".join(combo))

check("oracle size", len(ORACLE) == 18278, f"got {len(ORACLE)}")
check("oracle matches MAX_INDEX", len(ORACLE) == codec.MAX_INDEX, f"got {len(ORACLE)}")
check("oracle has no duplicates", len(set(ORACLE)) == len(ORACLE))

# Each enumeration is wrapped for the same reason guard() exists: an implementation that
# RAISES part-way through the domain must be reported as a failure of THAT check, not
# allowed to abort the prover and take every later check with it.
i = None  # bound by the loops below; initialised so a handler can always report
# --- 1. encode is exactly the oracle, for EVERY index in the domain ------------------
try:
    for i, expected in enumerate(ORACLE, start=1):
        got = codec.encode(i)
        if got != expected:
            check("encode", False, f"encode({i}) = {got!r}, oracle says {expected!r}")
            break
except Exception as e:  # noqa: BLE001
    FAIL.append(f"encode raised {type(e).__name__} at index {i}: {str(e)[:70]}")

# --- 2. decode inverts encode, for EVERY index in the domain -------------------------
try:
    for i in range(codec.MIN_INDEX, codec.MAX_INDEX + 1):
        back = codec.decode(codec.encode(i))
        if back != i:
            check("round-trip", False, f"decode(encode({i})) = {back}")
            break
except Exception as e:  # noqa: BLE001
    FAIL.append(f"round-trip raised {type(e).__name__} at index {i}: {str(e)[:70]}")

# --- 3. decode is exactly the oracle's inverse, for EVERY label ----------------------
try:
    for i, label in enumerate(ORACLE, start=1):
        got = codec.decode(label)
        if got != i:
            check("decode", False, f"decode({label!r}) = {got}, oracle says {i}")
            break
except Exception as e:  # noqa: BLE001
    FAIL.append(f"decode raised {type(e).__name__} at label {i}: {str(e)[:70]}")


# --- 4. everything OUTSIDE the domain raises, enumerated not sampled -----------------
def raises(fn, arg):
    try:
        fn(arg)
    except ValueError:
        return True
    except Exception as e:  # noqa: BLE001
        FAIL.append(f"{fn.__name__}({arg!r}) raised {type(e).__name__}, not ValueError")
        return True
    return False


for bad in [0, -1, -18278, codec.MAX_INDEX + 1, codec.MAX_INDEX + 10**6]:
    check("encode range", raises(codec.encode, bad), f"encode({bad}) did not raise")
# bool is an int in Python: True would silently encode as "A" without the explicit guard.
for bad in [True, False, 1.0, "1", None, [1], {1: 1}, complex(1)]:
    check("encode type", raises(codec.encode, bad), f"encode({bad!r}) did not raise")

# every single-character string that is NOT an uppercase A-Z, across the whole of
# latin-1 plus a few beyond it -- rejection is enumerated, not spot-checked
for point in list(range(0, 256)) + [0x100, 0x2028, 0x1F600]:
    ch = chr(point)
    if ch in codec.ALPHABET:
        continue
    check("decode charset", raises(codec.decode, ch), f"decode({ch!r}) did not raise")

for bad in ["", "AAAA", "ZZZZ", "a", "Aa", "A1", " A", "A ", "A\n"]:
    check("decode shape", raises(codec.decode, bad), f"decode({bad!r}) did not raise")
for bad in [1, None, ["A"], b"A", 1.0]:
    check("decode type", raises(codec.decode, bad), f"decode({bad!r}) did not raise")

# --- 5. span: contiguity, endpoints, inversion --------------------------------------
guard("span basic", lambda: codec.span("Y", "AB") == ["Y", "Z", "AA", "AB"])
guard("span single", lambda: codec.span("A", "A") == ["A"])
guard(
    "span endpoints",
    lambda: codec.span("A", "ZZZ")[0] == "A" and codec.span("A", "ZZZ")[-1] == "ZZZ",
)
guard("span full length", lambda: len(codec.span("A", "ZZZ")) == codec.MAX_INDEX)
guard("span equals oracle", lambda: codec.span("A", "ZZZ") == ORACLE)

# EVERY start point, not three hand-picked ranges.
#
# The first version of this proof checked span() on "Y".."AB", "A".."A" and the full
# range, and truth.json still claimed "no defect within the stated domain". A panel
# reviewing this fixture caught the gap: a span defect that only shows for particular
# sub-ranges -- an off-by-one at a width boundary, say -- would have survived, so the
# CLAIM was broader than the EVIDENCE. That is precisely the overclaim this fixture
# exists to make impossible, sitting in the fixture itself.
#
# All (first,last) pairs is ~167M and not worth the wall-clock. Every start index, at
# each of the three shortest lengths, is 3 x 18278 comparisons and catches anything that
# depends on where a span starts or on crossing Z->AA (26->27) and ZZ->AAA (702->703).
try:
    _bad_span = None
    for i in range(codec.MIN_INDEX, codec.MAX_INDEX + 1):
        for _len in (1, 2, 3):
            j = i + _len - 1
            if j > codec.MAX_INDEX:
                continue
            got = codec.span(ORACLE[i - 1], ORACLE[j - 1])
            if got != ORACLE[i - 1 : j]:
                _bad_span = f"span({ORACLE[i - 1]!r},{ORACLE[j - 1]!r}) = {got!r}"
                break
        if _bad_span:
            break
    check("span over every start point", _bad_span is None, _bad_span or "")
except Exception as e:  # noqa: BLE001
    FAIL.append(f"span sweep raised {type(e).__name__}: {str(e)[:70]}")
try:
    codec.span("B", "A")
    check("span inverted", False, "did not raise on last < first")
except ValueError:
    pass
# an inverted range must raise rather than return [] -- a silent empty list is the
# 'absence-as-zero' defect class this corpus plants elsewhere on purpose.
for a, b in [("AA", "A"), ("ZZZ", "AAA"), ("B", "A")]:
    try:
        codec.span(a, b)
        check("span inverted", False, f"span({a!r},{b!r}) did not raise")
    except ValueError:
        pass

# --- 6. no hidden state: repeated calls agree -----------------------------------------
guard(
    "encode is pure",
    lambda: (
        [codec.encode(n) for n in (1, 27, 18278)]
        == [codec.encode(n) for n in (1, 27, 18278)]
    ),
)
guard("no module mutation", lambda: codec.ALPHABET == "ABCDEFGHIJKLMNOPQRSTUVWXYZ")

print(f"  domain enumerated : {codec.MAX_INDEX} indices, {len(ORACLE)} labels")
print(
    f"  rejection cases   : {256 + 3} codepoints + {9 + 5 + 8 + 5} malformed/typed inputs"
)
if FAIL:
    print(f"\nNOT PROVEN -- {len(FAIL)} failure(s):")
    for f in FAIL[:20]:
        print("   ", f)
    sys.exit(1)
print("\nPROVEN: no defect within the stated domain.")
