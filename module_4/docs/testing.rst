Testing Guide
=============

Markers
-------

Every test carries at least one marker; unmarked tests are not permitted.

========== ====================================================
Marker     Covers
========== ====================================================
``web``    Flask route and page-structure tests
``buttons``"Pull Data" / "Update Analysis" endpoints and gating
``analysis``Label and percentage formatting
``db``     Schema, inserts, selects, uniqueness
``integration`` End-to-end pull -> update -> render
========== ====================================================

Running the suite
-----------------

.. code-block:: console

   $ pytest -m "web or buttons or analysis or db or integration"

Stable selectors
----------------

.. TODO: document data-testid="pull-data-btn" and
   data-testid="update-analysis-btn", and the "Answer:" label convention.

Fixtures and test doubles
-------------------------

.. TODO: document the app/client fixtures, the fake scraper and fake loader
   injected through create_app(), and the test-database fixture.

Coverage
--------

``pytest.ini`` sets ``--cov-fail-under=100`` against ``src/``. The terminal
summary is committed to ``coverage_summary.txt``.
