def count_lines(paths):
    """Line count per path."""
    return {p: len(open(p).read().splitlines()) for p in paths}
