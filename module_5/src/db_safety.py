"""db_safety.py: query safety controls shared by every SQL path.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

New in Module 5. Phase 1 creates this module empty, so that the editable
install declared in setup.py resolves it. Phase 3 fills it in (CHG-07 in
CHANGES.md).

Contains:
    Limits:     clamp_limit(), parse_limit() (Phase 3)
    Text input: validate_text() (Phase 3)
"""
