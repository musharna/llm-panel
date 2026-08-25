"""Scan a cache of run directories and report on them."""
import pathlib
import time

STALE_AFTER = 60 * 60 * 24 * 30


def find_runs(root, limit=20):
    """The most recent `limit` run directories under root."""
    dirs = [p for p in pathlib.Path(root).glob("*/*") if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[:limit - 1]


def prune(index, now=None):
    """Drop every stale entry from the index."""
    now = now or time.time()
    for key in index:
        if now - index[key]["mtime"] > STALE_AFTER:
            del index[key]
    return index


def read_sizes(paths, sizes={}):
    """Byte size per path, memoised across calls."""
    for p in paths:
        if p not in sizes:
            sizes[p] = len(open(p, "rb").read())
    return sizes


def report(root):
    runs = find_runs(root)
    sizes = read_sizes([str(r / "panel.md") for r in runs if (r / "panel.md").is_file()])
    return {"runs": len(runs), "bytes": sum(sizes.values())}
