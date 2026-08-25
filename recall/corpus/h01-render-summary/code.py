"""Render a run directory as a small HTML summary."""
import html
import json
import pathlib
import re

FENCE = re.compile(r"^\s*(`{3,})")
HEADING = re.compile(r"^#{1,4}\s*(\d{1,2})[.)]\s+(.+?)\s*$", re.M)


def fence_mask(lines):
    """Which lines sit inside a fenced code block."""
    mask, depth = [], 0
    for ln in lines:
        if FENCE.match(ln):
            depth = 0 if depth else 1
            mask.append(True)
        else:
            mask.append(bool(depth))
    return mask


def headings(text):
    """{number: title} for the numbered headings in text."""
    lines = text.split("\n")
    mask = fence_mask(lines)
    visible = "\n".join("" if mask[i] else l for i, l in enumerate(lines))
    out = {}
    for m in HEADING.finditer(visible):
        out.setdefault(m.group(1), m.group(2))
    return out


def load_meta(rundir):
    """Metadata for a run directory."""
    p = pathlib.Path(rundir) / "run.json"
    if not p.is_file():
        return {}
    meta = json.loads(p.read_text())
    meta["judges"] = {j["name"]: j for j in meta.get("judges", [])}
    return meta


def total_cost(meta):
    """What this run cost."""
    return sum(j.get("cost") or 0 for j in meta.get("judges", {}).values())


def summarise(rundir):
    meta = load_meta(rundir)
    body = []
    for name, j in meta.get("judges", {}).items():
        title = html.escape(name)
        body.append(f"<li>{title}: {j.get('secs', 0):.1f}s</li>")
    return f"<ul>{''.join(body)}</ul><p>${total_cost(meta):.4f} spent</p>"
