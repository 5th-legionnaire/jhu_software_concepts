# Snyk triage

Every finding from `snyk test` (dependencies) and `snyk code test` (static analysis of
`src/`), with what was decided and why. Evidence: `snyk_report.json`,
`snyk/before_upgrade_applies.json`, `snyk/excluded.json`, `snyk_code_report.txt`,
`snyk/code_before_fix.sarif.json`, and the screenshots `snyk-analysis.png` and
`snyk-code-analysis.png`.

## Dependencies (`snyk test`): 70 pinned packages scanned, 22 findings in 2 packages

Snyk reports one entry per dependency path, so urllib3's three distinct issues appear 21 times.

| Package | Issue | Severity | Decision |
| --- | --- | --- | --- |
| urllib3 2.7.0 | Improper Certificate Validation (SNYK-PYTHON-URLLIB3-20302844) | High | **Fixed**: `urllib3~=2.8` in `setup.py`, locked at 2.8.0 |
| urllib3 2.7.0 | Allocation of Resources Without Limits or Throttling (SNYK-PYTHON-URLLIB3-20302846) | High | **Fixed**: same upgrade |
| urllib3 2.7.0 | Infinite loop (SNYK-PYTHON-URLLIB3-20302845) | Medium | **Fixed**: same upgrade |
| python-dotenv 1.0.1 | Symlink Attack (SNYK-PYTHON-PYTHONDOTENV-16115271) | Medium | **Fixed**: `python-dotenv~=1.2` in `setup.py`, locked at 1.2.4. The application only reads `.env`, so the flaw (rewriting a file through a symlink) was not reachable, but the fix costs nothing |

After the upgrade: 65 packages scanned with no vulnerable path, and the 5 packages a platform
marker excludes here (`cffi`, `colorama`, `greenlet`, `pycparser`, `tzdata`) scanned separately
with none either. The full suite passed on the new versions (563 tests, 100% coverage).

## Static analysis (`snyk code test`, extra credit): 2 findings

| Rule | Where | Severity | Decision |
| --- | --- | --- | --- |
| python/NoHardcodedPasswords | `load_data.py`, the `ROLE_ENV` table | Warning | **False positive, fixed in code anyway (CHG-21).** The value was the *name* of an environment variable (`"DB_PASSWORD"`), not a password. `ROLE_ENV` now maps each role to a `(user variable, password variable)` pair, with no change in behavior |
| python/PT (Path Traversal) | `load_data.py`, `main()` opening `sys.argv[1]` | Low | **Accepted risk.** The path is chosen by the person running `python3 src/load_data.py <file>` on their own machine, who can already read any file they own. No web request reaches this code, and the Flask app never passes user input to it |

After the fix, Snyk Code reports 1 open issue: the accepted LOW note above.
