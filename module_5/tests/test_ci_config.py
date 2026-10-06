"""ci.yml still enforces what the assignment requires (CHG-19).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

This is not a substitute for a green run on GitHub, which is the real evidence.
It catches the cheaper failure first: a gate deleted or weakened in an edit,
which would otherwise show up as a green run that no longer checks anything.
It parses the workflow with PyYAML and asserts each requirement by name.
"""

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.security

REPO = Path(__file__).resolve().parent.parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"
TESTS_YML = REPO / ".github" / "workflows" / "tests.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _steps(workflow, job):
    return workflow["jobs"][job]["steps"]


def _commands(workflow, job):
    return "\n".join(step.get("run", "") for step in _steps(workflow, job))


def test_four_jobs(workflow):
    assert set(workflow["jobs"]) == {"lint", "dependency-graph", "snyk", "test"}


def test_the_workflow_runs_on_every_push_and_pull_request(workflow):
    """The assignment says "runs on every push/PR": no branch or path filter may narrow it."""
    triggers = workflow[True]            # PyYAML reads the bare key "on" as True
    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    for name in ("push", "pull_request"):
        assert not triggers[name], f"{name} is filtered: {triggers[name]}"


def test_every_job_runs_in_module_5_on_the_pinned_python(workflow):
    assert workflow["defaults"]["run"]["working-directory"] == "module_5"
    assert workflow["env"]["PYTHON_VERSION"] == "3.14.6"
    for job in workflow["jobs"].values():
        setup = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/setup-python")]
        assert setup and setup[0]["with"]["python-version"] == "${{ env.PYTHON_VERSION }}"


def test_pylint_fail_under_10(workflow):
    assert "pylint --rcfile=.pylintrc --fail-under=10 src" in _commands(workflow, "lint")


def test_the_lint_job_installs_the_pinned_lock_and_the_editable_package(workflow):
    commands = _commands(workflow, "lint")
    assert "pip install -r requirements.txt" in commands and "pip install -e . --no-deps" in commands


def test_svg_validation_step(workflow):
    commands = _commands(workflow, "dependency-graph")
    assert "pydeps src/app.py --noshow -T svg -o dependency.svg" in commands
    assert "--max-module-depth=1" in commands
    assert 'test -s dependency.svg && grep -q "<svg" dependency.svg' in commands
    assert "graphviz" in commands
    assert any(str(s.get("uses", "")).startswith("actions/upload-artifact") for s in _steps(workflow, "dependency-graph"))


def test_the_snyk_job_scans_through_the_marker_aware_script_and_fails_on_findings(workflow):
    assert "scripts/snyk_scan.sh" in _commands(workflow, "snyk")
    scan = next(s for s in _steps(workflow, "snyk") if "snyk_scan.sh" in s.get("run", ""))
    assert "continue-on-error" not in scan, "the dependency scan must be able to fail the job"
    assert "|| true" not in scan["run"]


def test_snyk_code_is_report_only(workflow):
    code = next(s for s in _steps(workflow, "snyk") if "snyk code test" in s.get("run", ""))
    assert "|| true" in code["run"]


def test_the_snyk_job_skips_with_a_notice_when_there_is_no_token(workflow):
    assert workflow["jobs"]["snyk"]["env"]["SNYK_TOKEN"] == "${{ secrets.SNYK_TOKEN }}"
    notice = next(s for s in _steps(workflow, "snyk") if "::notice::" in s.get("run", ""))
    assert notice["if"] == "env.SNYK_TOKEN == ''"
    gated = [s for s in _steps(workflow, "snyk") if s.get("if") == "env.SNYK_TOKEN != ''"]
    assert len(gated) >= 2


def test_pytest_runs_the_full_suite_with_no_marker_selection(workflow):
    runs = [s["run"] for s in _steps(workflow, "test") if "pytest" in s.get("run", "")]
    assert runs == [".venv/bin/python -m pytest"]


def test_the_test_job_runs_on_both_installers(workflow):
    assert workflow["jobs"]["test"]["strategy"]["matrix"]["installer"] == ["pip", "uv"]
    commands = _commands(workflow, "test")
    assert "pip install -r requirements.txt" in commands
    assert "uv pip sync requirements.txt" in commands
    assert commands.count("pip install -e . --no-deps") == 2


def test_the_test_job_has_a_postgres_service_and_both_roles(workflow):
    job = workflow["jobs"]["test"]
    assert job["services"]["postgres"]["image"].startswith("postgres:")
    commands = _commands(workflow, "test")
    assert "sql/roles.sql" in commands and "sql/grants.sql" in commands
    assert "TEST_DATABASE_URL" in commands and "TEST_ADMIN_DATABASE_URL" in commands
    assert "gradcafe_app" in commands and "gradcafe_owner" in commands


def test_ci_never_passes_a_cleartext_password_to_the_role_script(workflow):
    """Same rule as the README's database setup: verifiers in the environment, no -v password."""
    commands = _commands(workflow, "test")
    assert "scram_verifier.py" in commands and "OWNER_VERIFIER" in commands
    assert not re.search(r"psql[^\n]*-v\s+\w*(pw|pass)", commands, re.IGNORECASE)
    assert "::add-mask::" in commands, "the throwaway passwords must be masked in the log"


def test_ci_uses_the_db_contract_not_the_retired_pg_variables(workflow):
    text = CI.read_text(encoding="utf-8")
    assert not re.search("PG" + "(HOST|PORT|DATABASE|USER)", text)


def test_the_test_job_needs_graphviz_because_a_test_regenerates_the_graph(workflow):
    assert "graphviz" in _commands(workflow, "test")


def test_module_4s_workflow_is_untouched_and_still_tests_module_4():
    text = TESTS_YML.read_text(encoding="utf-8")
    assert "working-directory: module_4" in text and "name: tests" in text
    assert "module_5" not in text
