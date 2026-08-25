def page_of(items, page, per_page=10):
    """The items on `page` (1-indexed)."""
    start = (page - 1) * per_page
    return items[start:start + per_page - 1]
