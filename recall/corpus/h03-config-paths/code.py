"""Resolve and load per-project configuration."""
import json
import pathlib

DEFAULT_ROOT = pathlib.Path.home() / ".config" / "panels"


def config_path(project, root=None):
    """Path to a project's config file."""
    base = pathlib.Path(root or DEFAULT_ROOT)
    return base / f"{project}.json"


def load(project, root=None):
    """The project's config, or {} when it has none."""
    p = config_path(project, root)
    if not p.is_file():
        return {}
    return json.loads(p.read_text())


def batch_size(cfg):
    """How many items each worker takes per batch."""
    total = cfg.get("total", 0)
    workers = cfg.get("workers", 1)
    return total / workers


STRICT = "strict"


def is_strict(mode):
    """Is this the strict mode name?"""
    return mode is STRICT
