"""
clean.py — turn saved GradCafe pages into structured applicant records.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)
Written for Module 2 and carried over unchanged.

Contains:
    clean_data() — parse saved HTML pages into a list of applicant records
    load_data()  — read records back from a JSON file

Fetching the pages is scrape.py's job. save_data() is imported from scrape.py
so both halves write JSON the same way.

Page structure
--------------
Each applicant occupies two or three consecutive table rows:

    1. a main row with five cells:
       university | program and degree | date added | status | link to entry
    2. a badge row holding term, nationality, GPA and GRE scores
    3. an optional comment row

Only the main row has five cells, so it marks the start of a record. Missing
values are stored as an empty string so every record has the same keys.
"""

import html as html_module
import json
import os
import re

from bs4 import BeautifulSoup

from scrape import RAW_DIR, save_data

SITE_ROOT = "https://www.thegradcafe.com"

# Links to individual applicant entries, e.g. /result/935454
RESULT_LINK = re.compile(r"/result/(\d+)")

# "Fall 2026", "Spring 2027", and so on.
TERM = re.compile(r"(Fall|Spring|Summer|Winter)\s+\d{4}")

# "Accepted on Sep 11" splits into a decision and the date it was given.
STATUS_WITH_DATE = re.compile(r"^(.*?)\s+on\s+(.+)$")

# The keys every record carries, in output order.
FIELDS = (
    "program",
    "program_name",
    "university",
    "comments",
    "date_added",
    "url",
    "status",
    "decision_date",
    "term",
    "US/International",
    "GRE",
    "GRE V",
    "GRE AW",
    "GPA",
    "Degree",
)


def _clean_text(text):
    """Collapse whitespace and decode HTML entities such as &amp; and &#039;."""
    return " ".join(html_module.unescape(text).split())


def _normalize_status(raw):
    """Split a status into the decision and the date it was given.

    "Accepted on Sep 11" becomes ("Accepted", "Sep 11"). A status with no date,
    such as "Wait listed", returns an empty date. The raw text is kept in the
    record as well, so nothing is lost.
    """
    match = STATUS_WITH_DATE.match(raw)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return raw, ""


def _group_rows(tbody):
    """Group table rows into one list of rows per applicant.

    The main row is the one with five cells, so it starts a new group. Badge
    and comment rows that follow belong to the group above them.
    """
    groups = []
    for row in tbody.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 5:
            groups.append([row])
        elif groups:
            groups[-1].append(row)
    return groups


def _parse_badges(rows):
    """Pull term, nationality, GPA and GRE scores out of a group's badge row.

    Badges are short labels such as "Spring 2027", "International", "GPA 3.40",
    "GRE 163", "GRE V 158" and "GRE AW 4". The status is repeated here as a
    badge for small screens, so anything that matches no known pattern is
    ignored. "GRE AW" and "GRE V" are tested before "GRE" because the prefixes
    overlap.
    """
    found = {
        "term": "",
        "US/International": "",
        "GPA": "",
        "GRE": "",
        "GRE V": "",
        "GRE AW": "",
    }

    for row in rows[1:]:
        for badge in row.find_all("div", class_="tw-inline-flex"):
            text = _clean_text(badge.get_text(" ", strip=True))

            if TERM.fullmatch(text):
                found["term"] = text
            elif text in ("International", "American"):
                found["US/International"] = text
            elif text.startswith("GPA"):
                found["GPA"] = text
            elif text.startswith("GRE AW"):
                found["GRE AW"] = text
            elif text.startswith("GRE V"):
                found["GRE V"] = text
            elif text.startswith("GRE"):
                found["GRE"] = text

    return found


def _parse_comment(rows):
    """Return the applicant's comment, or an empty string if there is none.

    The comment row is the extra row that holds no badge elements, which is
    what separates it from the badge row.
    """
    for row in rows[1:]:
        cell = row.find("td")
        if cell and not cell.find("div", class_="tw-inline-flex"):
            return _clean_text(cell.get_text(" ", strip=True))
    return ""


def _parse_entry(rows):
    """Build one applicant record from a group of table rows."""
    cells = rows[0].find_all("td", recursive=False)

    university = _clean_text(cells[0].get_text(" ", strip=True))

    # The program cell holds the program name and the degree in two spans.
    spans = cells[1].find_all("span")
    program_name = _clean_text(spans[0].get_text()) if spans else ""
    degree = _clean_text(spans[1].get_text()) if len(spans) > 1 else ""

    raw_status = _clean_text(cells[3].get_text(" ", strip=True))
    status, decision_date = _normalize_status(raw_status)

    link = cells[4].find("a", href=RESULT_LINK)
    url = SITE_ROOT + link["href"] if link else ""

    record = {
        # Combined program and university text, in the shape the LLM
        # standardizer expects. Kept unmodified for traceability.
        "program": f"{program_name}, {university}" if program_name else university,
        "program_name": program_name,
        "university": university,
        "comments": _parse_comment(rows),
        "date_added": _clean_text(cells[2].get_text(" ", strip=True)),
        "url": url,
        "status": status,
        "decision_date": decision_date,
        "Degree": degree,
    }
    record.update(_parse_badges(rows))

    # Same key order in every record, with anything missing as "".
    return {key: record.get(key, "") for key in FIELDS}


def _parse_page(page_html):
    """Return the applicant records found on one saved page."""
    soup = BeautifulSoup(page_html, "html.parser")

    table = soup.find("table")
    if table is None or table.find("tbody") is None:
        return []

    return [_parse_entry(group) for group in _group_rows(table.find("tbody"))]


def clean_data(raw_dir=RAW_DIR):
    """Parse every saved page into a list of applicant records.

    Records are deduplicated on their entry URL, since date windows can overlap
    slightly at their edges.
    """
    if not os.path.isdir(raw_dir):
        print(f"No saved pages found in {raw_dir}/.")
        return []

    records = []
    seen = set()
    pages = sorted(f for f in os.listdir(raw_dir) if f.endswith(".html"))

    for name in pages:
        with open(os.path.join(raw_dir, name), encoding="utf-8") as page:
            for record in _parse_page(page.read()):
                if record["url"] and record["url"] in seen:
                    continue
                seen.add(record["url"])
                records.append(record)

    print(f"Parsed {len(records)} records from {len(pages)} pages.")
    return records


def load_data(filename="applicant_data.json"):
    """Read applicant records back from a JSON file."""
    with open(filename, encoding="utf-8") as infile:
        records = json.load(infile)
    print(f"Loaded {len(records)} records from {filename}")
    return records


if __name__ == "__main__":  # pragma: no cover - command line entry point
    save_data(clean_data(), "applicant_data.json")