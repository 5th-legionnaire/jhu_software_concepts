Overview and Setup
==================

What this service does
----------------------

.. TODO: one paragraph: scrape -> clean -> load -> query -> render.

Requirements
------------

.. TODO: Python version, PostgreSQL version, Chrome (for the scraper).

Installation
------------

.. code-block:: console

   $ cd module_4
   $ python3 -m venv .venv && source .venv/bin/activate
   $ pip install -r requirements.txt

Environment variables
---------------------

.. TODO: document DATABASE_URL (primary) and the PG* fallbacks.

``DATABASE_URL``
   SQLAlchemy URL for the PostgreSQL database, e.g.
   ``postgresql+psycopg://user:pass@localhost:5432/gradcafe``.
   Tests override this to point at a disposable test database.

Running the application
-----------------------

.. code-block:: console

   $ python src/app.py        # http://127.0.0.1:8080

Running the tests
-----------------

.. code-block:: console

   $ pytest -m "web or buttons or analysis or db or integration"

See :doc:`testing` for markers, fixtures, and test doubles.
