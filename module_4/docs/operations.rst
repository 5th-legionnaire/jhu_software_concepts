Operational Notes
=================

Busy-state policy
-----------------

.. TODO: a pull in progress is observable state, not a sleep. While busy,
   POST /pull-data and POST /update-analysis return 409 {"busy": true} and
   perform no work.

Idempotency and uniqueness
--------------------------

.. TODO: the uniqueness key and what happens on an overlapping re-pull.

Troubleshooting
---------------

.. TODO: common local and CI failures (PostgreSQL not running, DATABASE_URL
   unset, Chrome/ChromeDriver mismatch for the scraper).
