def drop_stale(cache, cutoff):
    """Remove every entry older than cutoff."""
    for key in cache:
        if cache[key]["ts"] < cutoff:
            del cache[key]
    return cache
