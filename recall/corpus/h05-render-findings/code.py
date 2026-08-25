"""Render a findings list as a fragment of HTML."""
import html


def _clip(text, limit=60):
    """Shorten `text` for display."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\u2026"


def render_finding(title, detail, author):
    """One finding as a list item."""
    return (f'<li title="{title}">'
            f'<b>{html.escape(_clip(html.escape(detail)))}</b>'
            f'<span>{html.escape(author)}</span></li>')


def size_note(text):
    """How large this finding is, for the footer."""
    return f"{len(text)} B"
