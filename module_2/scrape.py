"""
scrape.py — GradCafe admissions results scraper.

EN 605.256 Modern Software Concepts in Python, Module 2.
Joshua Latz (jlatz1)

Contains:
    scrape_data() — pull applicant entries from GradCafe
    save_data()   — write entries to a JSON file

Parsing of individual entries and further cleaning live in clean.py.

Pagination note: GradCafe uses cursor pagination. The `cursor` query parameter
is a base64-encoded JSON object holding the sort key of the last row on the
current page. There is no page number, so we follow the site's own "next" link
from each page rather than constructing page URLs ourselves.
"""

import json
import re
import time
from urllib import error, parse, request

from bs4 import BeautifulSoup

BASE_URL = "https://www.thegradcafe.com/survey"

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


def _fetch_html(url):
    """Request a page and return its HTML as a string.

    Returns None if the request fails, so the caller can stop cleanly rather
    than crash partway through a long run.
    """
    if not _is_allowed(url):
        print(f"Skipping disallowed URL: {url}")
        return None

    try:
        page = request.urlopen(url)
    except error.HTTPError as err:
        if err.code == 403:
            print("403 Forbidden. The site is blocking this request.")
        elif err.code == 404:
            print("404 Page not Found!")
        else:
            print(f"An HTTP error has occurred: {err}")
        return None
    except error.URLError as err:
        print(f"Could not reach the site: {err}")
        return None

    html_bytes = page.read()
    return html_bytes.decode("utf-8")


def _next_cursor(soup):
    """Find the cursor token for the next page, or None if there isn't one."""
    for link in soup.find_all("a", href=True):
        query = parse.urlparse(link["href"]).query
        cursor = parse.parse_qs(query).get("cursor")
        if cursor:
            return cursor[0]
    return None


def _parse_entry(row):
    """Pull one applicant's fields out of a results row.

    TODO: fill in once the real page markup has been inspected. The keys below
    are the fields the assignment requires.
    """
    entry = {
        "program": "",
        "university": "",
        "comments": "",
        "date_added": "",
        "url": "",
        "status": "",
        "term": "",
        "US/International": "",
        "GRE": "",
        "GRE V": "",
        "GRE AW": "",
        "GPA": "",
        "Degree": "",
    }
    return entry


def _parse_page(html):
    """Return (entries, next_cursor) for one results page."""
    soup = BeautifulSoup(html, "html.parser")

    # TODO: replace with the actual row container once the markup is known.
    rows = soup.find_all("tr")

    entries = []
    for row in rows:
        link = row.find("a", href=RESULT_LINK)
        if link:
            entries.append(_parse_entry(row))

    return entries, _next_cursor(soup)


def scrape_data(added_start, added_end, max_entries=30000, delay=2):
    """Collect applicant entries from GradCafe within a date window.

    Args:
        added_start: earliest date to include, "YYYY-MM-DD".
        added_end:   latest date to include, "YYYY-MM-DD".
        max_entries: stop once this many entries have been collected.
        delay:       seconds to wait between page requests, to be polite.

    Returns a list of dictionaries, one per applicant.
    """
    entries = []
    cursor = None

    while len(entries) < max_entries:
        url = _build_url(added_start, added_end, cursor)
        html = _fetch_html(url)
        if html is None:
            print("Stopping: the site rejected the request.")
            break

        page_entries, cursor = _parse_page(html)
        if not page_entries:
            print("Stopping: no entries found on this page.")
            break

        entries.extend(page_entries)
        print(f"Collected {len(entries)} entries so far.")

        if cursor is None:
            print("Stopping: no more pages.")
            break

        time.sleep(delay)

    return entries[:max_entries]


def save_data(entries, filename="applicant_data.json"):
    """Write the entries to a JSON file."""
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(entries, outfile, indent=2, ensure_ascii=False)
    print(f"Saved {len(entries)} entries to {filename}")


if __name__ == "__main__":
    data = scrape_data(added_start="2026-01-01", added_end="2026-09-14")
    save_data(data)