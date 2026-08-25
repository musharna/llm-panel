def top_n(scores, n):
    """The n highest scores, highest first."""
    ordered = sorted(scores.items(), key=lambda kv: kv[1])
    return [name for name, _ in ordered[:n]]
