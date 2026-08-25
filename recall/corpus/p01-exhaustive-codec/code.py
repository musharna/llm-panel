"""Spreadsheet-style column labels: 1 <-> "A", 27 <-> "AA", 18278 <-> "ZZZ".

Bijective base-26. Defined for 1 <= n <= 18278 (labels of one to three letters).
Both directions raise ValueError outside that domain; neither reads, writes, or
mutates anything outside its own frame.
"""

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MIN_INDEX = 1
MAX_INDEX = 18278  # 26 + 26**2 + 26**3, i.e. "ZZZ"


def encode(index):
    """Column label for a 1-based column index.

    >>> encode(1), encode(26), encode(27), encode(18278)
    ('A', 'Z', 'AA', 'ZZZ')

    Raises ValueError unless MIN_INDEX <= index <= MAX_INDEX. bool is rejected
    along with every other non-int type: `True` is an int in Python and would
    otherwise silently encode as "A".
    """
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError(f"index must be an int, got {type(index).__name__}")
    if index < MIN_INDEX or index > MAX_INDEX:
        raise ValueError(f"index {index} outside {MIN_INDEX}..{MAX_INDEX}")
    letters = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(ALPHABET[remainder])
    return "".join(reversed(letters))


def decode(label):
    """1-based column index for a column label. Inverse of encode over the domain.

    >>> decode("A"), decode("Z"), decode("AA"), decode("ZZZ")
    (1, 26, 27, 18278)

    Raises ValueError for anything that is not one to three characters drawn
    from ALPHABET. Case is significant: "a" is not a label.
    """
    if not isinstance(label, str):
        raise ValueError(f"label must be a str, got {type(label).__name__}")
    if not 1 <= len(label) <= 3:
        raise ValueError(f"label {label!r} must be one to three letters")
    index = 0
    for char in label:
        position = ALPHABET.find(char)
        if position < 0:
            raise ValueError(f"label {label!r} contains {char!r}, not an A-Z letter")
        index = index * 26 + position + 1
    return index


def span(first, last):
    """Every label from `first` to `last` inclusive, in column order.

    >>> span("Y", "AB")
    ['Y', 'Z', 'AA', 'AB']

    Raises ValueError if either endpoint is invalid or if `last` precedes `first`;
    an inverted range is a caller error, not an empty list, because silently
    returning [] would hide the mistake at the call site.
    """
    start, stop = decode(first), decode(last)
    if stop < start:
        raise ValueError(f"last {last!r} precedes first {first!r}")
    return [encode(i) for i in range(start, stop + 1)]
