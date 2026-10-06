"""Spies that record the statements code hands to a psycopg cursor.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

A spy wraps a real cursor or connection, records every statement passed to
execute or executemany, and then delegates, so the code under test runs for
real against the database while its statements are captured. Shared by
test_sql_guard.py (are they all composables?) and the pull tests (is any of
them DDL?).
"""

from psycopg import sql


class SpyCursor:
    """Records the statement of every execute and executemany, then delegates."""

    def __init__(self, inner, seen):
        self._inner, self._seen = inner, seen

    def execute(self, query, params=None, **kwargs):
        """Record the statement, then run it."""
        self._seen.append(query)
        return self._inner.execute(query, params, **kwargs)

    def executemany(self, query, params_seq, **kwargs):
        """Record the statement, then run it for every parameter set."""
        self._seen.append(query)
        return self._inner.executemany(query, params_seq, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return self._inner.__exit__(*exc_info)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class SpyConnection:
    """A connection whose cursors are spies."""

    def __init__(self, inner, seen):
        self._inner, self._seen = inner, seen

    def cursor(self, *args, **kwargs):
        """A spy over a real cursor."""
        return SpyCursor(self._inner.cursor(*args, **kwargs), self._seen)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def rendered(statement):
    """A recorded statement as text, however it was given."""
    return statement.as_string(None) if isinstance(statement, sql.Composable) else str(statement)
