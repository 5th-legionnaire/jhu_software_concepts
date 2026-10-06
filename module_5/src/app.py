"""
app.py: Flask application that displays the Grad Cafe analysis.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3; see the README for what Module 4 changed.

Contains:
    PullState:            whether a pull is running, and how the last one ended
    run_inline():         run a pull in the request that asked for it
    run_in_background():  run a pull on a daemon thread
    make_query():         the default page read, through the ORM
    make_scraper():       the default scraper, the real Grad Cafe pull
    make_loader():        the default loader, writing to PostgreSQL
    build_sections():     turns query results into display-ready sections
    create_app():         application factory
    index():              the analysis page (routes "/analysis" and "/")
    pull():               Pull Data (route "/pull-data", POST)
    update():             Update Analysis (route "/update-analysis", POST)

Every outward dependency reaches the application as an argument to
create_app(), and every default is the real implementation, so running
`python3 src/app.py` behaves as it did in Module 3. A test passes a fake scraper,
loader, or query instead, and reaches no network and no database.

The two buttons answer JSON rather than redirecting, which is what lets a
caller see a result rather than a 302:

    POST /pull-data        200 {"ok": true, "inserted": n}   finished here
                           202 {"ok": true, "started": true} running in the background
                           409 {"busy": true}                a pull is already running
                           500 {"ok": false, "error": text}  stopped, nothing written
    POST /update-analysis  200 {"ok": true, "total": n}
                           409 {"busy": true}
                           503 {"ok": false, "error": text}  database unreachable

Busy state is a plain attribute on PullState, which the page reads and a test
sets directly. Module 3 inferred it from subprocess.poll(), which no test
could drive without a real subprocess to wait on.

Update Analysis is gated during a pull. Module 3 allowed it, reasoning that
the loader's single transaction makes a concurrent read safe. That is still
true, but a refresh taken mid-pull reports a total that is about to change, so
the pull now has the page to itself and the answer is never half-stale.

Usage (from module_4/):
    python3 src/app.py      # then open http://127.0.0.1:8080/analysis
"""

import os
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template
from sqlalchemy.exc import SQLAlchemyError

from load_data import create_connection, get_db_config
from models import make_session_factory
from orm_queries import all_results, dataset_summary
from pull_data import load_records, run_pull, scrape_new_records
from query_data import fmt_avg, fmt_count, fmt_diff, fmt_pct

# Answers resting on less than this share of the dataset are flagged as thin.
THIN_SHARE = 0.05

DB_UNREACHABLE = ("The database could not be reached. Check that PostgreSQL is running and "
                  "that DATABASE_URL is correct, then try again.")


class PullState:
    """Whether a pull is running, and how the last one ended.

    Replaces Module 3's subprocess handle. A plain attribute is what makes
    busy gating assertable: a test sets ``busy`` and posts, with no subprocess
    to launch and nothing to sleep for.

    Attributes:
        busy: True while a pull is running.
        last: {"state": ..., "text": ...} for the page, or None before the
            first pull of this process.
    """

    def __init__(self):
        self.busy = False
        self.last = None

    def start(self):
        """Mark a pull as running."""
        self.busy = True
        self.last = {"state": "running", "text": "New data is being retrieved from Grad Café."}

    def finish(self, ok, text):
        """Mark the running pull as finished, successfully or not."""
        self.busy = False
        self.last = {"state": "succeeded" if ok else "failed", "text": text}


# Runners: how a pull is executed, which is separate from what it does

def run_inline(job):
    """Run the pull in the request that asked for it and return its result.

    create_app(testing=True) selects this, so a test's POST /pull-data has
    finished pulling by the time it returns. That is what keeps the suite
    deterministic without a sleep() or a poll loop.
    """
    return job()


def run_in_background(job):
    """Start the pull on a daemon thread and return None immediately.

    A real pull renders Grad Cafe pages in Chrome and can take minutes, so the
    request must not block on it. Returning None is how the route knows to
    answer 202 Accepted rather than 200 with a count.
    """
    threading.Thread(target=job, daemon=True).start()
    return None


# Default dependencies: the real implementations create_app() falls back to

def make_query(session_factory):
    """Build the page's database read.

    One callable returning both halves of the page's data, so create_app() can
    take a fake instead. That is what lets the page-rendering and formatting
    tests run with no PostgreSQL at all.

    Returns:
        callable: returns {"summary": ..., "results": ...}.
    """
    def query():
        with session_factory() as session:
            return {"summary": dataset_summary(session), "results": all_results(session)}
    return query


def make_scraper(session_factory):
    """Build the default scraper: the real Grad Cafe pull.

    The scraper reads the newest already-loaded entry to know where to stop,
    and does it through the application's own session factory rather than a
    module-level one, so an app pointed at a test database stays pointed there.
    """
    return lambda: scrape_new_records(session_factory=session_factory)


def make_loader(database_url=None):
    """Build the default loader: insert records into the database the app was given.

    The configuration is read inside the loader rather than here, so creating
    an application never requires connection settings to be present.
    """
    def loader(records):
        config = get_db_config(database_url)
        return load_records(records, connect=lambda: create_connection(config))
    return loader


# Page assembly

def _row(label, value, n=None, detail=None):
    """One displayed answer: a label, its formatted value, and the entries behind it."""
    return {"label": label, "value": value, "n": n, "detail": detail}


def _with_shares(sections, total):
    """Attach each row's share of the dataset, used for the sample-size bar.

    ``share_pct`` is a number because it becomes a CSS bar width.
    ``share_text`` is the same share formatted for reading, and goes through
    fmt_pct like every other percentage on the page: no percentage rendered as
    text is allowed to carry a different precision from the rest.
    """
    for section in sections:
        for item in section["items"]:
            for row in item["rows"]:
                if row["n"] is not None and total:
                    share = row["n"] / total
                    row["share_pct"] = round(100 * share, 2)
                    row["share_text"] = fmt_pct(100 * share)
                    row["thin"] = share < THIN_SHARE
                    row["n_text"] = f"{fmt_count(row['n'])} entries"
                # The line under the bar: the detail when there is one (details state
                # their own counts), otherwise just the number of entries.
                row["basis"] = row["detail"] or row.get("n_text")
    return sections


def build_sections(r, total):
    """Arrange every question's result into the page's two sections."""
    q3 = r["q3"]
    required = [
        {"number": "1",
         "question": "How many entries are from applicants who applied for Fall 2026?",
         "rows": [_row("Fall 2026 applicant count", fmt_count(r["q1"]["count"]), r["q1"]["count"])]},
        {"number": "2",
         "question": "Among entries that provide a nationality classification, what percentage "
                     "are international students?",
         "rows": [_row("Percent international", fmt_pct(r["q2"]["pct"]), r["q2"]["classified"],
                       f"{fmt_count(r['q2']['international'])} international of "
                       f"{fmt_count(r['q2']['classified'])} entries with a nationality")]},
        {"number": "3",
         "question": "What are the average GPA, GRE Quantitative, GRE Verbal, and GRE Analytical "
                     "Writing scores of applicants who provide each metric?",
         "rows": [
             _row("Average GPA", fmt_avg(q3["avg_gpa"]), q3["n_gpa"],
                  f"{fmt_count(q3['n_gpa'])} entries; "
                  f"{fmt_count(q3['x_gpa'])} off-scale values excluded"),
             _row("Average GRE Quantitative", fmt_avg(q3["avg_gre_q"]), q3["n_gre_q"],
                  f"{fmt_count(q3['n_gre_q'])} entries; {fmt_count(q3['x_gre_q'])} excluded, "
                  "most of them combined scores entered in the quantitative field"),
             _row("Average GRE Verbal", fmt_avg(q3["avg_gre_v"]), q3["n_gre_v"],
                  f"{fmt_count(q3['n_gre_v'])} entries; "
                  f"{fmt_count(q3['x_gre_v'])} off-scale values excluded"),
             _row("Average GRE Analytical Writing", fmt_avg(q3["avg_gre_aw"]), q3["n_gre_aw"],
                  f"{fmt_count(q3['n_gre_aw'])} entries; "
                  f"{fmt_count(q3['x_gre_aw'])} off-scale values excluded"),
         ]},
        {"number": "4",
         "question": "What is the average GPA of American applicants who applied for Fall 2026?",
         "rows": [_row("Average GPA, American, Fall 2026", fmt_avg(r["q4"]["avg_gpa"]), r["q4"]["n"])]},
        {"number": "5",
         "question": "What percentage of Fall 2025 entries are acceptances?",
         "rows": [_row("Fall 2025 acceptance percentage", fmt_pct(r["q5"]["pct"]), r["q5"]["total"],
                       f"{fmt_count(r['q5']['accepted'])} accepted of "
                       f"{fmt_count(r['q5']['total'])} Fall 2025 entries, all posted after "
                       "that cycle had largely finished")]},
        {"number": "6",
         "question": "What is the average GPA of accepted applicants who applied for Fall 2026?",
         "rows": [_row("Average GPA, accepted, Fall 2026", fmt_avg(r["q6"]["avg_gpa"]), r["q6"]["n"])]},
        {"number": "7",
         "question": "How many entries are from applicants who applied to Johns Hopkins University "
                     "for a master's degree in Computer Science?",
         "rows": [_row("JHU Masters in Computer Science", fmt_count(r["q7"]["count"]), r["q7"]["count"])]},
        {"number": "8",
         "question": "How many Fall 2026 entries are acceptances for a PhD in Computer Science at "
                     "Georgetown, MIT, Stanford, or Carnegie Mellon, using the original fields?",
         "rows": [_row("Original-field count", fmt_count(r["q9"]["original"]), r["q9"]["original"])]},
        {"number": "9",
         "question": "Repeating Question 8 with the LLM-generated university and program fields, "
                     "how does the count compare?",
         "rows": [
             _row("Original-field count", fmt_count(r["q9"]["original"]), r["q9"]["original"]),
             _row("LLM-field count", fmt_count(r["q9"]["llm"]), r["q9"]["llm"]),
             _row("Difference", fmt_diff(r["q9"]["difference"])),
         ]},
    ]
    user = [
        {"number": "UQ1",
         "question": "Among Fall 2026 entries, do applicants who report a usable GPA post "
                     "acceptances at a different rate from applicants who do not?",
         "rows": [_row(g["group"], fmt_pct(g["pct"]), g["entries"],
                       f"{fmt_count(g['accepted'])} accepted of {fmt_count(g['entries'])} entries")
                  for g in r["uq1"]]},
        {"number": "UQ2",
         "question": "How do Fall 2026 acceptance rates differ between American and International "
                     "applicants, for PhD and Masters programs?",
         "rows": [_row(f"{g['degree']}, {g['nationality']}", fmt_pct(g["pct"]), g["entries"],
                       f"{fmt_count(g['accepted'])} accepted of {fmt_count(g['entries'])} entries")
                  for g in r["uq2"]]},
    ]
    return _with_shares([
        {"title": "Required questions", "items": required},
        {"title": "User questions", "items": user},
    ], total)


def _pull_result_text(inserted):
    """What the page says about a pull that finished without error."""
    if inserted == 0:
        return "Last pull finished. Grad Café had no new entries to add."
    return (f"Last pull finished. Added {fmt_count(inserted)} new entries. "
            "Click Update Analysis to see them in the results.")


def create_app(scraper=None, loader=None, query=None, runner=None,
               database_url=None, testing=False):
    """Build and configure the Flask application.

    Every argument defaults to the real implementation, so running
    `python3 src/app.py` is unchanged from Module 3. Tests pass fakes instead;
    this factory is the seam the whole Module 4 suite hangs on.

    Args:
        scraper: callable returning applicant records. Defaults to the real
            Grad Cafe scraper.
        loader: callable taking records and returning the number inserted.
            Defaults to the real PostgreSQL loader.
        query: callable returning {"summary": ..., "results": ...} for the
            page. Defaults to reading PostgreSQL through the ORM.
        runner: callable taking the pull job and returning its result, or None
            when the job was started in the background. Defaults to
            run_inline when testing, run_in_background otherwise.
        database_url: the database the default query and loader should use.
            Falls back to DATABASE_URL, then to the PG* variables.
        testing: sets Flask's TESTING config and selects the inline runner.

    Returns:
        flask.Flask: the configured application.
    """
    app = Flask(__name__)
    app.config["TESTING"] = testing

    session_factory = make_session_factory(database_url)
    scraper = scraper or make_scraper(session_factory)
    loader = loader or make_loader(database_url)
    query = query or make_query(session_factory)
    runner = runner or (run_inline if testing else run_in_background)

    # Exposed on config so a test can set state.busy directly and so the
    # routes share one object rather than a module-level global.
    state = PullState()
    app.config["PULL_STATE"] = state

    @app.post("/pull-data")
    def pull():
        """Pull newly posted Grad Cafe entries into the database."""
        if state.busy:
            return jsonify(busy=True), 409

        state.start()

        def job():
            """One pull, with the page's status line kept correct either way."""
            try:
                inserted = run_pull(scraper, loader)
            except Exception as failure:  # noqa: BLE001 - reported, not swallowed
                state.finish(False, f"Pull Data stopped. {failure}")
                raise
            state.finish(True, _pull_result_text(inserted))
            return inserted

        try:
            inserted = runner(job)
        except Exception:  # noqa: BLE001 - every failure must answer non-200
            app.logger.exception("Pull Data failed")
            return jsonify(ok=False, error=state.last["text"]), 500

        if inserted is None:
            return jsonify(ok=True, started=True), 202
        return jsonify(ok=True, inserted=inserted), 200

    @app.post("/update-analysis")
    def update():
        """Re-read the analysis from the database. Never starts a scrape."""
        if state.busy:
            return jsonify(busy=True), 409
        try:
            total = query()["summary"]["total"]
        except SQLAlchemyError:
            app.logger.exception("Update Analysis query failed")
            return jsonify(ok=False, error=DB_UNREACHABLE), 503
        return jsonify(ok=True, total=total), 200

    @app.get("/analysis")
    def index():
        """The analysis page, rebuilt from the database on every request."""
        try:
            data = query()
        except SQLAlchemyError:
            app.logger.exception("Analysis query failed")
            return render_template(
                "index.html", error=DB_UNREACHABLE,
                pull_running=state.busy, pull_status=state.last,
            ), 503

        summary = data["summary"]
        return render_template(
            "index.html",
            summary=summary,
            queried_text=datetime.now().strftime("%-I:%M:%S %p"),
            total_text=fmt_count(summary["total"]),
            thin_pct_text=fmt_pct(THIN_SHARE * 100),
            sections=build_sections(data["results"], summary["total"]),
            pull_running=state.busy,
            pull_status=state.last,
        )

    # Module 3 served the page at the root and the rubric names /analysis, so
    # both reach the same view rather than one of them 404ing.
    app.add_url_rule("/", endpoint="root", view_func=index, methods=["GET"])

    return app


if __name__ == "__main__":  # pragma: no cover - command line entry point
    # Port 8080 rather than Flask's default 5000, which macOS's AirPlay Receiver occupies.
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), debug=False)
