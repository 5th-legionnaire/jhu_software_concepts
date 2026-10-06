"""Snyk: the lock is scannable, the findings were fixed, and the evidence says so (R25 to R27).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

These tests do not call Snyk: they need no network or account, so they run
everywhere. They pin what makes the scan meaningful and what keeps it
meaningful. scripts/snyk_requirements.py must account for every pinned package
(a package it dropped would be unscanned and unnoticed). The versions that fixed
the findings must stay locked, so a later regeneration cannot quietly reintroduce
a vulnerable pin. And the committed evidence must say what the report claims: the
scan before the upgrade found the issues, and each was fixed at or below the
locked version.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
LOCK = MODULE_DIR / "requirements.txt"
LOCAL_PATH = re.compile(r"/Users/|jjlatz|/var/folders|/private/|/home/")


@pytest.fixture(scope="module")
def splitter():
    spec = importlib.util.spec_from_file_location("snyk_requirements", MODULE_DIR / "scripts" / "snyk_requirements.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lock_lines():
    return [line for line in LOCK.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _pins():
    return {Requirement(line).name.lower(): Version(next(iter(Requirement(line).specifier)).version)
            for line in _lock_lines()}


# --- splitting the universal lock --------------------------------------------

LINES = ["flask==3.1.3", "colorama==0.4.6 ; sys_platform == 'win32'",
         "uvloop==0.21.0 ; sys_platform != 'win32'", "# a comment", "", "pytest==8.4.2"]


def test_a_marker_that_holds_keeps_the_package_and_one_that_fails_excludes_it(splitter):
    applies, excluded = splitter.split_lock(LINES, {"sys_platform": "linux"})
    assert applies == ["flask==3.1.3", "uvloop==0.21.0", "pytest==8.4.2"]
    assert excluded == ["colorama==0.4.6"]


def test_the_same_lock_splits_the_other_way_on_windows(splitter):
    applies, excluded = splitter.split_lock(LINES, {"sys_platform": "win32"})
    assert "colorama==0.4.6" in applies and "uvloop==0.21.0" in excluded


def test_output_lines_carry_no_marker(splitter):
    applies, excluded = splitter.split_lock(LINES, {"sys_platform": "linux"})
    assert not any(";" in line for line in applies + excluded)


def test_every_pinned_package_is_in_exactly_one_group(splitter):
    """A package in neither group would go unscanned, and nothing would say so."""
    applies, excluded = splitter.split_lock(_lock_lines())
    names = [Requirement(line).name.lower() for line in applies + excluded]
    assert len(names) == len(set(names)), "a package is in both groups"
    assert sorted(names) == sorted(_pins()), "the groups do not cover the lock"
    assert len(names) == len(_lock_lines())


def test_the_helper_writes_both_files_and_reports_the_counts(splitter, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["snyk_requirements.py", str(tmp_path / "a.txt"), str(tmp_path / "e.txt")])
    splitter.main()
    assert "apply here" in capsys.readouterr().out
    assert (tmp_path / "a.txt").read_text(encoding="utf-8").strip()


def test_the_helper_refuses_to_run_without_its_two_file_arguments(splitter, monkeypatch):
    monkeypatch.setattr("sys.argv", ["snyk_requirements.py"])
    with pytest.raises(SystemExit):
        splitter.main()


# --- the fixes stay fixed ----------------------------------------------------

def test_remediated_versions_stay_remediated():
    """If the lock is ever regenerated onto the vulnerable pins, this fails."""
    pins = _pins()
    assert pins["urllib3"] >= Version("2.8.0")
    assert pins["python-dotenv"] >= Version("1.2.2")


# --- the evidence ------------------------------------------------------------

def _report(name):
    return json.loads((MODULE_DIR / name).read_text(encoding="utf-8"))


def test_the_committed_scan_is_clean_and_covered_every_applicable_package():
    after = _report("snyk_report.json")
    assert after["ok"] is True and after["vulnerabilities"] == []
    assert after["dependencyCount"] >= 60


def test_the_marker_excluded_packages_were_scanned_too_and_are_clean():
    excluded = _report("snyk/excluded.json")
    assert excluded["ok"] is True and excluded["vulnerabilities"] == []
    assert excluded["dependencyCount"] == 5


def test_every_package_the_lock_pins_was_scanned():
    scanned = _report("snyk_report.json")["dependencyCount"] + _report("snyk/excluded.json")["dependencyCount"]
    assert scanned == len(_lock_lines())


def test_the_scan_before_the_upgrade_found_what_the_triage_says():
    before = _report("snyk/before_upgrade_applies.json")
    findings = before["vulnerabilities"]
    assert {(f["packageName"], f["id"]) for f in findings} == {
        ("urllib3", "SNYK-PYTHON-URLLIB3-20302844"), ("urllib3", "SNYK-PYTHON-URLLIB3-20302846"),
        ("urllib3", "SNYK-PYTHON-URLLIB3-20302845"), ("python-dotenv", "SNYK-PYTHON-PYTHONDOTENV-16115271")}
    assert {f["severity"] for f in findings} == {"high", "medium"}


def test_every_finding_was_fixed_at_or_below_the_version_now_locked():
    pins = _pins()
    for finding in _report("snyk/before_upgrade_applies.json")["vulnerabilities"]:
        fixed = min(Version(v) for v in finding["fixedIn"])
        assert pins[finding["packageName"].lower()] >= fixed, finding["id"]


def test_snyk_code_before_report_has_the_two_findings_the_triage_names():
    runs = json.loads((MODULE_DIR / "snyk" / "code_before_fix.sarif.json").read_text(encoding="utf-8"))["runs"]
    assert sorted(r["ruleId"] for run in runs for r in run["results"]) == [
        "python/NoHardcodedPasswords", "python/PT"]


def test_the_final_snyk_code_report_has_only_the_accepted_low_finding():
    text = (MODULE_DIR / "snyk_code_report.txt").read_text(encoding="utf-8")
    assert "Path Traversal" in text and "NoHardcodedPasswords" not in text and "Hardcoded" not in text
    assert "0 HIGH  0 MEDIUM  1 LOW" in text


@pytest.mark.parametrize("name", ["snyk_report.json", "snyk/excluded.json", "snyk/before_upgrade_applies.json",
                                  "snyk/code_before_fix.sarif.json", "snyk_code_report.txt",
                                  "report/snyk_triage.md"])
def test_evidence_files_carry_no_local_path_or_address(name):
    text = (MODULE_DIR / name).read_text(encoding="utf-8")
    assert not LOCAL_PATH.search(text)
    assert not re.search(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", text), "an email address (not a name@version)"


def test_the_scan_script_fails_on_high_findings_by_default_and_scans_both_groups():
    script = (MODULE_DIR / "scripts" / "snyk_scan.sh").read_text(encoding="utf-8")
    assert 'SNYK_THRESHOLD:-high' in script
    assert "snyk_requirements.py" in script and "scan applies" in script and "scan excluded" in script
    assert "--severity-threshold" in script


# --- the README explains the decisions, not just the results ------------------

def _readme_section(heading):
    text = (MODULE_DIR / "README.md").read_text(encoding="utf-8")
    start = text.index(f"### {heading}")
    return text[start:text.index("\n## ", start) if "\n## " in text[start:] else len(text)]


def test_readme_records_what_the_dependency_scan_found_and_why_it_was_upgraded():
    section = _readme_section("Upgrading dependencies when a vulnerability is known")
    for fact in ("urllib3", "2.7.0", "2.8.0", "python-dotenv", "1.0.1", "1.2.4", "Improper Certificate Validation",
                 "Infinite loop", "Symlink Attack", "22 entries", "4 distinct issues", "test_remediated_versions_stay_remediated"):
        assert fact in section, fact


def test_readme_explains_why_false_positives_are_refactored_and_where_that_stops():
    section = _readme_section("False positives: refactor the code, even when you know it is safe")
    for idea in ("recurs", "standing red result", "Suppression hides", "a person", "behavior-neutral",
                 "security theater", "hardcoded password", "CHG-21", "CHG-16", "accepted risk"):
        assert idea in section, idea
