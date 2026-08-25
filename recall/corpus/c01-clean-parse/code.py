def parse_kv(lines):
    """Parse `key = value` lines, ignoring blanks and # comments."""
    out = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"not a key=value line: {line!r}")
        key, _, value = stripped.partition("=")
        out[key.strip()] = value.strip()
    return out
