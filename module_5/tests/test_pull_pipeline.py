"""Pull Data's actual pipeline: scraper orchestration and HTML parsing.

Rubric: pytest.ini's own text defines the buttons marker as "'Pull Data' and
'Update Analysis' behavior," not Flask-route behavior specifically.
test_buttons.py covers the route's contract (status codes, JSON shape, busy
gating) with the whole scraper faked out, exactly as the assignment asks for
("should be faked / mocked"). This file covers what Pull Data actually does
once it runs: pull_data.scrape_new_records()'s real stop condition, record
filtering, and error paths, pull_data._standardize()'s handling of the LLM
subprocess's output, and clean.py's real HTML parsing. A fake browser and a
fake LLM process stand in for the two outward dependencies; nothing here
launches Chrome, an LLM, or a network request, and nothing calls sleep().
"""

import datetime
import json

import pytest

import clean
import pull_data as pd
import scrape as scrape_module
from clean import clean_data
from pull_data import PullError, _standardize, load_records, scrape_new_records

pytestmark = pytest.mark.buttons


# --- Fakes for the dependencies scrape_new_records and _standardize take ---

class _FakeDriver:
    """Enough of a Selenium driver for _scrape_new_pages: nothing but quit().

    fetch_html is faked separately (see module docstring), so this driver
    never has get() or find_element() called on it.
    """
    def quit(self):
        pass


class _FakeSession:
    """Enough of a SQLAlchemy Session for _newest_in_database: one canned row.

    _newest_in_database only ever does session.execute(a_select).one(), so a
    session that ignores the statement and returns a fixed row satisfies its
    whole contract without a real database.
    """
    def __init__(self, newest_id, newest_date):
        self._value = (newest_id, newest_date)

    def execute(self, _statement):
        return self

    def one(self):
        return self._value

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _session_factory(newest_id, newest_date=None):
    newest_date = newest_date or datetime.date(2026, 9, 1)
    return lambda: _FakeSession(newest_id, newest_date)


class _FetchQueue:
    """Returns canned HTML pages in order, standing in for scrape._fetch_html."""
    def __init__(self, pages):
        self._pages = list(pages)

    def __call__(self, _driver, _url):
        return self._pages.pop(0) if self._pages else None


def _entry_row(p_id, university="Johns Hopkins University",
               program="Computer Science", degree="Masters",
               date_added="Sep 12, 2026", status="Accepted on Sep 10",
               term="Fall 2026", nationality="American", gpa="3.80"):
    """One applicant's table rows, in the shape clean.py parses: a five-cell
    main row (the result id lives in its link) and a badge row."""
    return f"""
    <tr>
      <td>{university}</td>
      <td><span>{program}</span><span>{degree}</span></td>
      <td>{date_added}</td>
      <td>{status}</td>
      <td><a href="/result/{p_id}">See more</a></td>
    </tr>
    <tr><td>
      <div class="tw-inline-flex">{term}</div>
      <div class="tw-inline-flex">{nationality}</div>
      <div class="tw-inline-flex">GPA {gpa}</div>
    </td></tr>
    """


def _page(rows, next_cursor=None):
    """A full saved page: the result table, plus a Next link if there is one."""
    next_link = f'<a href="/survey?cursor={next_cursor}">Next</a>' if next_cursor else ""
    return f"<html><body><table><tbody>{rows}</tbody></table>{next_link}</body></html>"


def _echo_standardize(records):
    """Stands in for the LLM: adds the two generated fields, changes nothing else.

    Lets a test assert on exactly which records scrape_new_records handed to
    the standardizer, by checking what comes back.
    """
    return [
        {**r, "llm-generated-program": r["program_name"],
         "llm-generated-university": r["university"]}
        for r in records
    ]


# --- scrape_new_records: the orchestration ----------------------------------

def test_empty_database_raises_pull_error():
    """No prior entries means nothing to compare against: stop before scraping."""
    with pytest.raises(PullError, match="database is empty"):
        scrape_new_records(session_factory=_session_factory(None, None),
                           browser_factory=_FakeDriver, fetch_html=_FetchQueue([]))


def test_failed_fetch_raises_pull_error():
    """Grad Café not responding (or a verification check) stops the pull."""
    with pytest.raises(PullError, match="Grad Café did not return results"):
        scrape_new_records(session_factory=_session_factory(9000000),
                           browser_factory=_FakeDriver, fetch_html=_FetchQueue([None]))


def test_nothing_new_returns_empty_list():
    """Every id on the first page is already in the database: nothing to add."""
    page = _page(_entry_row(p_id=9000000))
    result = scrape_new_records(session_factory=_session_factory(9000000),
                                browser_factory=_FakeDriver, fetch_html=_FetchQueue([page]))
    assert result == []


def test_stops_at_the_database_newest_id_across_pages(tmp_path, monkeypatch):
    """Keeps following Next until it reaches an id already in the database.

    Two pages: the first holds two new entries and a Next link, the second
    holds the database's newest id, which is where the loop must stop.
    """
    monkeypatch.setattr("pull_data.PAGES_DIR", str(tmp_path / "pages"))
    # LLM_PYTHON is checked unconditionally, even with standardize faked, so
    # it must point at some existing file rather than the real (and in CI,
    # absent) llm_hosting/.venv.
    monkeypatch.setattr("pull_data.LLM_PYTHON", __file__)

    page_1 = _page(_entry_row(p_id=9000003) + _entry_row(p_id=9000002), next_cursor="p2")
    page_2 = _page(_entry_row(p_id=9000001))  # the database's newest id

    records = scrape_new_records(
        session_factory=_session_factory(9000001),
        browser_factory=_FakeDriver,
        fetch_html=_FetchQueue([page_1, page_2]),
        standardize=_echo_standardize,
        sleep=lambda _seconds: None,  # two pages means one real PAGE_DELAY otherwise
    )

    ids = {r["url"].rsplit("/", 1)[-1] for r in records}
    assert ids == {"9000003", "9000002"}
    assert all("llm-generated-program" in r for r in records)


def test_scrape_new_pages_stops_when_a_page_has_no_result_links(tmp_path, monkeypatch):
    """Distinct from "nothing new": this page has no results at all, not
    merely results already in the database."""
    monkeypatch.setattr("pull_data.PAGES_DIR", str(tmp_path / "pages"))
    result = scrape_new_records(
        session_factory=_session_factory(9000000),
        browser_factory=_FakeDriver,
        fetch_html=_FetchQueue(["<html><body>no results here</body></html>"]))
    assert result == []


def test_scrape_new_records_raises_when_the_standardizer_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("pull_data.PAGES_DIR", str(tmp_path / "pages"))
    monkeypatch.setattr("pull_data.LLM_PYTHON", __file__)
    page = _page(_entry_row(p_id=9000002))

    with pytest.raises(PullError, match="LLM standardizer failed"):
        scrape_new_records(
            session_factory=_session_factory(9000001),
            browser_factory=_FakeDriver,
            fetch_html=_FetchQueue([page]),
            standardize=lambda records: None)


def test_missing_llm_environment_raises_pull_error(tmp_path, monkeypatch):
    """A standardizer environment that was never set up stops the pull."""
    monkeypatch.setattr("pull_data.PAGES_DIR", str(tmp_path / "pages"))
    monkeypatch.setattr("pull_data.LLM_PYTHON", str(tmp_path / "does-not-exist"))

    page = _page(_entry_row(p_id=9000002))
    with pytest.raises(PullError, match="LLM standardizer's environment was not found"):
        scrape_new_records(session_factory=_session_factory(9000001),
                           browser_factory=_FakeDriver, fetch_html=_FetchQueue([page]))


# --- _standardize: the LLM subprocess's output, without the LLM ------------

class _FakeCompletedProcess:
    """The slice of subprocess.CompletedProcess _standardize reads."""
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_standardize_parses_a_json_array(tmp_path, monkeypatch):
    monkeypatch.setattr("pull_data.WORK_DIR", str(tmp_path))
    monkeypatch.setattr("pull_data.NEW_RECORDS", str(tmp_path / "new_records.json"))
    monkeypatch.setattr("pull_data.STANDARDIZED", str(tmp_path / "standardized.json"))
    records = [{"program": "Computer Science"}]
    stdout = json.dumps([{"program": "Computer Science", "llm-generated-program": "CS"}])

    result = _standardize(records, run=lambda *a, **k: _FakeCompletedProcess(stdout=stdout))

    assert result == [{"program": "Computer Science", "llm-generated-program": "CS"}]


def test_standardize_parses_json_lines(tmp_path, monkeypatch):
    """The standardizer may write one JSON object per line instead of an array."""
    monkeypatch.setattr("pull_data.WORK_DIR", str(tmp_path))
    monkeypatch.setattr("pull_data.NEW_RECORDS", str(tmp_path / "new_records.json"))
    monkeypatch.setattr("pull_data.STANDARDIZED", str(tmp_path / "standardized.json"))
    records = [{"program": "A"}, {"program": "B"}]
    stdout = '{"program": "A"}\n{"program": "B"}\n'

    result = _standardize(records, run=lambda *a, **k: _FakeCompletedProcess(stdout=stdout))

    assert result == [{"program": "A"}, {"program": "B"}]


def test_standardize_returns_none_on_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.setattr("pull_data.WORK_DIR", str(tmp_path))
    monkeypatch.setattr("pull_data.NEW_RECORDS", str(tmp_path / "new_records.json"))

    result = _standardize(
        [{"program": "A"}],
        run=lambda *a, **k: _FakeCompletedProcess(returncode=1, stderr="standardizer crashed"))

    assert result is None


def test_standardize_returns_none_on_record_count_mismatch(tmp_path, monkeypatch):
    """A length mismatch means the output does not line up with the input, 1:1."""
    monkeypatch.setattr("pull_data.WORK_DIR", str(tmp_path))
    monkeypatch.setattr("pull_data.NEW_RECORDS", str(tmp_path / "new_records.json"))
    monkeypatch.setattr("pull_data.STANDARDIZED", str(tmp_path / "standardized.json"))
    records = [{"program": "A"}, {"program": "B"}]
    stdout = json.dumps([{"program": "A"}])  # only one record back for two given

    result = _standardize(records, run=lambda *a, **k: _FakeCompletedProcess(stdout=stdout))

    assert result is None


# --- clean.py: real HTML, no scraping involved ------------------------------

def test_clean_data_parses_saved_pages(tmp_path):
    """A saved page parses into the fields load_data._prepare_record expects."""
    page = _page(_entry_row(p_id=9000001, university="Stanford University",
                            program="Electrical Engineering", degree="PhD",
                            nationality="International", gpa="3.90"))
    (tmp_path / "page_0001.html").write_text(page, encoding="utf-8")

    records = clean_data(str(tmp_path))

    assert len(records) == 1
    record = records[0]
    assert record["url"] == "https://www.thegradcafe.com/result/9000001"
    assert record["university"] == "Stanford University"
    assert record["program_name"] == "Electrical Engineering"
    assert record["Degree"] == "PhD"
    assert record["status"] == "Accepted"
    assert record["decision_date"] == "Sep 10"
    assert record["term"] == "Fall 2026"
    assert record["US/International"] == "International"
    assert record["GPA"] == "GPA 3.90"


def test_clean_data_deduplicates_by_url(tmp_path):
    """Overlapping date windows can save the same entry on two pages."""
    entry = _entry_row(p_id=9000001)
    (tmp_path / "page_0001.html").write_text(_page(entry), encoding="utf-8")
    (tmp_path / "page_0002.html").write_text(_page(entry), encoding="utf-8")

    assert len(clean_data(str(tmp_path))) == 1


def test_clean_data_handles_a_dateless_status_full_gre_badges_and_a_comment(tmp_path):
    """_entry_row above is deliberately minimal; this exercises what it never
    does: a status with no "on <date>" suffix, all three GRE badges (GRE AW
    and GRE V must be checked before the plain GRE prefix they overlap), and
    a comment row distinguished from the badge row by having no badge divs.
    """
    page = """
    <html><body><table><tbody>
    <tr>
      <td>Carnegie Mellon University</td>
      <td><span>Computer Science</span><span>PhD</span></td>
      <td>Sep 12, 2026</td>
      <td>Wait listed</td>
      <td><a href="/result/9000005">See more</a></td>
    </tr>
    <tr><td>
      <div class="tw-inline-flex">Fall 2026</div>
      <div class="tw-inline-flex">American</div>
      <div class="tw-inline-flex">GPA 3.70</div>
      <div class="tw-inline-flex">GRE 165</div>
      <div class="tw-inline-flex">GRE V 160</div>
      <div class="tw-inline-flex">GRE AW 5</div>
    </td></tr>
    <tr><td>Great campus visit, friendly faculty.</td></tr>
    </tbody></table></body></html>
    """
    (tmp_path / "page_0001.html").write_text(page, encoding="utf-8")

    records = clean_data(str(tmp_path))

    assert len(records) == 1
    record = records[0]
    assert record["status"] == "Wait listed"
    assert record["decision_date"] == ""
    assert record["GRE"] == "GRE 165"
    assert record["GRE V"] == "GRE V 160"
    assert record["GRE AW"] == "GRE AW 5"
    assert record["comments"] == "Great campus visit, friendly faculty."


def test_clean_data_with_no_directory_returns_an_empty_list():
    assert clean_data("/nonexistent/path/this-does-not-exist-9000") == []


def test_clean_data_with_no_table_on_the_page_returns_no_records(tmp_path):
    (tmp_path / "page_0001.html").write_text(
        "<html><body>no results table here</body></html>", encoding="utf-8")
    assert clean_data(str(tmp_path)) == []


def test_clean_load_data_reads_records_back_from_json(tmp_path):
    """clean.py's own load_data(), distinct from load_data.py's; nothing else
    in the suite calls it."""
    path = tmp_path / "applicant_data.json"
    path.write_text(json.dumps([{"program": "Computer Science"}]), encoding="utf-8")
    assert clean.load_data(str(path)) == [{"program": "Computer Science"}]


# --- pull_data._start_browser: delegates to scrape, with no browser launched

def test_pull_data_start_browser_opens_a_visible_window(monkeypatch):
    """Pull Data always shows the window, since the first run needs it for
    Cloudflare; this is what proves headless=False actually reaches scrape.py."""
    class _FakeChrome:
        def __init__(self, options):
            self.options = options

    monkeypatch.setattr(scrape_module.webdriver, "Chrome", _FakeChrome)

    driver = pd._start_browser()

    assert not any("--headless=new" in arg for arg in driver.options.arguments)


# --- load_records: the two branches the route's own tests never reach ------

def test_load_records_with_no_records_returns_zero_without_connecting():
    def _unused_connect():
        raise AssertionError("connect must not be called when there is nothing to load")

    assert load_records([], connect=_unused_connect) == 0


def test_load_records_raises_when_the_database_is_unreachable():
    with pytest.raises(PullError, match="database could not be reached"):
        load_records([{"url": "x"}], connect=lambda: None)


# --- main: the command-line entry point, all three outcomes ----------------

def test_main_reports_entries_added(monkeypatch, capsys):
    monkeypatch.setattr(pd, "scrape_new_records", lambda: ["record1", "record2"])
    monkeypatch.setattr(pd, "load_records", lambda records: len(records))

    assert pd.main() == 0
    assert "Added 2 new entries" in capsys.readouterr().out


def test_main_reports_nothing_new(monkeypatch, capsys):
    monkeypatch.setattr(pd, "scrape_new_records", lambda: [])
    monkeypatch.setattr(pd, "load_records", lambda records: 0)

    assert pd.main() == 0
    assert "no new entries" in capsys.readouterr().out


def test_main_reports_a_pull_error(monkeypatch, capsys):
    def _failing_scraper():
        raise PullError("stopped for a test reason")

    monkeypatch.setattr(pd, "scrape_new_records", _failing_scraper)
    monkeypatch.setattr(pd, "load_records", lambda records: 0)

    assert pd.main() == 1
    assert "Stopped: stopped for a test reason" in capsys.readouterr().out
