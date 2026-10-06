"""db_safety.py: query safety controls shared by every SQL path.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

New in Module 5 (CHG-07 in CHANGES.md). Every SELECT in the project carries a
LIMIT taken from clamp_limit(), so one definition of "maximum" governs the raw
SQL, the ORM, and the search endpoint. The two parsing functions are the
boundary between request text and SQL: they reject what they cannot make safe
and raise errors that name the field and the problem but never echo the value.

Contains:
    Constants:   MIN_LIMIT, MAX_LIMIT, DEFAULT_LIMIT
    Errors:      InputError, LimitError
    Limits:      clamp_limit(), parse_limit()
    Text input:  validate_text()
"""

import re
import unicodedata

MIN_LIMIT, MAX_LIMIT, DEFAULT_LIMIT = 1, 100, 20

# An optional sign and at most nine ASCII digits: enough that a huge request
# such as 1000000 is clamped rather than refused, few enough that int() never
# sees a long string. [0-9] rather than \d, which also matches non-ASCII digits
# that int() would accept; fullmatch rather than $, which tolerates a trailing
# newline.
_LIMIT_TEXT = re.compile(r"[+-]?[0-9]{1,9}")

# Control characters (category Cc, which includes NUL) and lone surrogates
# (Cs). psycopg raises DataError on NUL and UnicodeEncodeError on a surrogate,
# either of which would otherwise surface as a 500.
_REJECTED_CATEGORIES = {"Cc", "Cs"}


class InputError(ValueError):
    """Request input that cannot be made safe. The message never echoes the value."""


class LimitError(InputError):
    """A limit that is not a plain integer of reasonable length."""


def clamp_limit(value, default=DEFAULT_LIMIT):
    """Return a LIMIT inside MIN_LIMIT and MAX_LIMIT.

    Args:
        value: the requested limit, or None for the default.
        default: used when ``value`` is None.

    Returns:
        int: ``default`` for None, MIN_LIMIT for anything below it, MAX_LIMIT
        for anything above it, otherwise ``value``.
    """
    if value is None:
        value = default
    return max(MIN_LIMIT, min(MAX_LIMIT, value))


def parse_limit(raw):
    """Parse a limit from request text, strictly, and clamp it.

    Args:
        raw: the query-string value, or None when the parameter was absent.

    Returns:
        tuple[int, bool]: the effective limit, and whether clamping changed
        the requested value. An absent parameter is the default, not clamped.

    Raises:
        LimitError: unless ``raw`` is an optional sign and one to nine ASCII
            digits. Rejects "1e3", "10 OR 1=1", " 5", and a 5000-digit string
            without ever handing it to int().
    """
    if raw is None:
        return DEFAULT_LIMIT, False
    if not _LIMIT_TEXT.fullmatch(raw):
        raise LimitError("limit must be a whole number of at most 9 digits")
    requested = int(raw)
    effective = clamp_limit(requested)
    return effective, effective != requested


def validate_text(raw, field, max_len):
    """Check a free-text filter value before it becomes a query parameter.

    The value is returned unchanged: it is bound as a parameter, never spliced
    into SQL, so it needs rejecting where it cannot be stored or sent safely,
    not rewriting.

    Args:
        raw: the query-string value, or None when absent.
        field: the parameter's name, used in the error message.
        max_len: the longest accepted value, in characters.

    Returns:
        str | None: the value, or None when it was absent or empty.

    Raises:
        InputError: when the value is longer than ``max_len`` or contains a
            control character (NUL included) or a lone surrogate.
    """
    if raw is None or raw == "":
        return None
    if len(raw) > max_len:
        raise InputError(f"{field} must be at most {max_len} characters")
    if any(unicodedata.category(char) in _REJECTED_CATEGORIES for char in raw):
        raise InputError(f"{field} contains a control character")
    return raw
