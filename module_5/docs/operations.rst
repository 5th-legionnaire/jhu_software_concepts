Operational Notes
=================

Busy-state policy
------------------

A pull in progress is observable state, never inferred: ``app.config["PULL_STATE"]``
holds an :class:`app.PullState` object with a plain ``busy`` flag, set and
read directly rather than polled from a subprocess or a timer. While busy,
both ``POST /pull-data`` and ``POST /update-analysis`` return ``409``
``{"busy": true}`` and perform no work; a gated pull never calls the loader.
The pull job clears the flag in a ``finally`` block, so an error nobody
anticipated cannot leave the app refusing every later pull.

This is a change from Module 3, which allowed ``Update Analysis`` to refresh
during a pull and said so in its notice. Module 3's reasoning was, and
remains, correct: the loader commits a pull in a single transaction, so a
concurrent read sees the database either entirely before the new entries or
entirely after them, never halfway. The gate exists because the assignment
requires it, not because the earlier design was unsafe. It is a reporting
choice: a refresh taken mid-pull would report a total that is about to
change, so the pull now has the page to itself and the figure shown is
never half-superseded.

Idempotency and uniqueness
----------------------------

``p_id`` is the Grad Cafe result id, parsed from the entry's permalink
(``/result/<id>``), not a generated sequence. It is the table's primary
key, and ``url`` additionally carries a ``UNIQUE`` constraint; the two agree
by construction, since the id is parsed out of that same URL.

Every insert is composed by :func:`load_data.build_insert` and ends in:

.. code-block:: sql

   ON CONFLICT ("p_id") DO NOTHING

A pull whose date window overlaps a previous one, or is run twice in a row
with no new Grad Cafe data in between, reinserts nothing: rows already
present are silently skipped, not duplicated and not overwritten. Nothing
posted once is ever edited by a later pull. ``load_data.insert_records()``
reports the split in its log line: how many rows were inserted, how many
were already present, and how many were skipped entirely for having no
parseable result id.

Troubleshooting
-----------------

**PostgreSQL is not running, or the connection settings are wrong.**
``load_data.create_connection()`` catches the connection failure and
returns ``None`` rather than raising; it logs the exception's type and a fixed
hint, never the driver's message, which can echo the host and user name.
Callers stop cleanly. The Flask page returns ``503`` with a notice naming the problem;
``POST /pull-data`` and ``POST /update-analysis`` return ``500``/``503``
with ``{"ok": false, "error": ...}``. Check that PostgreSQL is running and
that the ``DB_*`` settings in ``.env`` (or ``DATABASE_URL``) point at it.

**A connection setting is missing.** Both ``load_data.get_db_config()`` and
``models.build_url()`` use an explicit URL, then ``DATABASE_URL``, then the
``DB_*`` variables. If none is set, ``get_db_config()`` raises ``KeyError``
naming the missing variable and never a value.

**Running the test suite with no PostgreSQL available.** The ``web``,
``buttons``, and ``analysis`` markers need none at all. The ``db`` and
``integration`` markers do; ``clean_db`` fails loudly with a message naming
what to start, rather than skipping silently, since a silent skip would
quietly reduce coverage while looking like a neutral result. They also need
``TEST_DATABASE_URL`` and ``TEST_ADMIN_DATABASE_URL`` to name a disposable
database as the runtime and the owner account; without them the fixtures fail
with a message naming the variable.

**Pull Data says the account is not allowed to add entries.** The runtime
account issues no DDL. If the table does not exist, or ``sql/grants.sql`` was
never applied, the pull stops with that message and writes nothing. Create the
table as the owner (``python3 src/load_data.py`` with the ``DB_OWNER_*``
settings) and apply the grants.

**Chrome or ChromeDriver mismatch, during a real Pull Data.** Selenium
Manager resolves a matching ChromeDriver automatically; no separate driver
install is required. If Grad Cafe shows a verification check instead of
results, it is cleared once, by hand, in the persistent Chrome profile at
``~/.gradcafe-chrome-profile``, the same way an ordinary browser would clear
it.

**The LLM standardizer's environment is missing.** Pull Data stops with a
message pointing at "LLM standardizer setup" in the README, and adds
nothing to the database. It keeps its own virtual environment under
``llm_hosting/.venv``, separate from the main one, because it depends on
``llama-cpp-python``, which compiles native code.

**CI-specific.** ``.github/workflows/ci.yml`` starts a PostgreSQL 16 service,
creates the two roles from per-run random passwords (masked in the log and
passed as SCRAM verifiers), creates the table as the owner, applies the
grants, and runs the suite as the runtime account. Nothing needs configuring
by hand. Module 4's ``tests.yml`` is untouched and still tests ``module_4``.
