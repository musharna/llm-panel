import json


def read_config(path):
    """Load config, falling back to defaults if anything goes wrong."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}
