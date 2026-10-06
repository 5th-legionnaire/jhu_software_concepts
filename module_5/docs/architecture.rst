Architecture
============

Three layers, web, ETL and database, each built around one seam that makes it
testable without a browser or a live database. ``dependency.svg`` in the
module folder shows the import structure.

Web layer
---------

:func:`app.create_app` is the application factory:

.. code-block:: python

   create_app(services=None, *, database_url=None, testing=False)

Every outward dependency arrives in one frozen :class:`app.Services` object
(``scraper``, ``loader``, ``query``, ``runner``, ``search``). A field left as
``None`` becomes the real implementation (:func:`app.with_defaults`), so
``python3 src/app.py`` is unchanged from Module 3 while a test names only what
it fakes: ``create_app(Services(search=fake), testing=True)``.

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
     - ``200``/``202`` ``{"ok": true}``; ``409`` ``{"busy": true}`` while a pull runs;
       ``500`` ``{"ok": false, "error": ...}`` on an anticipated failure
   * - ``/update-analysis``
     - POST
     - ``200`` ``{"ok": true, "total": n}``; ``409`` while busy; ``503`` database unreachable
   * - ``/api/applicants``
     - GET
     - ``200`` rows and the effective ``limit``; ``400`` rejected input; ``503`` database unreachable

Any unhandled error answers ``500`` in the same JSON shape, without the
exception's text. Busy state is a plain flag on :class:`app.PullState`; the pull
job clears it in a ``finally`` block, so no failure can leave the app refusing
every later pull. The anticipated failures are
:data:`pull_data.PULL_FAILURES`.

ETL layer
---------

:func:`pull_data.scrape_new_records` orchestrates a pull: read the newest
``p_id`` in the database, fetch pages until reaching it, parse them
(:func:`clean.clean_data`), keep the new records, and standardize them with
the instructor-provided LLM. :func:`pull_data.load_records` inserts them, as the
runtime account, issuing no DDL. :func:`pull_data.run_pull` is the seam the
route and the tests share.

``scrape.py`` exposes the helpers ``pull_data`` uses as a public API
(:func:`scrape.start_browser`, :func:`scrape.fetch_html`, :func:`scrape.build_url`,
:func:`scrape.page_path`, :func:`scrape.next_cursor`), and
:func:`scrape.scrape_data` takes a :class:`scrape.ScrapeWindow` and optional
:class:`scrape.ScrapeOptions`, whose ``browser_factory``, ``fetch_html`` and
``sleep`` fields let a test stand in for Chrome and for waiting.

Database layer
--------------

:class:`models.Applicant` maps the ``applicants`` table. ``p_id`` is the Grad
Cafe result id parsed from the entry URL, and the primary key; inserts use
``ON CONFLICT (p_id) DO NOTHING``. The ``CREATE TABLE`` and the ``INSERT`` are
composed from one column tuple, :data:`load_data.COLUMNS`.

Two read paths answer the same questions: :mod:`query_data` with composed SQL,
whose eleven builders are in :data:`query_data.QUESTIONS`, and
:mod:`orm_queries` through the ORM, which the Flask page uses. Both share
validity ranges and patterns, so the answers are computed under identical
rules. :mod:`db_safety` holds the one definition of the limit, and
:mod:`applicant_search` the search. Connection settings resolve through
:func:`load_data.get_db_config`, which takes a ``role``: ``"app"`` for the
runtime account, ``"owner"`` for schema setup and loading.
