"""scrape.py: URL building, page parsing helpers, and the batch scraper.

Rubric: pytest.ini's buttons marker text is "'Pull Data' and 'Update
Analysis' behavior." scrape_data() is Module 2's one-time historical-pull
entry point, not something the Pull Data button calls (pull_data.py calls
_start_browser, _build_url, _next_cursor, and _page_path directly instead),
but it is the same scraping behavior these functions exist for, so it is
grouped with test_pull_pipeline.py under the same marker rather than left
unmarked or forced into db/integration, neither of which it is.

Nothing here launches a real browser or calls sleep(). _start_browser is
exercised with webdriver.Chrome replaced by a fake that records what it was
given, never a real Chrome process. _fetch_html's real-Selenium-timeout
branch is pragma'd in scrape.py itself, for the reason given there: reaching
it for real needs either a real browser timeout or WebDriverWait's own
internal sleep, both excluded by this suite's constraints.
"""

import pytest

import scrape

pytestmark = pytest.mark.buttons


# --- Pure helpers ------------------------------------------------------------

def test_build_url_includes_the_date_window():
    url = scrape._build_url("2026-01-01", "2026-09-14")
    assert url.startswith(scrape.BASE_URL + "?")
    assert "added_start=2026-01-01" in url
    assert "added_end=2026-09-14" in url
    assert "cursor" not in url


def test_build_url_includes_a_cursor_when_given_one():
    url = scrape._build_url("2026-01-01", "2026-09-14", cursor="abc123")
    assert "cursor=abc123" in url


def test_is_allowed_rejects_robots_txt_disallowed_paths():
    assert scrape._is_allowed("https://www.thegradcafe.com/survey") is True
    assert scrape._is_allowed("https://www.thegradcafe.com/signin") is False
    assert scrape._is_allowed("https://www.thegradcafe.com/profile/edit") is False


def test_is_challenge_true_only_without_a_result_link():
    challenge_page = "<html>Just a moment... cf-browser-verification</html>"
    assert scrape._is_challenge(challenge_page) is True
    assert scrape._is_challenge('<a href="/result/9000001">Just a moment</a>') is False
    assert scrape._is_challenge("<html>nothing relevant here</html>") is False


def test_count_entries_counts_distinct_result_links():
    html = ('<a href="/result/9000001">a</a>'
            '<a href="/result/9000002">b</a>'
            '<a href="/result/9000001">a again</a>')  # same entry, linked twice
    assert scrape._count_entries(html) == 2


def test_next_cursor_finds_the_next_link():
    html = '<a href="/survey?cursor=p2xyz">Next</a>'
    assert scrape._next_cursor(html) == "p2xyz"


def test_next_cursor_none_when_there_is_no_next_link():
    assert scrape._next_cursor("<a href=\"/survey?cursor=p2\">Previous</a>") is None
    assert scrape._next_cursor("<p>no links here</p>") is None


def test_page_path_is_numbered_and_zero_padded():
    assert scrape._page_path("/out", 1) == "/out/page_0001.html"
    assert scrape._page_path("/out", 23) == "/out/page_0023.html"


# --- _start_browser: configuration only, no real Chrome ---------------------

class _FakeChrome:
    """Captures the Options it was built with, instead of launching Chrome."""
    def __init__(self, options):
        self.options = options


def test_start_browser_uses_the_persistent_profile(monkeypatch):
    monkeypatch.setattr(scrape.webdriver, "Chrome", _FakeChrome)
    driver = scrape._start_browser(headless=False)
    assert any(scrape.PROFILE_DIR in arg for arg in driver.options.arguments)
    assert not any("--headless=new" in arg for arg in driver.options.arguments)


def test_start_browser_headless_adds_the_headless_flag(monkeypatch):
    monkeypatch.setattr(scrape.webdriver, "Chrome", _FakeChrome)
    driver = scrape._start_browser(headless=True)
    assert "--headless=new" in driver.options.arguments


# --- _fetch_html: the part that is not a real Selenium wait ------------------

def test_fetch_html_skips_disallowed_urls_without_touching_the_driver():
    class _UnusedDriver:
        def get(self, url):
            raise AssertionError("a disallowed URL must never reach driver.get()")

    result = scrape._fetch_html(_UnusedDriver(), "https://www.thegradcafe.com/signin")
    assert result is None


def test_fetch_html_returns_the_page_source_once_results_are_present():
    class _ReadyDriver:
        """A result link is present from the first poll: no waiting at all."""
        page_source = '<a href="/result/9000001">entry</a>'

        def get(self, url):
            pass

        def find_element(self, by, value):
            return object()  # WebDriverWait only checks truthiness

    result = scrape._fetch_html(_ReadyDriver(), "https://www.thegradcafe.com/survey")
    assert result == '<a href="/result/9000001">entry</a>'


# --- _resume: reading a previous run's saved pages back, no browser ---------

def test_resume_with_no_saved_pages(tmp_path):
    assert scrape._resume(str(tmp_path / "missing")) == (0, 0, None)
    assert scrape._resume(str(tmp_path)) == (0, 0, None)  # exists, but empty


def test_resume_counts_entries_and_finds_the_cursor(tmp_path):
    page_1 = '<a href="/result/9000001">a</a><a href="/result/9000002">b</a>'
    page_2 = '<a href="/result/9000003">c</a><a href="/survey?cursor=p3">Next</a>'
    (tmp_path / "page_0001.html").write_text(page_1, encoding="utf-8")
    (tmp_path / "page_0002.html").write_text(page_2, encoding="utf-8")

    page_count, entry_count, cursor = scrape._resume(str(tmp_path))

    assert page_count == 2
    assert entry_count == 3
    assert cursor == "p3"


# --- scrape_data: the orchestration, with Chrome and waiting faked ----------

class _FakeDriver:
    def quit(self):
        pass


class _FetchQueue:
    def __init__(self, pages):
        self._pages = list(pages)

    def __call__(self, _driver, _url):
        return self._pages.pop(0) if self._pages else None


def test_scrape_data_stops_when_a_page_cannot_be_fetched(tmp_path):
    saved = scrape.scrape_data(
        "2026-01-01", "2026-09-14", out_dir=str(tmp_path),
        browser_factory=_FakeDriver, fetch_html=_FetchQueue([None]),
        sleep=lambda _seconds: None)
    assert saved == 0


def test_scrape_data_stops_when_a_page_has_no_entries(tmp_path):
    saved = scrape.scrape_data(
        "2026-01-01", "2026-09-14", out_dir=str(tmp_path),
        browser_factory=_FakeDriver, fetch_html=_FetchQueue(["<html>empty</html>"]),
        sleep=lambda _seconds: None)
    assert saved == 0


def test_scrape_data_stops_when_there_is_no_next_link(tmp_path):
    page = '<a href="/result/9000001">a</a><a href="/result/9000002">b</a>'
    saved = scrape.scrape_data(
        "2026-01-01", "2026-09-14", out_dir=str(tmp_path),
        browser_factory=_FakeDriver, fetch_html=_FetchQueue([page]),
        sleep=lambda _seconds: None)
    assert saved == 2
    assert (tmp_path / "page_0001.html").exists()


def test_scrape_data_stops_at_max_entries_across_pages(tmp_path):
    page_1 = ('<a href="/result/9000001">a</a><a href="/result/9000002">b</a>'
              '<a href="/survey?cursor=p2">Next</a>')
    page_2 = '<a href="/result/9000003">c</a><a href="/survey?cursor=p3">Next</a>'
    saved = scrape.scrape_data(
        "2026-01-01", "2026-09-14", max_entries=3, out_dir=str(tmp_path),
        browser_factory=_FakeDriver, fetch_html=_FetchQueue([page_1, page_2]),
        sleep=lambda _seconds: None)
    assert saved == 3
    assert (tmp_path / "page_0001.html").exists()
    assert (tmp_path / "page_0002.html").exists()


def test_scrape_data_resumes_a_previous_run(tmp_path):
    """A page already on disk counts toward max_entries before fetching more."""
    (tmp_path / "page_0001.html").write_text(
        '<a href="/result/9000001">a</a><a href="/result/9000002">b</a>', encoding="utf-8")

    saved = scrape.scrape_data(
        "2026-01-01", "2026-09-14", max_entries=2, out_dir=str(tmp_path),
        browser_factory=_FakeDriver, fetch_html=_FetchQueue([]),
        sleep=lambda _seconds: None)

    assert saved == 2  # the while loop never runs: entry_count already meets max_entries


# --- save_data: pure file writing -------------------------------------------

def test_save_data_writes_a_json_file(tmp_path):
    path = tmp_path / "applicant_data.json"
    scrape.save_data([{"program": "Computer Science"}], filename=str(path))

    import json
    assert json.loads(path.read_text(encoding="utf-8")) == [{"program": "Computer Science"}]
