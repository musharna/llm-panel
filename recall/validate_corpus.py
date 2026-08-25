#!/usr/bin/env python3
"""Prove every corpus case behaves as its truth.json claims, by EXECUTION.

An unvalidated corpus turns a recall number into a guess with a decimal point: a planted
defect that does not actually misbehave inflates the miss count, and a "clean" decoy with an
accidental bug turns the false-positive control into noise. Both failures are silent.
"""
import importlib.util
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent / "corpus"
FAIL = []


def mod(cid):
    p = ROOT / cid / "code.py"
    spec = importlib.util.spec_from_file_location("c_" + cid.replace("-", "_"), p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check(cid, desc, ok):
    if not ok:
        FAIL.append(cid)
    print(f"  {'ok  ' if ok else 'FAIL'}  {cid}: {desc}")


m = mod("d01-newline-in-regex")
check("d01-newline-in-regex", "a heading pairs with the NEXT line's numbered item",
      m.parse_heading("## Repro\n1. Run it.\n").get("1") == "Run it.")
m = mod("d02-absence-is-zero")
check("d02-absence-is-zero", "an unmeasured cost is summed as zero",
      m.total_spend([{"cost": None}, {"cost": 1.5}]) == 1.5)
m = mod("d03-dead-guard")
check("d03-dead-guard", "IMG_TYPES is a local, so the guard is always False",
      not hasattr(m.Config(), "IMG_TYPES"))
m = mod("d04-catastrophic-backtracking")
t = time.time(); m.linkify("[x](https://a" * 4000); t1 = time.time() - t
t = time.time(); m.linkify("[x](https://a" * 16000); t4 = time.time() - t
check("d04-catastrophic-backtracking",
      f"4x input costs {t4/max(t1,1e-6):.1f}x time (linear would be ~4)", t4 > t1 * 8)
m = mod("d05-explicit-null")
f = pathlib.Path(tempfile.mkdtemp()) / "r.json"; f.write_text('{"judges": null}')
try:
    m.load_judges(f); ok = False
except TypeError:
    ok = True
check("d05-explicit-null", "an explicit null raises TypeError", ok)
m = mod("d06-mutable-default")
m.add_finding("a")
check("d06-mutable-default", "the second call sees the first call's list",
      len(m.add_finding("b")) == 2)
m = mod("d07-swallowed-error")
check("d07-swallowed-error", "a broken config is indistinguishable from an empty one",
      m.read_config("/nonexistent/x.json") == {})
m = mod("d08-sort-direction")
check("d08-sort-direction", "top_n returns the LOWEST scores",
      m.top_n({"Alice": 100, "Bob": 50}, 1) == ["Bob"])
m = mod("d09-mutate-during-iteration")
try:
    m.drop_stale({"a": {"ts": 0}, "b": {"ts": 0}}, 10); ok = False
except RuntimeError:
    ok = True
check("d09-mutate-during-iteration", "RuntimeError: dict changed size", ok)
src = (ROOT / "d10-resource-leak" / "code.py").read_text()
check("d10-resource-leak", "open() with no close and no with-statement",
      "open(" in src and "with " not in src)
m = mod("d11-truncated-digest")
check("d11-truncated-digest", "a.___b and a__---b produce the SAME slug",
      m.slug("a.___b") == m.slug("a__---b"))
m = mod("d12-off-by-one")
check("d12-off-by-one", "a full page returns 9 of 10 items",
      len(m.page_of(list(range(30)), 1)) == 9)

print("  --- clean decoys must behave CORRECTLY ---")
m = mod("c01-clean-parse")
ok = m.parse_kv(["a = 1", "# c", "", "b=2"]) == {"a": "1", "b": "2"}
try:
    m.parse_kv(["oops"]); ok = False
except ValueError:
    pass
check("c01-clean-parse", "parses, and RAISES on a malformed line", ok)
m = mod("c02-clean-spend")
check("c02-clean-spend", "returns (total, unmeasured); never treats None as 0",
      m.total_spend([{"cost": None}, {"cost": 1.5}]) == (1.5, 1))
m = mod("c03-clean-retry")
calls = []


def flaky():
    calls.append(1)
    if len(calls) < 3:
        raise ValueError("nope")
    return "ok"


ok = m.retry(flaky) == "ok" and len(calls) == 3
try:
    m.retry(lambda: (_ for _ in ()).throw(KeyError("always"))); ok = False
except KeyError:
    pass
check("c03-clean-retry", "retries, then RE-RAISES the last error", ok)

print("  --- hard tier: several defects per file, scored per defect ---")
m = mod("h01-render-summary")
_msk = m.fence_mask("```\n  ```python\n  x = 1\n  ```\n```\nAFTER\n".split("\n"))
check("h01/fence-toggle", "a nested fence desynchronises the toggle", _msk[2] is False)
_d = pathlib.Path(tempfile.mkdtemp()); (_d / "run.json").write_text('{"judges": null}')
try:
    m.load_meta(_d); ok = False
except TypeError:
    ok = True
check("h01/null-judges", "an explicit null raises TypeError", ok)
check("h01/cost-none", "an unmeasured cost sums as zero",
      m.total_cost({"judges": {"a": {"cost": None}, "b": {"cost": 1.5}}}) == 1.5)

m = mod("h02-scan-runs")
_root = pathlib.Path(tempfile.mkdtemp())
for _i in range(30):
    (_root / f"r{_i}" / f"s{_i}").mkdir(parents=True)
check("h02/off-by-one", "limit=20 returns 19", len(m.find_runs(_root, 20)) == 19)
try:
    m.prune({"a": {"mtime": 0}, "b": {"mtime": 0}}, now=10 ** 10); ok = False
except RuntimeError:
    ok = True
check("h02/mutate-iter", "RuntimeError: dict changed size", ok)
_f = _root / "f.txt"; _f.write_text("hello")
m.read_sizes([str(_f)])
check("h02/mutable-default", "the memo dict persists across calls",
      len(m.read_sizes([])) == 1)

print("  --- hard tier, expansion 2026-08-23 ---")
m = mod("h03-config-paths")
_root = pathlib.Path(tempfile.mkdtemp())
_esc = m.config_path("../../etc/passwd", _root)
check("h03/path-traversal", "a project name escapes the config root",
      not str(_esc.resolve()).startswith(str(_root.resolve())))
check("h03/int-division", "batch_size returns a float where a count is meant",
      isinstance(m.batch_size({"total": 10, "workers": 4}), float))
# v1 of this case compared str(PosixPath) -- pathlib CACHES its _str, so the identity check
# accidentally held and the planted defect was not a defect. Only execution showed that.
check("h03/identity-vs-equality", "`is` fails for an equal string built at runtime",
      m.is_strict("".join(["str", "ict"])) is False)

m = mod("h04-index-cache")
_ix = m.Index(pathlib.Path(tempfile.mkdtemp()) / "i.json", max_entries=2)
for _i in range(5):
    _g = pathlib.Path(tempfile.mkdtemp()) / f"{_i}.md"
    _g.write_text("y" * (_i + 1))
    _ix.summarise(_g)
check("h04/cap-ignored", "max_entries=2 yet 5 entries are held", len(_ix.entries) == 5)
_f = pathlib.Path(tempfile.mkdtemp()) / "panel.md"
_f.write_text("x" * 10)
_ix2 = m.Index(pathlib.Path(tempfile.mkdtemp()) / "j.json")
_a = _ix2.summarise(_f)
_f.write_text("x" * 99)
check("h04/stale-key", "the file grew 10->99 bytes and the cache still says 10",
      _a == _ix2.summarise(_f) == 10)
_bad = pathlib.Path(tempfile.mkdtemp()) / "c.json"
_bad.write_text("{not json")
_ix3 = m.Index(_bad)
_ix3.entries = {"a": 1}
check("h04/corrupt-silently-empty", "a corrupt index is indistinguishable from an empty one",
      _ix3.load() == {})

m = mod("h05-render-findings")
_out = m.render_finding('" onmouseover=alert(1) x="', "d", "a")
check("h05/unescaped-attribute", "a raw quote breaks out of the title attribute",
      "onmouseover" in _out and "&quot;" not in _out.split("<b>")[0])
_r = m.render_finding("t", "A & B " * 20, "a")
check("h05/clip-after-escape", "the text is escaped twice and the clip cuts an entity",
      "&amp;amp;" in _r or "&am\u2026" in _r or "&a\u2026" in _r)
check("h05/chars-labelled-bytes", "a 2-byte character is reported as 1 B",
      m.size_note("\u00e9") == "1 B" and len("\u00e9".encode()) == 2)

# The sound-scope fixtures are NOT defect-free, and their real defects are ground truth
# now. Asserting them here stops a future pass quietly "fixing" one and turning a
# documented known_unplanted entry into a lie the corpus still ships.
print("  --- sound-scope fixtures: their KNOWN defects are ground truth too ---")
from decimal import Decimal as _Dec

m = mod("c01-clean-parse")
check("c01/known-empty-key", "an empty key is accepted (documented, not planted)",
      m.parse_kv([" = value"]) == {"": "value"})
m = mod("c02-clean-spend")
try:
    m.total_spend([{"cost": _Dec("1.25")}]); _ok = False
except TypeError:
    _ok = True
check("c02/known-decimal", "the 0.0 accumulator rejects Decimal", _ok)
check("c02/known-float", "float accumulation is imprecise",
      m.total_spend([{"cost": 0.1}, {"cost": 0.2}])[0] != 0.3)
m = mod("c03-clean-retry")
try:
    m.retry(lambda: 1 / 0, attempts=3, delay=-1); _ok = False
except ValueError:
    _ok = True
except ZeroDivisionError:
    _ok = False
check("c03/known-negative-delay", "a negative delay masks the callable's exception", _ok)

print(f"\n{'CORPUS INVALID: ' + ', '.join(FAIL) if FAIL else 'corpus validated'}")
sys.exit(1 if FAIL else 0)
