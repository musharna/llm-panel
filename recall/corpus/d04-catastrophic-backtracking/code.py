import re


def linkify(text):
    """Turn markdown links into anchors."""
    return re.sub(r"\[([^\]\n]{1,300})\]\((https?://[^)\s]+)\)",
                  r'<a href="\2">\1</a>', text)
