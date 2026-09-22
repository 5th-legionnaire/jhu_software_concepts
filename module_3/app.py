"""
app.py: Flask application that displays the Module 3 analysis.

EN 605.256 Modern Software Concepts in Python, Module 3.
Joshua Latz (jlatz1)

Contains:
    create_app():      application factory
    build_sections():  turns ORM results into display-ready sections
    index():           the analysis page (route "/")
    pull():            Pull Data (route "/pull-data", POST), which starts pull_data.py
    update():          Update Analysis (route "/update-analysis", POST), which re-queries

Every database read goes through the SQLAlchemy Applicant model, via the
functions in orm_queries.py; no query logic is duplicated in the routes.
Results are read on every request, so the page always reflects the current
contents of PostgreSQL.

Pull Data runs pull_data.py as a subprocess, so a pull that takes minutes
never blocks the page. The app keeps the subprocess handle and will not start
another pull while that one is still running.

Update Analysis re-reads every result from PostgreSQL and never starts a
scrape. It is safe during a pull, because the loader commits in a single
transaction: a read sees the database either before or after the new
entries, never halfway.

Usage:
    python3 app.py      # then open http://127.0.0.1:8080
"""

import os
import subprocess
import sys
from datetime import datetime

from flask import Flask, flash, redirect, render_template, session, url_for
from sqlalchemy.exc import SQLAlchemyError

from models import get_session
from orm_queries import all_results, dataset_summary
from query_data import fmt_avg, fmt_count, fmt_diff, fmt_pct

# Answers resting on less than this share of the dataset are flagged as thin.
THIN_SHARE = 0.05

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PULL_SCRIPT = os.path.join(MODULE_DIR, "pull_data.py")
PULL_LOG = os.path.join(MODULE_DIR, "pull_work", "pull_data.log")


def _row(label, value, n=None, detail=None):
    """One displayed answer: a label, its formatted value, and the entries behind it."""
    return {"label": label, "value": value, "n": n, "detail": detail}


def _with_shares(sections, total):
    """Attach each row's share of the dataset, used for the sample-size bar."""
    for section in sections:
        for item in section["items"]:
            for row in item["rows"]:
                if row["n"] is not None and total:
                    share = row["n"] / total
                    row["share_pct"] = round(100 * share, 1)
                    row["thin"] = share < THIN_SHARE
                    row["n_text"] = f"{fmt_count(row['n'])} entries"
                # The line under the bar: the detail when there is one (details state
                # their own counts), otherwise just the number of entries.
                row["basis"] = row["detail"] or row.get("n_text")
    return sections


def build_sections(r, total):
    """Arrange every question's ORM result into the page's two sections."""
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


def _last_line(path):
    """The last non-blank line of a file: pull_data.py's latest progress or result."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
    except OSError:
        return ""
    return lines[-1] if lines else ""


def create_app():
    """Build and configure the Flask application."""
    app = Flask(__name__)
    # Signs the one-time notices shown after a button press.
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)
    app.config["PULL_PROCESS"] = None

    def pull_running():
        """True while the Pull Data subprocess this app started is still running."""
        process = app.config["PULL_PROCESS"]
        return process is not None and process.poll() is None

    def pull_status():
        """What to show about the latest pull, or None if none has run since the app started."""
        process = app.config["PULL_PROCESS"]
        if process is None:
            return None
        line = _last_line(PULL_LOG) or "Starting."
        if process.poll() is None:
            return {"state": "running", "text": f"New data is being retrieved. {line}"}
        if process.returncode == 0:
            return {"state": "succeeded", "text": f"Last pull finished. {line}"}
        return {"state": "failed", "text": line}

    @app.post("/pull-data")
    def pull():
        if pull_running():
            flash("Pull Data is already running, so it was not started again. The status "
                  "below shows its progress.", "warning")
            return redirect(url_for("index"))
        os.makedirs(os.path.dirname(PULL_LOG), exist_ok=True)
        with open(PULL_LOG, "w", encoding="utf-8") as log:
            app.config["PULL_PROCESS"] = subprocess.Popen(
                [sys.executable, "-u", PULL_SCRIPT], cwd=MODULE_DIR,
                stdout=log, stderr=subprocess.STDOUT)
        flash("Pull Data started. A Chrome window will open while it checks Grad Café. "
              "The results below still show the data from before this pull.", "info")
        return redirect(url_for("index"))

    @app.post("/update-analysis")
    def update():
        """Re-query the database for the latest results. Never starts a scrape."""
        try:
            with get_session() as db:
                total = dataset_summary(db)["total"]
        except SQLAlchemyError:
            flash("The analysis could not be updated because the database could not be "
                  "reached. Check that PostgreSQL is running, then try again.", "warning")
            return redirect(url_for("index"))

        previous = session.get("shown_total")
        if previous is None or total == previous:
            change = f"The database holds {fmt_count(total)} entries, the same as before."
        else:
            change = (f"The database now holds {fmt_count(total)} entries, "
                      f"{fmt_count(total - previous)} more than before.")

        if pull_running():
            flash("New data is currently being retrieved by Pull Data, so these results may "
                  "not include it yet. The pull was left running. " + change + " Click Update "
                  "Analysis again after the pull finishes to include its new entries.",
                  "warning")
        else:
            flash("Analysis updated with the latest data in the database. " + change, "info")
        # The redirect re-renders the page, which re-runs every query.
        return redirect(url_for("index"))

    @app.route("/")
    def index():
        running, status = pull_running(), pull_status()
        try:
            with get_session() as db:
                summary = dataset_summary(db)
                results = all_results(db)
        except SQLAlchemyError:
            app.logger.exception("Analysis query failed")
            return render_template(
                "index.html",
                error="The database could not be reached. Check that PostgreSQL is running "
                      "and that the connection settings in .env are correct, then reload "
                      "this page.",
                pull_running=running, pull_status=status,
            ), 503
        session["shown_total"] = summary["total"]
        return render_template(
            "index.html",
            summary=summary,
            queried_text=datetime.now().strftime("%-I:%M:%S %p"),
            total_text=fmt_count(summary["total"]),
            thin_pct=int(THIN_SHARE * 100),
            sections=build_sections(results, summary["total"]),
            pull_running=running,
            pull_status=status,
        )

    return app


if __name__ == "__main__":
    # Port 8080 rather than Flask's default 5000, which macOS's AirPlay Receiver occupies.
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), debug=False)