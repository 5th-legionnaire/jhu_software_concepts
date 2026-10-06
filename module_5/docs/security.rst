Security and Assurance
======================

Each control below has a Change Register entry (``CHANGES.md``, ``CHG-xx``)
with its reason and the tests that verify it, and a gate that fails when the
control is removed.

SQL injection defenses
----------------------

Every statement is a psycopg ``sql.Composed``: identifiers through
``sql.Identifier``, values through placeholders, static text as ``sql.SQL``.
Builders return ``(statement, params)`` and touch no database; one executor
per module calls ``cursor.execute(statement, params)``, and
:func:`load_data.execute_query` refuses a bare string. Every value is bound,
constants included (CHG-05, CHG-06).

:mod:`applicant_search` is the endpoint that takes user input (CHG-08). It
validates request text into a frozen :class:`applicant_search.SearchFilters`,
composes the statement, and executes it, in three separate steps. The sort
column must be one of nine names and reaches SQL as a quoted identifier; the
direction is one of two fixed fragments; filters are bound parameters; LIKE
wildcards in the search text are escaped. Unknown parameters, control
characters (including NUL) and over-length values are a ``400`` before any
statement exists, and no error repeats the input.

Proved by an AST guard over ``src/`` (no f-string, ``+``, ``%`` or
``.format()`` holding SQL), a spy cursor (only composed statements reach the
driver), and a 51-case malicious-input matrix against a real database: no
``500``, no leak, never every row, and the table intact.

LIMIT enforcement
-----------------

:mod:`db_safety` defines one maximum: :func:`db_safety.clamp_limit` keeps every
limit between 1 and 100 (default 20). Every SELECT, raw and ORM, ends in a
bound ``LIMIT``. Aggregates get an output limit, so no analysis answer
changes, which a parity test checks against Module 4 over all 30,000 rows.
:func:`db_safety.parse_limit` accepts only an optional sign and up to nine
ASCII digits, so ``1000000`` is clamped to 100 and ``1e3`` is refused (CHG-07).

Least privilege and credentials
-------------------------------

Two roles (CHG-11 to CHG-13). ``gradcafe_owner`` owns the table and does
schema setup and the bulk load. ``gradcafe_app``, which the app and Pull Data
use, is not a superuser, cannot create databases or roles, and holds only
``SELECT`` and ``INSERT`` on ``applicants``. It cannot DROP, ALTER, UPDATE,
DELETE or TRUNCATE, so a flaw can at worst read and add public applicant rows.
The tests connect as these accounts and ask the database what each may do.

Credentials come only from the environment (CHG-03); connection errors are
logged without the driver's text, which can echo host and user (CHG-04).
Passwords never reach the server or a command line: roles are set from
SCRAM verifiers. ``scripts/check_credential_leaks.py`` searches the tree, all
git history, the server log and shell history for the real passwords on every
gate.

Static analysis and supply chain
--------------------------------

- **Pylint** scores 10.00/10 on ``src/`` with no inline disables; ``.pylintrc``
  holds only the source root and one classification (CHG-14 to CHG-17).
- **pydeps** and Graphviz build ``dependency.svg``; a test regenerates it and
  checks it is current.
- **Snyk** found 22 entries in two packages (``urllib3`` 2.7.0, ``python-dotenv``
  1.0.1), fixed by upgrading; all 70 pinned packages now scan clean. Snyk Code
  found a false positive, removed in code (CHG-21), and a low-severity note on a
  command-line path, accepted with reasons in ``report/snyk_triage.md``.

Continuous integration
----------------------

``.github/workflows/ci.yml`` runs on every push and pull request with four
jobs that fail independently: ``lint``, ``dependency-graph``, ``snyk``, and
``test`` (the full suite on pip and on uv, against PostgreSQL 16 with the two
least-privilege roles) (CHG-19).
