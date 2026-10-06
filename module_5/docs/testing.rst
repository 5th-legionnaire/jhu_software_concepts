Testing Guide
=============

Markers
-------

Every test carries at least one marker; unmarked tests are not permitted.
The text below is quoted exactly from ``pytest.ini``, which is itself
quoted from the assignment.

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

Running the suite
------------------

.. code-block:: console

   $ pytest -m "web or buttons or analysis or db or integration"

Stable selectors
-----------------

The analysis page carries two ``data-testid`` attributes, so tests select on
them rather than on CSS classes or text content that styling changes could
break:

- ``data-testid="pull-data-btn"``
- ``data-testid="update-analysis-btn"``

Every rendered analysis value is prefixed ``Answer:`` (as
``<span class="answer-label">Answer:</span>``), and every percentage shown
as page text is formatted to exactly two decimals. Both are asserted
directly in ``test_analysis_format.py``, by parsing the rendered page with
BeautifulSoup rather than matching substrings in raw HTML.

Fixtures and test doubles
---------------------------

All fixtures live in ``tests/conftest.py``. Two application fixtures fake
different amounts of the app, because no single fixture can serve both
halves of the suite:

.. list-table::
   :header-rows: 1

   * - Fixture
     - scraper
     - loader
     - query
     - Needs PostgreSQL
   * - ``app`` / ``client``
     - fake
     - fake (records calls, writes nothing)
     - fake
     - No
   * - ``db_client``
     - fake
     - real, against a truncated test database
     - real, same database
     - Yes

``app``/``client`` serves ``web``, ``buttons``, and ``analysis`` tests.
Faking ``query`` as well as the scraper and loader is what keeps ``POST
/update-analysis`` from reaching PostgreSQL even when a pull is not in
progress, which is what makes all 24 of those tests run in well under a
tenth of a second with no database configured at all. ``db_client`` serves
``db`` and ``integration`` tests; its scraper is still faked, so even these
tests never reach Grad Cafe, but its loader and queries are real, against
the disposable database the ``clean_db`` fixture truncates before and after
each test using ``load_data.create_table`` (the production schema, column
comments and the ``ON CONFLICT`` target included, not a parallel
``Base.metadata.create_all``).

Other fixtures:

- ``fake_rows``: two well-formed applicant records, in the Module 2 JSON key
  format the real scraper returns after standardization. Every required
  schema field is set, which is what lets the same fixture double as what
  the loader expects.
- ``fake_scraper`` / ``failing_scraper``: return ``fake_rows``, or raise, in
  place of the real Grad Cafe pull.
- ``fake_loader``: records the rows it was called with instead of writing
  to PostgreSQL.
- ``fake_query``: a fixed ``{"summary": ..., "results": ...}``, chosen so
  every formatter is exercised, including a percentage that is not already
  round.
- ``db_url``: ``TEST_DATABASE_URL``. There is no default, because a
  credential written into the suite is a credential in the repository. When
  it is unset, offline tests get a URL naming no user or password at an
  unreachable port, so they cannot find a real database, and ``clean_db``
  fails with a message naming the variable.

Beyond the five required files
-------------------------------

``pytest.ini`` scopes ``--cov-fail-under=100`` to all of ``src/``, not only
the code the five required files reach. Two facts about Module 3's own
design mean that is a real gap, not a theoretical one: ``query_data.py``
and ``orm_queries.py`` are independent paths to the same analyses, with
only the ORM one read by the Flask app, and several modules carry a
command-line entry point (each module's ``main()``,
``models._verify_mapping()``, :func:`scrape.scrape_data`) that nothing in
the web app reaches. Five more files close what the required five leave
dark:

.. list-table::
   :header-rows: 1

   * - File
     - Marker
     - What it covers
   * - ``test_pull_pipeline.py``
     - ``buttons``
     - :func:`pull_data.scrape_new_records`'s real orchestration (a fake
       browser and a fake LLM subprocess stand in for the two outward
       dependencies) and :func:`clean.clean_data`'s HTML parsing
   * - ``test_scrape.py``
     - ``buttons``
     - :func:`scrape.scrape_data`, the Module 2 batch scraper, with the
       same injected seams as ``pull_data.py``
   * - ``test_query_data.py``
     - ``db``
     - the raw-SQL analyses, run against a real database rather than a
       fake cursor, so the SQL text itself is proven correct
   * - ``test_orm_queries.py``
     - ``db``
     - the ``--sql`` debug output and ``main()``
   * - ``test_models.py``
     - ``db``
     - the process-cached default session, and ``models._verify_mapping()``,
       which doubles as a genuine proof the ``Applicant`` model still
       matches the live schema

Why the scraper is faked at two different depths
----------------------------------------------------

``test_buttons.py`` fakes the whole ``scraper`` callable at the
``create_app()`` boundary, which is what the assignment itself asks for
("Triggers the loader with the rows from the scraper (should be faked /
mocked)"). That tests the route's contract, not what Pull Data's scraper
actually does when it runs. ``test_pull_pipeline.py`` calls the real
:func:`pull_data.scrape_new_records` instead, with a fake Selenium driver
and a fake LLM subprocess, and proves the real stop-at-the-database's-
newest-entry logic, record filtering, and every error path.

Coverage
--------

.. code-block:: text

   TOTAL  802  0  100%
   Required test coverage of 100% reached. Total coverage: 100.00%
   102 passed

The committed terminal summary is ``coverage_summary.txt``. Nine
``# pragma: no cover`` lines appear in ``src/``, each with a one-line reason
beside it: one per module's ``if __name__ == "__main__":`` block, and one
branch in ``scrape._fetch_html()`` that only a real Selenium timeout, or
standing in for ``WebDriverWait``'s own internal sleep, can reach.

Constraints
-----------

No test touches the live internet, launches a real browser, runs a real
scrape, or calls ``sleep()``. Where a real wait is unavoidable to observe an
asynchronous result (:func:`app.run_in_background`'s daemon thread), the
test uses a :class:`threading.Event` the background job sets, with a
generous timeout only as a hang safety net, rather than a fixed-duration
sleep.
