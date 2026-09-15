# EN 605.256 Modern Software Concepts in Python — Module 2: Web Scraping

**Name:** Joshua Latz
**JHED ID:** jlatz1
**Module:** Module 2 — Assignment: Web Scraping
**Due:** Sunday, 13 September 2026, 11:59 PM
**Submitted:** Monday, 14 September 2026 (one day late)
**Repository:** https://github.com/5th-legionnaire/jhu_software_concepts (private) — this assignment lives under `module_2/`
**Python:** 3.14.6 (CPython, macOS)

---

## 1. Overview

This assignment scrapes publicly posted graduate admissions results from
[The Grad Cafe](https://www.thegradcafe.com/), parses each applicant entry into a structured
record, and saves the result as a clean JSON object for use in later course modules.

A second pass runs the instructor-provided local LLM standardizer over the `program` field to
split and normalize program name and university name into two additional fields, while leaving
the original raw text intact.

**Date window scraped:** 2026-01-01 through 2026-09-14, for which the site's own search interface
reported approximately 32,324 results. This window was chosen for two reasons: it clears the
30,000-entry minimum with margin, and it covers a single admissions cycle, so the dataset is
analytically coherent rather than a mixture of several cycles with different applicant pools. For
reference, the site reports roughly 958,851 records in total across its full history.

**Entries collected:** `<TODO: final count from applicant_data.json>`

---

## 2. Repository Structure

```
jhu_software_concepts/
└── module_2/
    ├── scrape.py                        # scrape_data(), save_data()
    ├── clean.py                         # clean_data(), load_data()
    ├── run_llm.sh                       # chunked, resumable LLM standardization runner
    ├── raw_pages/                       # captured result pages, one HTML file per page
    ├── chunks/                          # LLM input/output splits
    ├── applicant_data.json              # Part 1 output: parsed applicant records
    ├── llm_extend_applicant_data.json   # Part 2 output: LLM-standardized records
    ├── llm_hosting/                     # instructor-provided local LLM standardizer
    │   ├── app.py
    │   ├── requirements.txt
    │   └── <canonical list files>
    ├── screenshot.jpg                   # robots.txt evidence
    ├── requirements.txt                 # scraper environment
    └── README.md                        # this file
```

The captured HTML in `raw_pages/` is committed so the parsed JSON can be traced back to its
source and re-parsed without rerunning the scrape. The TinyLlama model weights (`*.gguf`, roughly
650 MB) are excluded via `.gitignore` and download automatically on first run, as do the virtual
environments, which are reconstructed from the two `requirements.txt` files.

---

## 3. Installation and Setup

Two separate virtual environments are used: one for the scraper and one for the LLM
standardizer. They are kept apart because the standardizer depends on `llama-cpp-python`, which
compiles native code, and a failed build there should not take down the scraper.

### 3.1 Prerequisites
- Python 3.14.6 (verified via `python3 --version`)
- Google Chrome. ChromeDriver is resolved automatically by Selenium Manager, which ships with
  Selenium 4.x, so no separate driver installation is required.
- **macOS only:** the python.org installer ships without a CA certificate bundle, so every HTTPS
  request raises `ssl.SSLCertVerificationError: unable to get local issuer certificate` before it
  ever reaches the network. Run the bundled installer script once:
  ```bash
  /Applications/Python\ 3.14/Install\ Certificates.command
  ```
  Or, portably:
  ```bash
  pip install --upgrade certifi
  export SSL_CERT_FILE=$(python3 -m certifi)
  ```
  Certificate verification is **not** disabled anywhere in this project.

### 3.2 Scraper environment
```bash
cd module_2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Pinned: `beautifulsoup4==4.15.0`, `selenium==4.49.0`, `urllib3==2.7.0`, `soupsieve==2.9.2`.
URL construction and inspection use the standard library `urllib.parse`, which needs no
installation; `urllib3` arrives as a Selenium dependency and is pinned explicitly.

### 3.3 LLM standardizer environment
```bash
cd module_2/llm_hosting
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On first run this downloads a TinyLlama 1.1B Chat Q4_K_M GGUF model (~650 MB) from Hugging Face.
Note that `app.py` imports Flask at module scope even in CLI mode, so Flask is required whether
or not the API server is used.

---

## 4. How to Run

### 4.1 One-time browser setup
Grad Cafe sits behind Cloudflare. The verification must be cleared once, by hand, in the
persistent Chrome profile the scraper uses (`~/.gradcafe-chrome-profile`). The first run of
`scrape.py` opens a visible Chrome window; clear the verification when it appears, then rerun.
The clearance cookie persists in that profile for subsequent runs, the same way an ordinary
browser reuses it.

### 4.2 Scrape (Part 1)
```bash
cd module_2
source .venv/bin/activate
python3 scrape.py
```

Writes one HTML file per results page into `raw_pages/`. Safe to interrupt: rerunning reads the
pages already on disk, recovers the pagination cursor from the last one, and resumes from there
rather than starting over.

### 4.3 Parse (Part 1)
```bash
python3 clean.py
```

Parses every file in `raw_pages/` and writes `applicant_data.json`.

### 4.4 LLM standardization (Part 2)
```bash
cd module_2/llm_hosting
source .venv/bin/activate
bash ../run_llm.sh
```

`run_llm.sh` splits `applicant_data.json` into chunks of 3,000, runs the standardizer over each
with the GPU settings determined in section 6.7, skips any chunk whose output already exists, and
stitches the results into `llm_extend_applicant_data.json`. Rerunning after a failure reprocesses
only the missing chunk.

The equivalent single-process invocation, for reference:
```bash
N_GPU_LAYERS=999 N_BATCH=512 python3 app.py \
  --file ../applicant_data.json --stdout > ../llm_extend_applicant_data.json
```

### 4.5 Reproducing the submitted JSON files
`clean.py` and `run_llm.sh` are fully automated and require no manual intervention. `scrape.py`
requires one manual step: a human must clear the Cloudflare verification once in the browser
window before the scrape can proceed unattended. This is a property of the target site as of
September 2026, not a limitation of the scraper, and the instructor documented encountering the
same behaviour in the 7 September 2026 assignment note. No paths are hard-coded to this machine
and no credentials or API keys are required.

---

## 5. robots.txt Compliance

### 5.1 How it was checked
`https://www.thegradcafe.com/robots.txt` was retrieved and read in full before any scraping
began, and captured as `module_2/screenshot.jpg`. The file was additionally checked
programmatically with `urllib.robotparser.RobotFileParser`. See section 5.4 for an important
caveat about what that check does and does not catch.

### 5.2 What the file says
Retrieved `<TODO: date of capture>`. The live file differs substantially from the version shown
in the Module 2 lecture slides: the historical `Disallow: /cgi-bin/` and
`Disallow: /index-ad-test.php` rules are no longer present, and Cloudflare-managed AI crawler
rules and a `Content-Signal` declaration have been added.

```
# BEGIN Cloudflare Managed content

User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /

User-agent: Amazonbot
Disallow: /

User-agent: Applebot-Extended
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CloudflareBrowserRenderingCrawler
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: GPTBot
Disallow: /

User-agent: meta-externalagent
Disallow: /

# END Cloudflare Managed Content

User-agent: *
Disallow: /signin
Disallow: /register
Disallow: /forgot-password
Disallow: /reset-password
Disallow: /confirm-password
Disallow: /verify-email
Disallow: /profile
Sitemap: https://www.thegradcafe.com/sitemap.xml

User-agent: ia_archiver
Disallow: /

User-agent: ia_archiver/1.6
Disallow: /

User-agent: dotbot
Disallow: /

User-agent: YandexBot
Disallow: /
```

The file is prefaced by a comment block defining the Content-Signal vocabulary and asserting that
any restriction expressed via Content-Signal is an express reservation of rights under Article 4
of EU Directive 2019/790.

### 5.3 Interpretation
Three distinct rule sets apply:

1. **Named AI and archival crawlers are barred site-wide.** `Amazonbot`, `Applebot-Extended`,
   `Bytespider`, `CCBot`, `ClaudeBot`, `CloudflareBrowserRenderingCrawler`, `Google-Extended`,
   `GPTBot`, `meta-externalagent`, `ia_archiver`, `ia_archiver/1.6`, `dotbot`, and `YandexBot`
   may not crawl any URL on the site. This scraper does not use, impersonate, or default to any
   of these user-agent strings.

2. **All other agents may crawl the site, except account and authentication paths.** The second
   `User-agent: *` group disallows `/signin`, `/register`, `/forgot-password`,
   `/reset-password`, `/confirm-password`, `/verify-email`, and `/profile`. Every one is an
   account-management endpoint, none is required by this assignment, and all are excluded from
   the crawl. The public admissions results listing and individual `/result/<id>` permalinks are
   not disallowed.

3. **Content-Signal declares `search=yes, ai-train=no, use=reference`.** This is directly
   relevant to Part 2, which runs scraped text through a locally hosted language model.
   `ai-train` covers training or fine-tuning a model; the local standardizer performs inference
   only, and no Grad Cafe content is used to train, fine-tune, or otherwise update model weights.
   `ai-input` is not declared, so the operator neither grants nor restricts that use.
   `use=reference` is declared and is consistent with how the data is handled here.

### 5.4 Caveat: two `User-agent: *` groups
CPython's `urllib.robotparser` keeps only the **first** `User-agent: *` group it encounters (in
`RobotFileParser._add_entry`, the default entry is set once and subsequent `*` groups are
discarded). Because this file contains two such groups and the first is a bare `Allow: /`,
`can_fetch()` returns `True` for the account paths disallowed in the second group.

Verified on CPython 3.14.6 against the live file parsed from disk:

```python
parser.can_fetch(AGENT, "/result/935454")  # True   (correct)
parser.can_fetch(AGENT, "/signin")         # True   (WRONG — the file disallows this)
parser.can_fetch(AGENT, "/profile")        # True   (WRONG — the file disallows this)
```

`robotparser` is therefore used as a supporting check only, not as the sole gate. The disallowed
prefixes from the second `*` group are enforced explicitly in `scrape.py` as the
`DISALLOWED_PREFIXES` constant, checked by `_is_allowed()` before every request rather than only
against seed URLs, so a link encountered mid-crawl is caught too. Because robots.txt `Disallow`
rules are prefix matches rather than exact matches, `str.startswith` is the correct test.

### 5.5 How this scraper complies
- No requests are issued to any path disallowed by either `*` group.
- Only the public admissions results pages are requested. No login-protected, private, or
  restricted pages are touched.
- Politeness: a 2-second delay between page requests, single-threaded, no concurrency against
  the site. The scraper stops on the first failed or challenged request rather than retrying in a
  loop (`_fetch_html()` returns `None`, and `scrape_data()` breaks).
- No attempt is made to bypass robots.txt, login requirements, access controls, CAPTCHAs, or
  rate limits. Notably, no automation-masking flags such as
  `--disable-blink-features=AutomationControlled` are used, and no stealth driver is used.
- Scraped content is not used to train or fine-tune any model, consistent with `ai-train=no`.

---

## 6. Approach

### 6.1 URL management
All Grad Cafe URLs are constructed, inspected, and managed with the standard library `urllib`.

`_build_url()` in `scrape.py` assembles the survey URL from a parameter dictionary via
`parse.urlencode()`. `_is_allowed()` decomposes a URL with `parse.urlparse()` and tests its path
against the robots.txt deny-list. `_next_cursor()` extracts the pagination token from a link's
query string with `parse.urlparse()` and `parse.parse_qs()`. `clean.py` uses the site root plus
the relative href to build each entry's permalink.

The search interface exposes three relevant query parameters, all GET:

```
https://www.thegradcafe.com/survey?added_start=2026-01-01&added_end=2026-09-14&sort=newest
```

`added_start` and `added_end` filter on the same column the results are sorted by, and both
survive pagination: the site carries them alongside the cursor on every subsequent page. `sort`
accepts `oldest` but has no observed effect; results are always newest-first.

### 6.2 Fetch strategy
The scraper uses a **hybrid workflow**: urllib for URL management, Selenium for page rendering,
BeautifulSoup and regex for parsing.

The first implementation used `urllib.request.urlopen()` directly. It returns **HTTP 403**: the
site is behind Cloudflare, which rejects the request based on TLS and HTTP fingerprinting rather
than on the User-Agent header alone. Changing the User-Agent string does not help, and doing so
specifically to defeat the check would fall under the assignment's prohibition on evading access
controls.

The solution is a persistent Chrome profile. `_start_browser()` launches Chrome with
`--user-data-dir=~/.gradcafe-chrome-profile`, the Cloudflare verification is cleared once by a
human in that profile, and the resulting `cf_clearance` cookie persists across runs. This is
ordinary browser behaviour, not evasion: the challenge is satisfied the way it was designed to be
satisfied, by a person, once.

The instructor's 7 September 2026 note reported that a Selenium-controlled browser gets stuck in
a repeated verification loop. That behaviour is reproducible with Selenium's default settings,
which create a fresh throwaway profile on every launch, so the clearance cookie is discarded the
moment the driver closes. Reusing a persistent profile resolves it.

- **Browser/driver setup:** Google Chrome, driver resolved automatically by Selenium Manager.
- **Explicit waits:** `WebDriverWait(driver, 30).until(EC.presence_of_element_located(...))` on
  the CSS selector `a[href*="/result/"]`, i.e. the first link to an applicant entry. Waiting on
  rendered content rather than `document.readyState` avoids reading the page before the results
  table is populated. No hard-coded `sleep()` is used for page loading; the only `sleep()` in the
  scraper is the deliberate 2-second politeness delay between pages.
- **Challenge detection:** `_is_challenge()` distinguishes a Cloudflare interstitial from a
  genuine timeout by looking for result links and, failing that, for known interstitial text.
  This matters because `cf_clearance` expires on a timescale shorter than a full run, and the
  scraper needs to stop and report rather than loop.

### 6.3 Pagination and resumption
Grad Cafe uses Laravel **cursor pagination**, not page numbers. The `cursor` query parameter is
an unsigned, base64url-encoded JSON object carrying the sort key of the last row on the current
page:

```json
{"created_at": "2026-08-29 06:16:48", "admitid": 1020464, "_pointsToNextItems": true}
```

Two consequences. First, page *N*'s URL is derivable only from page *N-1*'s content, so the crawl
is strictly sequential and cannot be started at an arbitrary offset. The scraper follows the
site's own link labelled "Next" rather than synthesizing cursors. Second, there is no stable page
number to use as a filename or a resume marker.

Resumption works by reading back what is already on disk. `_resume()` reads the saved pages in
order, sums their entry counts, and recovers the pagination cursor from the last one, all without
touching the network. Rerunning `scrape.py` therefore continues from where the previous run
stopped, which matters because the Cloudflare clearance expires partway through a run of this
length.

Observed structure, confirmed across consecutive pages: 20 results per page, with `admitid`
descending by exactly 20 between adjacent cursors and by exactly 1 between adjacent entries. Ids
are dense in the recent range, though not across the full corpus: the maximum `admitid` is about
1,020,483 against roughly 958,851 total records, implying about 6% of ids have been removed over
the site's history.

### 6.4 Parsing
Parsing is deliberately separated from fetching. `scrape.py` writes raw page HTML to
`raw_pages/`; `clean.py` parses those files. This makes the run resumable, makes re-parsing free
when a field extraction turns out to be wrong, and means a crash costs nothing already captured.

The results table does not use one row per applicant. Each applicant occupies two or three
consecutive `<tr>` elements:

1. a main row with five cells: university, program and degree, date added, status, link to entry
2. a badge row holding term, nationality, GPA and GRE scores
3. an optional comment row

`_group_rows()` therefore groups rows by cell count: only the main row has five cells, so it
marks the start of a record, and following rows attach to the group above. Keying on cell count
rather than on the page's Tailwind class names makes the parser less brittle.

Within a group:

| Helper | What it does |
|---|---|
| `_parse_entry()` | Builds one record. University from cell 0; program and degree from the two `<span>` elements in cell 1; date added from cell 2; status from cell 3; permalink from the `/result/<id>` href in cell 4. |
| `_parse_badges()` | Classifies badge text by content pattern: a term regex, `International`/`American`, and `GPA`/`GRE`/`GRE V`/`GRE AW` prefixes. `GRE AW` and `GRE V` are tested before `GRE` because the prefixes overlap. The status is repeated as a badge for small screens and is ignored here. |
| `_parse_comment()` | Returns the comment row, identified as the extra row containing no badge elements. |
| `_normalize_status()` | Splits `"Accepted on Sep 11"` into `status` and `decision_date` using a two-group regex, while the combined form remains recoverable. |
| `_clean_text()` | Collapses whitespace and decodes HTML entities with `html.unescape()`. |

### 6.5 Cleaning
- **HTML tags and entities:** tags never enter the values, because every field is read via
  BeautifulSoup's `get_text()` rather than from raw markup. Entities are decoded by
  `html.unescape()` inside `_clean_text()`, which is applied at extraction rather than as a final
  pass, because `_parse_badges()` and `_normalize_status()` compare against clean text and would
  silently fail on uncollapsed whitespace.
- **Missing values:** represented consistently as an empty string `""`. `_parse_entry()` returns
  `{key: record.get(key, "") for key in FIELDS}`, so every record carries the same keys in the
  same order whether or not the source provided a value.
- **Raw text preserved:** the `program` field holds the combined `"Program, University"` string,
  the form the LLM standardizer expects and the form the site itself presents. It is never
  modified destructively.
- **Deduplication:** `clean_data()` deduplicates on the entry permalink.

### 6.6 LLM standardization
The instructor-provided standardizer under `llm_hosting/` was run in CLI mode over the parsed
records, producing `llm-generated-program` and `llm-generated-university` alongside the original
`program` field.

Changes made to the provided files: `<TODO: list every edit to app.py, the canonical lists, or
requirements.txt, and why. Note at minimum the deprecated hf_hub_download arguments
(force_filename, local_dir_use_symlinks) that newer huggingface_hub versions ignore.>`

One advantage of this parser worth noting: because the site presents program and university in
separate table cells, `clean.py` extracts both natively. That gives a ground-truth `university`
value to compare the model's `llm-generated-university` against, which is the basis for the
measured accuracy in section 8.

### 6.7 Runtime and parallelization
The instructor recommended parallelizing the standardization across CPU cores. Measured on this
hardware (Apple silicon, 128 GB unified memory), that advice is counterproductive: the provided
defaults already oversubscribe the CPU, and GPU offload beats every CPU configuration.

100 records, wall clock and total CPU time:

| Configuration | Wall clock | CPU time |
|---|---|---|
| Provided defaults (16 threads, CPU) | 31.3 s | 452 s |
| `N_THREADS=4`, CPU | 26.6 s | 153 s |
| `N_GPU_LAYERS=999` (Metal offload) | 14.6 s | 2.2 s |
| `N_GPU_LAYERS=999 N_BATCH=512` | **11.8 s** | **2.2 s** |
| Above, 2 concurrent processes | 16.7 s for 200 (8.4 s per 100) | 4.7 s |

Findings: reducing threads from the default to 4 made the job both faster and far cheaper in CPU,
a classic oversubscription result for single-sequence generation. Metal offload reduced CPU time
by roughly 200x and wall clock by nearly half. Raising `N_BATCH` to 512 gained a further 24% by
speeding up prompt processing. Running two GPU processes concurrently yielded only 1.4x
throughput, not 2x, so single-process was retained.

Chunking is used for resumability rather than speed: model load is only about 2.6 s, so ten
chunks cost roughly 26 s across the whole run, and a failure late in the job costs one chunk
instead of everything.

- Scrape wall clock: `<TODO: actual>`
- Standardization wall clock: `<TODO: actual>`

---

## 7. Data Schema

Each record in `applicant_data.json` is a dictionary with the same keys in the same order.
Missing values are represented as an empty string `""`.

| Key | Description |
|---|---|
| `program` | Combined `"Program, University"` text as presented by the site. Preserved unmodified for traceability and used as the LLM standardizer's input. |
| `program_name` | Program name alone, from the first `<span>` in the program cell. |
| `university` | University name alone, from the first table cell. |
| `comments` | Applicant free-text comment, when present. |
| `date_added` | Date the entry was posted to Grad Cafe, e.g. `"Sep 14, 2026"`. |
| `url` | Permalink to the individual applicant entry. |
| `status` | Decision alone, e.g. `"Accepted"`, `"Rejected"`, `"Wait listed"`, `"Interview"`. |
| `decision_date` | Date the decision was given, e.g. `"Sep 11"`. Empty when the source gives no date. |
| `term` | Semester and year of program start, e.g. `"Spring 2027"`. |
| `US/International` | `"International"` or `"American"`. |
| `GRE` | GRE total score, as labelled by the site, e.g. `"GRE 163"`. |
| `GRE V` | GRE verbal score, e.g. `"GRE V 158"`. |
| `GRE AW` | GRE analytical writing score, e.g. `"GRE AW 4"`. |
| `GPA` | Reported GPA, e.g. `"GPA 3.40"`. |
| `Degree` | `"PhD"`, `"Masters"`, `"MFA"`, and so on. |

GPA and GRE values retain the site's own label prefix rather than being converted to numbers.
This preserves the source representation exactly; numeric conversion is deferred to the database
work in Module 3.

`llm_extend_applicant_data.json` adds two keys to every record while preserving all of the above:

| Key | Description |
|---|---|
| `llm-generated-program` | Standardized program name from the local model and post-processor. |
| `llm-generated-university` | Standardized university name. |

Sample record: `<TODO: paste one real record from llm_extend_applicant_data.json>`

---

## 8. Cleaning Edge Cases and Known Imperfections

### Field availability
Field coverage is genuinely uneven, which the consistent empty-string representation is designed
to absorb. Measured on a 60-record sample: program, university, date added, permalink, status,
term and degree at 100%; nationality 93%; GPA 67%; comments 52%; GRE, GRE V and GRE AW at
approximately 7%. GRE reporting has clearly declined; sparse score fields are a property of the
source data, not a parsing failure.

### Standardization accuracy
`<TODO: run the comparison of llm-generated-university against the parsed university field and
record the exact-match rate plus the dominant mismatch patterns. Expected categories to look for:
truncated source text where the site itself cut the name off; abbreviations absent from the
canonical lists; non-US institutions; and model confabulation.>`

### Structural assumptions that could break
- Group boundaries are detected by a five-cell main row. A layout change altering the cell count
  would break grouping.
- The comment row is identified by the *absence* of badge elements, a negative test. A badge
  rendered inside a comment row would misclassify it.
- The permalink is read from the comment-icon anchor in the fifth cell. Every sampled row carried
  one, but an entry rendered without that anchor would yield an empty `url`.

---

## 9. Known Bugs

`<TODO: complete after the final run. If the solution works correctly this section may be
omitted; otherwise, for each bug state what is wrong, what the incorrect behaviour is, and how
you would fix it.>`

---

## 10. Requirements Traceability

### SHALL
- [ ] Programmatically pull data from Grad Cafe using Python
- [ ] Use Python 3.10 or later
- [ ] Use urllib to construct, inspect, and manage Grad Cafe URLs
- [ ] Store scraped data as JSON under the filename `applicant_data.json`
- [ ] Use reasonable and descriptive JSON object keys
- [ ] Include at least 30,000 graduate applicant entries
- [ ] Include a README
- [ ] Include a `requirements.txt` sufficient to reconstruct the environment
- [ ] Available on GitHub in a private repo named `jhu_software_concepts`
- [ ] All assignment materials inside a folder named `module_2`
- [ ] Comply with robots.txt before scraping
- [ ] Include robots.txt evidence: `screenshot.jpg` plus written explanation in this README
- [ ] Scrape only publicly accessible Grad Cafe pages
- [ ] Be polite: avoid rapid repeated requests
- [ ] Stop scraping if the site blocks, rate-limits, or rejects requests
- [ ] Clean the data per the cleaning requirements
- [ ] Capture all required fields when available
- [ ] Preserve the original raw program/applicant listing text for traceability
- [ ] Use a consistent representation for missing values
- [ ] Ensure `applicant_data.json` is valid JSON

### SHOULD
- [ ] Use BeautifulSoup, Python string methods, and/or regex for extraction
- [ ] Use Selenium only as a browser-rendering tool for public pages
- [ ] Use explicit waits rather than bare `sleep()` calls
- [ ] Include reasonable delays or throttling between requests
- [ ] Include `selenium` in `requirements.txt`
- [ ] Document whether the scraper is urllib-only, Selenium-rendered, or hybrid
- [ ] Document browser/driver setup
- [ ] Written using functions or class methods
- [ ] Implement `scrape_data()`, `clean_data()`, `save_data()`, `load_data()`
- [ ] Use leading-underscore private helpers (`_parse_entry()`, `_normalize_status()`)
- [ ] Scraping logic in `scrape.py`; cleaning logic in `clean.py`
- [ ] No remnant HTML tags or HTML entities in final data
- [ ] Handle unexpected, inconsistent, or messy information gracefully
- [ ] Preserve applicant-provided data accurately
- [ ] Maintain raw fields alongside cleaned fields where helpful
- [ ] Well commented and clearly named

### SHALL NOT
- [ ] No scraping of pages disallowed by robots.txt
- [ ] No bypassing of robots.txt, logins, access controls, CAPTCHAs, or rate limits
- [ ] No browser automation used to evade blocking or throttling
- [ ] No fabricated applicant records
- [ ] No alteration of outcomes, dates, scores, universities, programs, or comments
- [ ] No scraping of private, login-protected, restricted, or personally identifying data
- [ ] No secret API keys, paid services, private credentials, or unrecoverable local paths
- [ ] `applicant_data.json` submitted in JSON format only
- [ ] Nothing omitted: README, `requirements.txt`, robots.txt evidence, repo structure
- [ ] No find/search methods outside BeautifulSoup, string methods, regex, or Selenium rendering
- [ ] No destructive modification of the original applicant-provided program field
- [ ] No hard-coded applicant records
- [ ] Not submitted as only a notebook or screenshot

---

## 11. Submission Checklist

1. [ ] SSH URL to the GitHub repository
2. [ ] `scrape.py` under `module_2`
3. [ ] `clean.py` under `module_2`
4. [ ] `llm_hosting/` folder with all instructor-provided files
5. [ ] `applicant_data.json` under `module_2`
6. [ ] `llm_extend_applicant_data.json` under `module_2`
7. [ ] `screenshot.jpg` (robots.txt evidence) under `module_2`
8. [ ] This README under `module_2`
9. [ ] `requirements.txt` under `module_2`
10. [ ] Zipped `module_2` folder uploaded to Canvas, matching the GitHub push
11. [ ] Final GitHub push timestamped before submission
