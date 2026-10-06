Overview and Setup
==================

What this service does
----------------------

Grad Cafe Analytics loads self-reported graduate admissions results into
PostgreSQL and serves them as an analysis page. The pipeline has five steps:
**scrape** (render Grad Cafe result pages in Chrome), **clean** (parse the
saved HTML into applicant records), **load** (insert them into PostgreSQL,
``ON CONFLICT (p_id) DO NOTHING`` so a repeated pull is a no-op rather than a
duplicate), **query** (answer nine required questions and two original ones,
through raw SQL and again through the SQLAlchemy ORM), and **render** (the
Flask analysis page, read fresh from the database on every request). The
**Pull Data** and **Update Analysis** buttons on the page trigger the first
three steps and the last two, respectively.

Requirements
------------

- Python 3.14.6
- A running PostgreSQL server (developed against 18.6; any reasonably
  recent version works, since the schema uses nothing exotic)
- Chrome, for the scraper, *only* if you intend to run a real Pull Data.
  No test in the suite launches a browser.

Installation
------------

.. code-block:: console

   $ cd module_4
   $ python3 -m venv .venv && source .venv/bin/activate
   $ pip install -r requirements.txt

Environment variables
---------------------

The connection settings come from the environment, populated from a ``.env``
file in ``module_5/`` if one exists (copy ``.env.example``). Both the psycopg
code in ``load_data.py`` and the SQLAlchemy code in ``models.py`` read them.
``DB_HOST``, ``DB_PORT``, and ``DB_NAME`` locate the database. ``DB_USER`` and
``DB_PASSWORD`` are the runtime account the web app and Pull Data use.
``DB_OWNER_USER`` and ``DB_OWNER_PASSWORD`` are a separate owner account for
schema setup and the bulk load, kept out of the running app's environment.

``DATABASE_URL`` is an optional single-URL override, used by CI and tests. It
takes precedence over ``DB_*``, and an explicit ``database_url`` argument takes
precedence over both:

.. code-block:: console

   $ export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/gradcafedb

A bare ``postgresql://`` URL has the ``+psycopg`` driver supplied
automatically. A password containing ``@``, ``/``, or ``:`` must be
percent-encoded by whoever sets the variable; the application decodes it
correctly once it is. A missing ``DB_*`` variable raises ``KeyError`` naming
the variable and never a value.

The libpq ``PG*`` variables Module 3 used are no longer read. The test suite
takes its database from ``TEST_DATABASE_URL``, and
``create_app(database_url=...)`` lets a test override the setting directly,
which is what keeps a test run from ever reaching a developer's real database
by accident; see :doc:`testing`.

Running the application
-----------------------

.. code-block:: console

   $ python3 src/app.py        # http://127.0.0.1:8080/analysis

Port 8080 rather than Flask's default 5000, which macOS's AirPlay Receiver
occupies; set ``PORT`` to override.

Running the tests
------------------

.. code-block:: console

   $ pytest -m "web or buttons or analysis or db or integration"

See :doc:`testing` for markers, fixtures, and test doubles.
