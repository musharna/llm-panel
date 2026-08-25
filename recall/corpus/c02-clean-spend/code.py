def total_spend(records):
    """Total billed, and how many records carried no measurement.

    Returns (total, unmeasured). Callers must not treat an unmeasured
    record as zero -- the count is returned so they cannot.
    """
    total = 0.0
    unmeasured = 0
    for r in records:
        cost = r.get("cost")
        if cost is None:
            unmeasured += 1
            continue
        total += cost
    return total, unmeasured
