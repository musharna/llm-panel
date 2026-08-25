import json


def load_judges(path):
    """Judges by name, from a run.json that may not list any yet."""
    meta = json.loads(open(path).read())
    return {j["name"]: j for j in meta.get("judges", [])}
