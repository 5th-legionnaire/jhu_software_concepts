"""
pull_data.py: Pull newly posted Grad Cafe entries into PostgreSQL (Part 9).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 3; see the README for what Module 4 changed.

Reuses the Module 2 code rather than reimplementing it:
    1. scrape.py     fetch result pages newer than the newest entry in the database
    2. clean.py      parse them into records, keeping only entries not already loaded
    3. llm_hosting/  standardize program and university, in its own environment
    4. load_data.py  insert them; ON CONFLICT (p_id) DO NOTHING protects existing rows

Contains:
    PullError:            a pull that stopped before writing anything
    run_pull():           the seam the Flask route and the tests share
    scrape_new_records(): the real scraper, steps 1 to 3 above
    load_records():       the real loader, step 4 above
    main():               run one pull from the command line

Module 4 split this file into those seams. Module 3 ran the whole pull as an
opaque subprocess, which no test could drive and no coverage tool could see
into. Now the Flask route calls run_pull() with a scraper and a loader, both of
which default to the real implementations and both of which a test replaces
with a plain callable. Every outward dependency reaches this module as an
argument: the browser, the LLM standardizer, the database connection, and even
the politeness delay between page requests.

Usage (from module_4/):
    python3 src/pull_data.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import date, timedelta

from sqlalchemy import func, select

import clean
import scrape
from load_data import create_connection, create_table, get_db_config, insert_records
from models import Applicant, get_session

# The working directory, the bulk JSON, and the LLM standardizer all live in
# module_4/, one level above this file's src/.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.path.join(PROJECT_DIR, "pull_work")          # gitignored
PAGES_DIR = os.path.join(WORK_DIR, "pages")
NEW_RECORDS = os.path.join(WORK_DIR, "new_records.json")
STANDARDIZED = os.path.join(WORK_DIR, "standardized.json")
LOG_PATH = os.path.join(WORK_DIR, "pull_data.log")

LLM_DIR = os.path.join(PROJECT_DIR, "llm_hosting")
LLM_PYTHON = os.path.join(LLM_DIR, ".venv", "bin", "python")
LLM_ENV = {"N_GPU_LAYERS": "999", "N_BATCH": "512"}        # tuned in Module 2

RESULT_ID = re.compile(r"/result/(\d+)")

# Seconds between page requests, matching Module 2's politeness delay.
PAGE_DELAY = 2


class PullError(RuntimeError):
    """A pull that stopped before loading anything.

    The message is written for the person who clicked Pull Data, because the
    Flask route returns it to the page. Raising rather than returning a code
    is what lets the route answer with a non-200 and an explanation while
    guaranteeing the database was never written to.
    """


def run_pull(scraper, loader):
    """Run one pull: ask the scraper for records, hand them to the loader.

    This is the only path into a pull. The Flask route calls it with the real
    implementations below; a test calls it with two plain callables, so no page
    is rendered and no network request is made. Because the loader runs in a
    single transaction, a scraper that raises leaves the database untouched.

    Args:
        scraper: callable taking no arguments and returning applicant records.
        loader: callable taking those records and returning the number inserted.

    Returns:
        int: rows newly inserted.

    Raises:
        PullError: propagated from the scraper or the loader. Nothing was written.
    """
    return loader(scraper())


# The real scraper: Grad Cafe -> parsed, standardized records

def _newest_in_database(session_factory):
    """Return (highest p_id, latest date_added) currently in the database."""
    with session_factory() as session:
        return session.execute(
            select(func.max(Applicant.p_id), func.max(Applicant.date_added))).one()


def _start_browser():
    """Open the Chrome window Module 2's scraper drives.

    A visible window is deliberate: Grad Cafe sits behind Cloudflare, and a
    verification check has to be cleared by hand the first time.
    """
    return scrape._start_browser(headless=False)


def _scrape_new_pages(newest_id, newest_date, browser_factory, sleep=time.sleep,
                      fetch_html=None):
    """Save result pages, newest first, until reaching an entry already in the database.

    Grad Cafe lists entries newest first and result ids increase over time, so
    the first page holding an id at or below the database's highest id is the
    last one with anything new.

    Args:
        newest_id: highest p_id already in the database.
        newest_date: latest date_added already in the database.
        browser_factory: callable returning a Selenium driver.
        sleep: the delay between page requests. Injected so a test passes a
            no-op rather than waiting, which is why this suite needs no sleep().
        fetch_html: callable(driver, url) returning a page's HTML or None.
            Defaults to scrape._fetch_html, which drives a real Selenium
            WebDriverWait. Injected separately from browser_factory because
            WebDriverWait polls on a real clock: a test exercising the
            "page never arrived" branch through the real function would
            block for its full timeout. A fake here keeps that branch fast
            without touching browser_factory's contract at all.

    Returns:
        bool: False if a page could not be fetched, True otherwise.
    """
    fetch_html = fetch_html or scrape._fetch_html
    shutil.rmtree(PAGES_DIR, ignore_errors=True)
    os.makedirs(PAGES_DIR)
    added_start = (newest_date - timedelta(days=1)).isoformat()
    added_end = (date.today() + timedelta(days=1)).isoformat()

    driver = browser_factory()
    page, cursor = 0, None
    try:
        while True:
            print(f"Checking Grad Café for new entries (page {page + 1}).")
            html = fetch_html(driver, scrape._build_url(added_start, added_end, cursor))
            if html is None:
                return False
            ids = [int(i) for i in RESULT_ID.findall(html)]
            if not ids:
                return True
            page += 1
            with open(scrape._page_path(PAGES_DIR, page), "w", encoding="utf-8") as out:
                out.write(html)
            cursor = scrape._next_cursor(html)
            if min(ids) <= newest_id or cursor is None:
                return True
            sleep(PAGE_DELAY)
    finally:
        driver.quit()


def _standardize(records, run=subprocess.run):
    """Run the provided LLM standardizer over the new records.

    Args:
        records: the records to standardize.
        run: the subprocess runner. Injected so a test can stand in for the
            LLM environment without launching it.

    Returns:
        list[dict] | None: the standardized records, or None if the
        standardizer failed or returned a different number of records than it
        was given.
    """
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(NEW_RECORDS, "w", encoding="utf-8") as out:
        json.dump(records, out, ensure_ascii=False)

    result = run(
        [LLM_PYTHON, "app.py", "--file", NEW_RECORDS, "--stdout"],
        cwd=LLM_DIR, env={**os.environ, **LLM_ENV}, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        return None

    # The standardizer may write a JSON array or one JSON object per line.
    text = result.stdout.strip()
    try:
        standardized = json.loads(text)
    except json.JSONDecodeError:
        standardized = [json.loads(line) for line in text.splitlines() if line.strip()]
    with open(STANDARDIZED, "w", encoding="utf-8") as out:
        json.dump(standardized, out, ensure_ascii=False)

    return standardized if len(standardized) == len(records) else None


def scrape_new_records(session_factory=None, browser_factory=None, standardize=None,
                       fetch_html=None, sleep=time.sleep):
    """Fetch, parse, and standardize every Grad Cafe entry newer than the database's newest.

    This is the default scraper create_app() injects. Each dependency is an
    argument so a test can exercise this orchestration without a browser, an
    LLM, or a network.

    Args:
        session_factory: returns a Session, for reading the newest loaded entry.
        browser_factory: returns a Selenium driver.
        standardize: takes records and returns standardized records, or None.
        fetch_html: callable(driver, url) returning a page's HTML or None.
            See _scrape_new_pages for why this is separate from browser_factory.
        sleep: the delay between page requests, passed through to
            _scrape_new_pages. A test covering more than one page overrides
            this, or it would wait out a real PAGE_DELAY between pages.

    Returns:
        list[dict]: standardized records, empty when Grad Cafe has nothing new.

    Raises:
        PullError: when the database is empty, Grad Cafe did not return
            results, or the standardizer failed. Nothing has been written.
    """
    session_factory = session_factory or get_session
    browser_factory = browser_factory or _start_browser
    standardize = standardize or _standardize

    newest_id, newest_date = _newest_in_database(session_factory)
    if newest_id is None:
        raise PullError("The database is empty. Run load_data.py before pulling new entries.")

    if not _scrape_new_pages(newest_id, newest_date, browser_factory, sleep=sleep,
                             fetch_html=fetch_html):
        raise PullError(
            "Grad Café did not return results. If a verification check appeared, complete "
            "it in the Chrome window, then click Pull Data again. No entries were added.")

    print("Reading the new pages.")
    records = [r for r in clean.clean_data(PAGES_DIR)
               if (m := RESULT_ID.search(r["url"])) and int(m.group(1)) > newest_id]
    if not records:
        return []

    if not os.path.exists(LLM_PYTHON):
        raise PullError(
            "The LLM standardizer's environment was not found at llm_hosting/.venv. Set it "
            "up as described under \"LLM standardizer setup\" in the README. No entries "
            "were added.")

    print(f"Standardizing {len(records):,} new entries with the LLM.")
    standardized = standardize(records)
    if standardized is None:
        raise PullError(
            "The LLM standardizer failed. No entries were added. Details are in "
            "pull_work/pull_data.log.")
    return standardized


# The real loader: records -> PostgreSQL

def load_records(records, connect=None):
    """Insert records into PostgreSQL in one transaction.

    This is the default loader create_app() injects. create_table() runs first
    and is a no-op on an existing table, so a pull against a fresh database
    does not require load_data.py to have been run.

    Args:
        records: standardized applicant records.
        connect: returns an open psycopg connection, or None on failure.

    Returns:
        int: rows newly inserted; 0 when every record was already present.

    Raises:
        PullError: when the database could not be reached. Nothing was written.
    """
    if not records:
        return 0

    connect = connect or (lambda: create_connection(get_db_config()))
    connection = connect()
    if connection is None:
        raise PullError("The database could not be reached. No entries were added.")
    try:
        create_table(connection)
        return insert_records(connection, records)
    finally:
        connection.close()


def main():
    """Run one pull from the command line. Returns the process exit status."""
    try:
        inserted = run_pull(scrape_new_records, load_records)
    except PullError as stopped:
        print(f"Stopped: {stopped}")
        return 1
    if inserted == 0:
        print("Grad Café has no new entries since the newest one in the database.")
        return 0
    print(f"Added {inserted:,} new entries. Click Update Analysis to see them in the results.")
    return 0


if __name__ == "__main__":  # pragma: no cover - command line entry point
    try:
        sys.exit(main())
    except Exception:  # keep the last line readable even on an unexpected error
        traceback.print_exc()
        print("Stopped because of an unexpected error. No entries were added. "
              "Details are in pull_work/pull_data.log.")
        sys.exit(1)
