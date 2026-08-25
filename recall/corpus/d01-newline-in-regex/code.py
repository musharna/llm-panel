import re

# Headings look like "## Defect 3: title" or "## 3. title".
HEADING = re.compile(r"^#{1,4}\s*(?:[A-Za-z]{1,12}\s+)?(\d{1,2})\s*[.:)]\s+(.+?)\s*$", re.M)


def parse_heading(document):
    """Return {number: title} for every heading in the document."""
    out = {}
    for m in HEADING.finditer(document):
        out.setdefault(m.group(1), m.group(2).strip())
    return out
