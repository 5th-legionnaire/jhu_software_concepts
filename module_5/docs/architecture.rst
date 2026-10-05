Architecture
============

The service has three layers: web, ETL, and database. Each is built around
one seam that makes it testable without touching a browser or a live
database.

Web layer
---------

:func:`app.create_app` is the application factory, and the seam the whole
test suite hangs on:

.. code-block:: python

   create_app(scraper=None, loader=None, query=None, runner=None,
              database_url=None, testing=False)

Every argument defaults to the real implementation, so ``python3 src/app.py``
is unchanged by any of this. A test passes fakes for some or all of
``scraper``, ``loader``, and ``query`` instead, which is what lets most of
the suite run with no PostgreSQL at all; see :doc:`testing`.

Three routes:

.. list-table::
   :header-rows: 1

   * - Route
     - Method
     - Responses
   * - ``/analysis``, ``/``
     - GET
     - ``200`` the page; ``503`` the page with an error notice
   * - ``/pull-data``
     - POST
     - ``200``/``202`` ``{"ok": true}`` when not busy; ``409`` ``{"busy": true}``
       while busy; ``500`` ``{"ok": false, "error": ...}`` on failure
   * - ``/update-analysis``
     - POST
     - ``200`` ``{"ok": true, "total": n}``; ``409``/``503`` as above

**JSON, not redirects.** Module 3's buttons flashed a message and redirected.
The rubric requires ``POST /update-analysis`` to return ``200`` when not
busy, which a redirect cannot do, and names ``{"ok": true}``/``{"busy":
true}`` literally. Both routes now answer JSON unconditionally; the page's
two buttons call them with ``fetch()`` and reload on success. Content
negotiation on ``Accept`` was considered and rejected: Flask's test client
sends ``Accept: */*`` by default, so the obvious ``client.post("/pull-data")``
would have received a redirect under that design.

**Busy state** lives on a :class:`app.PullState` object at
``app.config["PULL_STATE"]``, with a plain ``busy`` flag a test sets
directly, rather than Module 3's ``subprocess.poll()``. ``POST
/update-analysis`` is gated while busy, which Module 3 did not do; see
:doc:`operations` for why.

The page carries ``data-testid="pull-data-btn"`` and
``data-testid="update-analysis-btn"`` as stable test selectors, and labels
every rendered value ``Answer:``.

ETL layer
---------

``pull_data.scrape_new_records()`` orchestrates the pull: read the database's
newest ``p_id`` (``pull_data._newest_in_database()``), fetch pages until
reaching it (``pull_data._scrape_new_pages()``), parse them
(:func:`clean.clean_data`), filter to genuinely new records, and standardize
them through the instructor-provided LLM (``pull_data._standardize()``).
``pull_data.load_records()`` then inserts them.

Every outward dependency is an injected argument, following one pattern
throughout: ``scrape.py``'s own ``scrape_data()`` (the Module 2 one-time
historical scraper, still present in ``src/`` though the Pull Data button no
longer calls it) gained the identical seams for the identical reason.

.. list-table::
   :header-rows: 1

   * - Argument
     - Why it is separate
   * - ``browser_factory``
     - returns a Selenium driver; real default launches Chrome
   * - ``fetch_html``
     - ``(driver, url) -> html | None``. Separate from ``browser_factory``
       because the real default, ``scrape._fetch_html()``, drives a real
       ``WebDriverWait``; a test for "the page never arrived" through the
       real function would block for a real 30-second timeout
   * - ``sleep``
     - the delay between page requests; a real multi-page test would
       otherwise wait out a real ``PAGE_DELAY``
   * - ``standardize``
     - takes records, returns standardized records or ``None``; real
       default shells out to the LLM

Database layer
---------------

:class:`models.Applicant` maps the ``applicants`` table. ``p_id`` is the
Grad Cafe result id parsed from the entry URL, not a generated sequence
(``autoincrement=False``), and is the primary key; ``url`` additionally
carries a ``UNIQUE`` constraint. Inserts use ``ON CONFLICT (p_id) DO
NOTHING``, which is the whole of the uniqueness policy: a repeated or
overlapping pull reinserts nothing. See :doc:`operations` for what that
means for Pull Data specifically.

Two independent read paths answer the same nine required questions and two
original ones: ``query_data.py`` in raw SQL, and ``orm_queries.py`` through
the ORM. Only the ORM path is wired into the Flask page
(:func:`orm_queries.all_results`, :func:`orm_queries.dataset_summary`); the
raw SQL path exists for its own command line
(``python3 src/query_data.py``) and is never read by the application. Both
share their validity ranges, matching patterns, and output formatters from
``query_data.py``, so the two answers are computed under identical rules.

``models.make_session_factory(database_url)`` is deliberately uncached, so
two callers asking for different URLs reach different databases; this is
what lets ``create_app(database_url=...)`` redirect the whole application.
The cached-for-the-process ``models.get_engine()``/``get_session()`` remain
for the command-line scripts, unchanged from Module 3's single, process-wide
connection.
