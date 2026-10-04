"""
pull_data.py: Pull newly posted Grad Cafe entries into PostgreSQL (Part 9).

EN 605.256 Modern Software Concepts in Python, Module 3.
Joshua Latz (jlatz1)

Reuses the Module 2 code rather than reimplementing it:
    1. scrape.py     fetch result pages newer than the newest entry in the database
    2. clean.py      parse them into records, keeping only entries not already loaded
    3. llm_hosting/  standardize program and university, in its own environment
    4. load_data.py  insert them; ON CONFLICT (p_id) DO NOTHING protects existing rows

app.py runs this file as a subprocess and shows the last line it prints on the
page, so every line printed here is written for the person who clicked Pull Data.
It can also be run directly: python3 pull_data.py
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
from load_data import create_connection, get_db_config, load_data
from models import Applicant, get_session

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(MODULE_DIR, "pull_work")          # gitignored
PAGES_DIR = os.path.join(WORK_DIR, "pages")
NEW_RECORDS = os.path.join(WORK_DIR, "new_records.json")
STANDARDIZED = os.path.join(WORK_DIR, "standardized.json")
LOG_PATH = os.path.join(WORK_DIR, "pull_data.log")

LLM_DIR = os.path.join(MODULE_DIR, "llm_hosting")
LLM_PYTHON = os.path.join(LLM_DIR, ".venv", "bin", "python")
LLM_ENV = {"N_GPU_LAYERS": "999", "N_BATCH": "512"}        # tuned in Module 2

RESULT_ID = re.compile(r"/result/(\d+)")


def _newest_in_database():
    """Return (highest p_id, latest date_added) currently in the database."""
    with get_session() as session:
        return session.execute(
            select(func.max(Applicant.p_id), func.max(Applicant.date_added))).one()


def _scrape_new_pages(newest_id, newest_date):
    """Save result pages, newest first, until reaching an entry already in the database.

    Grad Cafe lists entries newest first and result ids increase over time, so
    the first page holding an id at or below the database's highest id is the
    last one with anything new. Returns False if a page could not be fetched.
    """
    shutil.rmtree(PAGES_DIR, ignore_errors=True)
    os.makedirs(PAGES_DIR)
    added_start = (newest_date - timedelta(days=1)).isoformat()
    added_end = (date.today() + timedelta(days=1)).isoformat()

    driver = scrape._start_browser(headless=False)
    page, cursor = 0, None
    try:
        while True:
            print(f"Checking Grad Café for new entries (page {page + 1}).")
            html = scrape._fetch_html(driver, scrape._build_url(added_start, added_end, cursor))
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
            time.sleep(2)                                   # same politeness delay as Module 2
    finally:
        driver.quit()


def _standardize(records):
    """Run the provided LLM standardizer over the new records. Returns True on success."""
    with open(NEW_RECORDS, "w", encoding="utf-8") as out:
        json.dump(records, out, ensure_ascii=False)
    result = subprocess.run(
        [LLM_PYTHON, "app.py", "--file", NEW_RECORDS, "--stdout"],
        cwd=LLM_DIR, env={**os.environ, **LLM_ENV}, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        return False

    # The standardizer may write a JSON array or one JSON object per line.
    text = result.stdout.strip()
    try:
        standardized = json.loads(text)
    except json.JSONDecodeError:
        standardized = [json.loads(line) for line in text.splitlines() if line.strip()]
    with open(STANDARDIZED, "w", encoding="utf-8") as out:
        json.dump(standardized, out, ensure_ascii=False)
    return len(standardized) == len(records)


def main():
    """Run one pull. The last line printed is the result shown on the page."""
    newest_id, newest_date = _newest_in_database()
    if newest_id is None:
        print("The database is empty. Run load_data.py before pulling new entries.")
        return 1

    if not _scrape_new_pages(newest_id, newest_date):
        print("Stopped: Grad Café did not return results. If a verification check appeared, "
              "complete it in the Chrome window, then click Pull Data again. "
              "No entries were added.")
        return 1

    print("Reading the new pages.")
    records = [r for r in clean.clean_data(PAGES_DIR)
               if (m := RESULT_ID.search(r["url"])) and int(m.group(1)) > newest_id]
    if not records:
        print("Grad Café has no new entries since the newest one in the database.")
        return 0

    if not os.path.exists(LLM_PYTHON):
        print("Stopped: the LLM standardizer's environment was not found at llm_hosting/.venv. "
              "Set it up as described in the README (section 3.4). No entries were added.")
        return 1
    print(f"Standardizing {len(records):,} new entries with the LLM.")
    if not _standardize(records):
        print("Stopped: the LLM standardizer failed. No entries were added. "
              "Details are in pull_work/pull_data.log.")
        return 1

    print(f"Adding {len(records):,} new entries to the database.")
    connection = create_connection(get_db_config())
    if connection is None:
        print("Stopped: the database could not be reached. No entries were added.")
        return 1
    try:
        inserted = load_data(connection, STANDARDIZED)
    finally:
        connection.close()
    print(f"Added {inserted:,} new entries. Click Update Analysis to see them in the results.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # keep the last line readable even on an unexpected error
        traceback.print_exc()
        print("Stopped because of an unexpected error. No entries were added. "
              "Details are in pull_work/pull_data.log.")
        sys.exit(1)