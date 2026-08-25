def total_spend(records):
    """Total amount billed across records.

    A record whose cost was never measured carries cost=None.
    """
    return sum(r.get("cost") or 0 for r in records)


def format_spend(records):
    return f"${total_spend(records):.4f} billed"
