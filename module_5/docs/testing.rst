Testing Guide
=============

Running the suite
-----------------

.. code-block:: console

   $ pytest

Every collected test runs; there is no marker selection, and coverage of
``src/`` must be 100%. The suite never reads your ``.env`` into the environment,
only ``TEST_DATABASE_URL`` and ``TEST_ADMIN_DATABASE_URL``, by name, so a local run
sees what CI sees. ``db`` and ``integration`` tests need those URLs to name a
disposable database, as the runtime and the owner account; everything else
needs no database. No test touches the internet, launches a browser, runs a
real scrape, or calls ``sleep()``.

Markers
-------

Every test carries at least one of these, and a collection hook in
``tests/conftest.py`` stops the run if one does not:

.. list-table::
   :header-rows: 1

   * - Marker
     - Covers
   * - ``web``
     - Flask route/page tests
   * - ``buttons``
     - "Pull Data" and "Update Analysis" behavior
   * - ``analysis``
     - formatting/rounding of analysis output
   * - ``db``
     - database schema/inserts/selects
   * - ``integration``
     - end-to-end flows
   * - ``security``
     - SQL safety, least privilege, and repository policy checks

What the Module 5 tests prove
-----------------------------

.. list-table::
   :header-rows: 1

   * - Files
     - Proves
   * - ``test_sql_guard.py``, ``test_db_safety.py``
     - no SQL built from strings; only composed statements reach the driver;
       every SELECT has a bounded ``LIMIT``
   * - ``test_sqli_malicious.py``, ``test_applicant_search.py``
     - the search contract, and 51 hostile inputs that never produce a ``500``,
       a leak, or every row
   * - ``test_least_privilege.py``, ``test_database_scripts.py``
     - the two accounts are what the database says they are; no cleartext
       password is sent or documented
   * - ``test_query_data.py``, ``test_orm_queries.py``
     - answers equal Module 4's over all 30,000 rows; the ORM's compiled SQL is
       Module 4's plus one ``LIMIT``
   * - ``test_config.py``, ``test_packaging.py``
     - configuration precedence and messages; the lock covers ``setup.py``
   * - ``test_lint_policy.py``, ``test_gate_checkers.py``
     - Pylint is 10.00 with nothing relaxed; the repository's own checks reject
       what they should
   * - ``test_dependency_graph.py``, ``test_snyk_scan.py``, ``test_ci_config.py``
     - the graph is current; the Snyk fixes stay fixed; CI keeps its gates

The Module 4 files (page, buttons, formatting, loader, pull pipeline,
scraper) remain, updated where Module 5 changed an interface.

Fixtures
--------

``tests/conftest.py`` holds them. ``app``/``client`` fake the scraper, loader
and query, so page, button and formatting tests need no database.
``db_client`` keeps the scraper fake and the loader and query real. ``clean_db``
builds the schema and truncates the table before and after a test, as the
owner account, because the runtime account is not allowed to.

The phase gate
--------------

``scripts/gate.sh N`` is the exit gate for each development phase: the suite,
markers, Pylint, inline disables, secrets, the Change Register, and checks
specific to the phase. See the README's Development process section.
