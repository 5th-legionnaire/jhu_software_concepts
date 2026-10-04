Architecture
============

The service has three layers.

Web layer
---------

.. TODO: create_app() factory, the three routes, JSON contracts, busy gating,
   the data-testid selectors the UI exposes.

ETL layer
---------

.. TODO: scrape.py renders Grad Cafe pages, clean.py normalizes them,
   load_data.py writes to PostgreSQL. Describe the injection seams used by
   the tests.

Database layer
--------------

.. TODO: models.py (SQLAlchemy ORM), the applicants schema and uniqueness
   policy, orm_queries.py / query_data.py read paths.
