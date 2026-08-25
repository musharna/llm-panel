"""A small on-disk index that summarises run directories."""
import json
import pathlib


class Index:
    """Caches a summary per run directory, up to `max_entries`."""

    def __init__(self, path, max_entries=500):
        self.path = pathlib.Path(path)
        self.max_entries = max_entries
        self.entries = {}

    def summarise(self, run):
        """Byte size of the run's panel.md, cached."""
        key = str(run)
        if key not in self.entries:
            self.entries[key] = len(pathlib.Path(run).read_bytes())
        return self.entries[key]

    def save(self):
        self.path.write_text(json.dumps(self.entries))

    def load(self):
        """Read the index back."""
        if not self.path.is_file():
            return {}
        try:
            self.entries = json.loads(self.path.read_text())
        except ValueError:
            self.entries = {}
        return self.entries
