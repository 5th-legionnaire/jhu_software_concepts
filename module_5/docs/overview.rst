Overview and Setup
==================

What this service does
----------------------

Grad Cafe Analytics loads self-reported graduate admissions results into
PostgreSQL and serves them. The pipeline has five steps: **scrape** (render
Grad Cafe result pages in Chrome), **clean** (parse the saved HTML into
applicant records), **load** (insert them, ``ON CONFLICT (p_id) DO NOTHING`` so
a repeated pull adds nothing twice), **query** (nine required questions and two
original ones, through composed SQL and again through the SQLAlchemy ORM), and
**serve** (the Flask analysis page, read fresh on every request, and
``GET /api/applicants``, a bounded and validated search).

Requirements
------------

- Python 3.14 (developed and tested on 3.14.6)
- PostgreSQL (18.6 locally, 16 in CI)
- Graphviz, for the dependency graph and one test that regenerates it
- Chrome, only for a real Pull Data; no test launches a browser

Installation (pip or uv)
------------------------

Dependencies are declared once, in ``setup.py``. ``requirements.txt`` is a
fully pinned lock generated from it. Either installer builds the same
environment; the second command in each is the editable install of the
project itself, which is what lets the flat modules in ``src/`` import each
other from anywhere.

.. code-block:: console

   $ cd module_5
   $ python3.14 -m venv .venv && source .venv/bin/activate     # pip
   $ pip install -r requirements.txt
   $ pip install -e . --no-deps

   $ uv venv -p 3.14 .venv && source .venv/bin/activate        # or uv
   $ uv pip sync requirements.txt
   $ uv pip install -e . --no-deps

``scripts/fresh_install_check.sh`` proves both recipes from a clean copy.

Configuration
-------------

Settings come from the environment, from a ``.env`` file in ``module_5/``
(copy ``.env.example``) or the shell:

.. list-table::
   :header-rows: 1

   * - Variable
     - Meaning
   * - ``DB_HOST``, ``DB_PORT``, ``DB_NAME``
     - where the database is
   * - ``DB_USER``, ``DB_PASSWORD``
     - the runtime account (``gradcafe_app``): the web app and Pull Data
   * - ``DB_OWNER_USER``, ``DB_OWNER_PASSWORD``
     - the owner account (``gradcafe_owner``): schema setup and the bulk load
       only, kept out of the running app's environment
   * - ``DATABASE_URL``
     - optional single-URL override; beats ``DB_*``, loses to an explicit
       ``database_url`` argument
   * - ``TEST_DATABASE_URL``, ``TEST_ADMIN_DATABASE_URL``
     - the disposable test database, as the runtime and the owner account

A missing variable raises ``KeyError`` naming the variable and never a value.
The libpq ``PG*`` variables Module 3 used are not read.

Database setup
--------------

``sql/roles.sql`` creates the two accounts, ``sql/grants.sql`` gives the
runtime account ``SELECT`` and ``INSERT`` on ``applicants`` and nothing else,
and ``sql/migrate_ownership.sql`` moves an existing table under the owner. No
password is ever given to ``psql``: each is turned into a SCRAM-SHA-256
verifier by ``scripts/scram_verifier.py`` and passed in the environment. The
README's "Database setup" section has the exact commands; :doc:`security`
explains the privileges.

Running
-------

.. code-block:: console

   $ python3 src/app.py        # http://127.0.0.1:8080/analysis  (PORT overrides 8080)
   $ curl "http://127.0.0.1:8080/api/applicants?limit=5&sort=gpa"
   $ pytest                    # the whole suite, 100% coverage required
