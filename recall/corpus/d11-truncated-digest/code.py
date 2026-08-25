import hashlib
import re


def slug(name):
    """A CSS-safe class per name, unique across different names."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "n"
    return f"{base}-{hashlib.sha256(name.encode()).hexdigest()[:4]}"
