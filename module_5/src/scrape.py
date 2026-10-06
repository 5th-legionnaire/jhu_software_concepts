"""
scrape.py — GradCafe admissions results scraper.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 2. Module 4 adds browser_factory, fetch_html, and sleep
injection seams to scrape_data(), for the same reason pull_data.py added the
same seams: so a test can stand in for Chrome and for waiting, without
launching a real browser or calling sleep(). The scraping logic itself is
unchanged.

Contains:
    scrape_data() — pull raw result pages from GradCafe and save them
    save_data()   — write records to a JSON file

Turning the saved pages into applicant records is clean.py's job.

Approach
--------
This is a hybrid workflow:
    1. urllib builds, inspects, and manages the Grad Cafe URLs.
    2. Selenium renders each page in a real Chrome browser.
    3. The rendered HTML is written to disk.
    4. clean.py parses those files with BeautifulSoup and regex.

Selenium is needed because a plain urllib request to the survey page returns
HTTP 403: the site sits behind Cloudflare. Selenium is used only to render
publicly accessible pages, never to bypass the verification itself. The
verification is cleared once, by hand, in a persistent Chrome profile, and the
resulting cookie is reused on later runs the same way an ordinary browser would
reuse it.

Saving the raw HTML before parsing means a run can be resumed instead of
restarted, and means the pages can be re-parsed later without scraping again.

Pagination note: GradCafe uses cursor pagination. The `cursor` query parameter
is a base64-encoded JSON object holding the sort key of the last row on the
current page, so there is no page number to increment. The scraper follows the
site's own "Next" link from each page instead.
"""

import json
import os
import re
import time
from urllib import parse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://www.thegradcafe.com/survey"

# Chrome profile that holds the Cloudflare clearance cookie. Using a persistent
# profile is what keeps the verification from reappearing on every run.
PROFILE_DIR = os.path.expanduser("~/.gradcafe-chrome-profile")

# Where raw page HTML is saved.
RAW_DIR = "raw_pages"

# Paths disallowed by robots.txt. Checked before every request.
DISALLOWED_PREFIXES = (
    "/signin",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/confirm-password",
    "/verify-email",
    "/profile",
)

# Links to individual applicant entries, e.g. /result/935454
RESULT_LINK = re.compile(r"/result/(\d+)")

# Text that appears on a Cloudflare verification page rather than results.
CHALLENGE_MARKERS = (
    "Just a moment",
    "Verifying you are human",
    "cf-browser-verification",
)

PAGE_TIMEOUT = 30


def _build_url(added_start, added_end, cursor=None):
    """Build a survey URL for a date window, optionally at a cursor position."""
    params = {
        "added_start": added_start,
        "added_end": added_end,
        "sort": "newest",
    }
    if cursor:
        params["cursor"] = cursor
    return BASE_URL + "?" + parse.urlencode(params)


def _is_allowed(url):
    """Return True if the URL is not disallowed by robots.txt."""
    path = parse.urlparse(url).path
    return not path.startswith(DISALLOWED_PREFIXES)


def _is_challenge(html):
    """Return True if the page is a Cloudflare check rather than results."""
    if RESULT_LINK.search(html):
        return False
    return any(marker in html for marker in CHALLENGE_MARKERS)


def _count_entries(html):
    """Count the applicant entries linked from a page of results."""
    return len(set(RESULT_LINK.findall(html)))


def _next_cursor(html):
    """Find the cursor token for the next page, or None if there isn't one.

    The pagination control labels the forward link "Next", and its href carries
    the cursor for the following page. This is navigation only; the applicant
    data itself is parsed in clean.py.
    """
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        if link.get_text(strip=True) != "Next":
            continue
        cursor = parse.parse_qs(parse.urlparse(link["href"]).query).get("cursor")
        if cursor:
            return cursor[0]
    return None


def _start_browser(headless=False):
    """Open Chrome using the persistent profile.

    Headless is off by default. The first run needs a visible window so the
    Cloudflare verification can be cleared by hand.
    """
    options = Options()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--profile-directory=Default")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


def _fetch_html(driver, url):
    """Load a page in the browser and return its HTML.

    Waits for an applicant result link to appear rather than sleeping for a
    fixed time, so the page is not read before it has finished rendering.
    Returns None if the page never loads or comes back as a Cloudflare check.
    """
    if not _is_allowed(url):
        print(f"Skipping disallowed URL: {url}")
        return None

    driver.get(url)

    try:
        WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/result/"]'))
        )
    # Reaching this branch for real means either a real browser genuinely
    # timing out or standing in for WebDriverWait's own internal sleep; both
    # are excluded by this suite's no-real-browser, no-sleep() constraints.
    # pull_data.py injects fetch_html precisely so production code reaches
    # this line while tests never do.
    except TimeoutException:  # pragma: no cover - real Selenium wait, see above
        if _is_challenge(driver.page_source):
            print("Cloudflare verification appeared. Clear it in the browser "
                  "window, then run the script again to resume.")
        else:
            print(f"Timed out waiting for results on: {url}")
        return None

    return driver.page_source


def _page_path(out_dir, number):
    """Path for a saved page, numbered in the order it was fetched."""
    return os.path.join(out_dir, f"page_{number:04d}.html")


def _resume(out_dir):
    """Work out where a previous run stopped.

    Reads the pages already on disk and returns (page_count, entry_count,
    next_cursor) so a rerun picks up where it left off instead of starting
    over. Returns a cursor of None when there is nothing saved yet.
    """
    if not os.path.isdir(out_dir):
        return 0, 0, None

    pages = sorted(f for f in os.listdir(out_dir) if f.startswith("page_"))
    if not pages:
        return 0, 0, None

    entries = 0
    cursor = None
    for name in pages:
        with open(os.path.join(out_dir, name), encoding="utf-8") as saved:
            html = saved.read()
        entries += _count_entries(html)
        cursor = _next_cursor(html)

    print(f"Resuming: {len(pages)} pages and {entries} entries already saved.")
    return len(pages), entries, cursor


def scrape_data(added_start, added_end, max_entries=30000, out_dir=RAW_DIR,
                delay=2, headless=False, browser_factory=None, fetch_html=None,
                sleep=time.sleep):
    """Save raw GradCafe result pages for one date window.

    Args:
        added_start: earliest date to include, "YYYY-MM-DD".
        added_end:   latest date to include, "YYYY-MM-DD".
        max_entries: stop once this many applicant entries have been saved.
        out_dir:     directory to write page HTML into.
        delay:       seconds to wait between page requests, to be polite.
        headless:    run Chrome without a window. Leave False on the first run.
        browser_factory: callable returning a Selenium driver. Defaults to
            _start_browser(headless=headless). Injected so a test can stand
            in for Chrome, the same seam pull_data.py uses for Pull Data.
        fetch_html: callable(driver, url) returning a page's HTML or None.
            Defaults to _fetch_html. See _fetch_html's own docstring for why
            this is the one piece a test replaces rather than drives for real.
        sleep: the delay between page requests. Injected so a test passes a
            no-op rather than waiting out a real `delay` between pages.

    Returns the number of applicant entries saved.
    """
    browser_factory = browser_factory or (lambda: _start_browser(headless=headless))
    fetch_html = fetch_html or _fetch_html

    os.makedirs(out_dir, exist_ok=True)
    page_count, entry_count, cursor = _resume(out_dir)

    driver = browser_factory()
    try:
        while entry_count < max_entries:
            url = _build_url(added_start, added_end, cursor)
            html = fetch_html(driver, url)
            if html is None:
                print("Stopping: could not retrieve the page.")
                break

            found = _count_entries(html)
            if found == 0:
                print("Stopping: no entries found on this page.")
                break

            page_count += 1
            entry_count += found
            with open(_page_path(out_dir, page_count), "w", encoding="utf-8") as out:
                out.write(html)
            print(f"Saved page {page_count} ({entry_count} entries so far).")

            cursor = _next_cursor(html)
            if cursor is None:
                print("Stopping: no more pages.")
                break

            sleep(delay)
    finally:
        driver.quit()

    return entry_count


def save_data(records, filename="applicant_data.json"):
    """Write records to a JSON file.

    Also imported by clean.py, which produces the records this writes.
    """
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(records, outfile, indent=2, ensure_ascii=False)
    print(f"Saved {len(records)} records to {filename}")


if __name__ == "__main__":  # pragma: no cover - command line entry point
    total = scrape_data(added_start="2026-01-01", added_end="2026-09-14")
    print(f"Done. {total} entries saved under {RAW_DIR}/.")