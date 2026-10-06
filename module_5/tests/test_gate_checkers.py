"""The gate's own checkers must fail when they should (the safety net's safety net).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

scripts/check_secrets.py, scripts/check_change_register.py, and the log step of
scripts/gate.sh decide whether a phase may be called done. They live outside
src/, so the coverage gate never sees them, and a loosened regex or a broken
comparison would let bad work through without any test noticing. Each test
here feeds one a synthetic input that it must reject, built in a temporary
directory so no real file is touched, and pairs it with a clean input that it
must accept, so a checker that rejects everything does not pass either.

Two of these tests are regressions from Phase 1: the Gate Log row check once
matched unrelated tables whose rows begin "| 1 |", and the heading marker once
skipped headings that end in a closing parenthesis.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = MODULE_DIR / "scripts"


def _load(name):
    """Import scripts/<name>.py, which is not on sys.path."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def secrets():
    return _load("check_secrets")


@pytest.fixture(scope="module")
def register():
    return _load("check_change_register")


# --- check_secrets ----------------------------------------------------------

def _scan(secrets, tmp_path, rel, text, phase=0):
    path = tmp_path / "scan_target.txt"
    path.write_text(text, encoding="utf-8")
    return secrets.scan_file(str(path), rel, phase)


# Each hostile line is assembled from pieces. Written whole, these literals
# would trip check_secrets.py on this very file, and the scanner is not
# loosened to excuse its own tests.
BAD_LINES = [
    ('URL = "postgresql://app:' + "hunter2" + '@db.example.com/gradcafe"',
     "password embedded in a URL"),
    ('password = "' + "hunter2" + '"', "password assigned a literal"),
    ('PASSWORD: "' + "hunter2" + '"', "password assigned a literal"),
    ("-----BEGIN RSA " + "PRIVATE KEY-----", "private key block"),
    ("key = " + "AKIA" + "IOSFODNN7EXAMPLE", "AWS access key"),
    ("t = " + "ghp_" + "a" * 36, "GitHub token"),
    ('api_token = "' + "123e4567-e89b-12d3-a456-" + '426614174000"',
     "Snyk or other UUID API token assigned to a name"),
]


@pytest.mark.parametrize("line, expected", BAD_LINES)
def test_secrets_scan_flags_credential_shapes(secrets, tmp_path, line, expected):
    findings = _scan(secrets, tmp_path, os.path.join("src", "x.py"), line + "\n")
    assert len(findings) == 1
    assert findings[0].startswith(f"{os.path.join('src', 'x.py')}:1:")
    assert expected in findings[0]


@pytest.mark.parametrize("line", [
    'URL = "postgresql://app:change-me@localhost/gradcafe"',
    'URL = "postgresql://user:${DB_PASSWORD}@host/db"',
    'PG = {"password": "PGPASSWORD"}',
    'password = "pass"',
    "x = os.environ['DB_PASSWORD']",
])
def test_secrets_scan_accepts_placeholders_and_references(secrets, tmp_path, line):
    assert _scan(secrets, tmp_path, os.path.join("src", "x.py"), line + "\n") == []


def test_secrets_password_literal_is_only_checked_under_src(secrets, tmp_path):
    """Tests build throwaway configs on purpose; application code may not."""
    line = 'password = "hunter2"\n'
    assert _scan(secrets, tmp_path, os.path.join("tests", "t.py"), line) == []
    assert _scan(secrets, tmp_path, os.path.join("src", "a.py"), line) != []


def test_secrets_known_exception_expires_at_its_phase(secrets, tmp_path):
    rel, literal, until, _why = secrets.KNOWN_EXCEPTIONS[0]
    line = f'URL = "{literal}"\n'
    assert _scan(secrets, tmp_path, rel, line, phase=until - 1) == []
    assert len(_scan(secrets, tmp_path, rel, line, phase=until)) == 1


def test_secrets_exception_applies_only_to_its_own_file(secrets, tmp_path):
    _rel, literal, until, _why = secrets.KNOWN_EXCEPTIONS[0]
    other = os.path.join("tests", "other.py")
    assert len(_scan(secrets, tmp_path, other, f'URL = "{literal}"\n', phase=until - 1)) == 1


def _secrets_main(secrets, monkeypatch, root, phase="0"):
    monkeypatch.setattr(secrets, "MODULE_DIR", str(root))
    monkeypatch.setattr(sys, "argv", ["check_secrets.py", phase])
    secrets.main()


def test_secrets_main_exits_1_and_names_the_file(secrets, tmp_path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.py").write_text('password = "hunter2"\n', encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        _secrets_main(secrets, monkeypatch, tmp_path)
    assert caught.value.code == 1
    assert os.path.join("src", "bad.py") + ":1" in capsys.readouterr().out


def test_secrets_main_passes_a_clean_tree(secrets, tmp_path, monkeypatch, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text('password = os.environ["DB_PASSWORD"]\n', encoding="utf-8")
    _secrets_main(secrets, monkeypatch, tmp_path)
    assert "Secrets check OK: 1 files scanned" in capsys.readouterr().out


def test_secrets_main_requires_a_numeric_phase(secrets, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check_secrets.py", "zero"])
    with pytest.raises(SystemExit):
        secrets.main()


# --- check_change_register --------------------------------------------------

HEADER = ("| ID | Phase | Status | Change | Rationale | Verified by |\n"
          "|---|---|---|---|---|---|\n")


def _row(cid="CHG-01", phase="1", status="done", rationale="Because.",
         verified="`test_x.py::test_a`"):
    return f"| {cid} | {phase} | {status} | A change. | {rationale} | {verified} |\n"


NODES = ["tests/test_x.py::test_a", "tests/test_x.py::test_b[one]", "tests/test_x.py::test_b[two]"]


def _run_register(register, monkeypatch, tmp_path, rows, readme="", phase="1", nodes=NODES):
    changes = tmp_path / "CHANGES.md"
    changes.write_text(HEADER + "".join(rows), encoding="utf-8")
    readme_path = tmp_path / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    monkeypatch.setattr(register, "REGISTER", str(changes))
    monkeypatch.setattr(register, "README", str(readme_path))
    monkeypatch.setattr(register, "collected_node_ids", lambda: list(nodes))
    monkeypatch.setattr(sys, "argv", ["check_change_register.py", phase])
    register.main()


ANCHOR = '<a id="chg-01"></a>\n'


def test_register_accepts_a_complete_row(register, tmp_path, monkeypatch, capsys):
    _run_register(register, monkeypatch, tmp_path, [_row()], ANCHOR)
    assert "Change Register OK: 1 row(s) due by phase 1" in capsys.readouterr().out


@pytest.mark.parametrize("row, readme, complaint", [
    (_row(status="planned"), ANCHOR, "CHG-01: status is 'planned', not 'done'"),
    (_row(rationale=""), ANCHOR, "CHG-01: no rationale"),
    (_row(), "", "CHG-01: README.md has no 'chg-01' anchor"),
    (_row(verified="`test_x.py::test_missing`"), ANCHOR,
     "CHG-01: test 'test_x.py::test_missing' is not collected"),
    (_row(verified="`fresh_install_check.sh`"), ANCHOR,
     "CHG-01: no test reference and no 'Evidence:' statement"),
])
def test_register_rejects_an_incomplete_row(register, tmp_path, monkeypatch, capsys,
                                            row, readme, complaint):
    with pytest.raises(SystemExit) as caught:
        _run_register(register, monkeypatch, tmp_path, [row], readme)
    assert caught.value.code == 1
    assert complaint in capsys.readouterr().out


def test_register_ignores_rows_for_later_phases(register, tmp_path, monkeypatch, capsys):
    later = _row(cid="CHG-09", phase="4", status="planned", rationale="")
    _run_register(register, monkeypatch, tmp_path, [_row(), later], ANCHOR, phase="1")
    assert "1 row(s) due by phase 1, 2 registered" in capsys.readouterr().out


def test_register_rejects_duplicate_ids(register, tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        _run_register(register, monkeypatch, tmp_path, [_row(), _row()], ANCHOR)
    assert "duplicate ID CHG-01" in capsys.readouterr().out


def test_register_accepts_evidence_in_place_of_a_test(register, tmp_path, monkeypatch, capsys):
    row = _row(verified="Evidence: RTD build log")
    _run_register(register, monkeypatch, tmp_path, [row], ANCHOR)
    assert "Change Register OK" in capsys.readouterr().out


def test_register_rejects_a_malformed_row(register, tmp_path):
    path = tmp_path / "CHANGES.md"
    path.write_text("| CHG-01 | 1 | done | too few cells |\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Malformed register row"):
        register.parse_register(str(path))


def test_register_test_refs_carry_the_file_forward_and_skip_evidence(register):
    cell = "`test_a.py::one`, `::two`; `test_b.py`; `scripts/gate.sh`; `test_c.py::three[*]`"
    assert register.extract_test_refs(cell) == [
        ("test_a.py", "one"), ("test_a.py", "two"), ("test_b.py", "*"), ("test_c.py", "three[*]")]


def test_register_rejects_a_reference_with_no_file_to_carry(register):
    with pytest.raises(SystemExit):
        register.extract_test_refs("`::orphan`")


@pytest.mark.parametrize("ref, expected", [
    (("test_x.py", "test_a"), True),
    (("test_x.py", "test_b"), True),          # parametrized instances count
    (("test_x.py", "test_b[one]"), True),
    (("test_x.py", "test_b[*]"), True),
    (("test_x.py", "test_*"), True),
    (("test_x.py", "*"), True),
    (("test_x.py", "test_b[three]"), False),
    (("test_x.py", "test_nope"), False),
    (("test_y.py", "test_a"), False),         # right name, wrong file
])
def test_register_resolves_references_against_collected_ids(register, ref, expected):
    assert register.resolves(ref, NODES) is expected


def test_register_collects_node_ids_from_a_real_pytest_run(register):
    """collected_node_ids lists this very test, so its pytest flags still yield node IDs."""
    ids = register.collected_node_ids()
    assert any(i.endswith("test_gate_checkers.py::test_register_collects_node_ids_from_a_real_pytest_run")
               for i in ids)


def test_register_stops_when_collection_itself_fails(register, monkeypatch):
    failed = subprocess.CompletedProcess(args=[], returncode=2, stdout="boom", stderr="")
    monkeypatch.setattr(register.subprocess, "run", lambda *a, **k: failed)
    with pytest.raises(SystemExit, match="pytest collection failed"):
        register.collected_node_ids()


# --- gate.sh: the Gate Log step --------------------------------------------

PLAN_TEXT = """# Plan

### Phase 1: Packaging (CHG-01, CHG-02)

| Count | Message |
|---|---|
| 1 | R0914 `too-many-locals` |

## 11. Gate Log

| Phase | Completed (ET) | Commit | Tests | Coverage | Pylint | Notes |
|---|---|---|---|---|---|---|
| baseline | 2026-10-05 | 1ecf2c9 | 102 | 100% | 8.36 | module_4 HEAD |
"""


def _git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def gate_repo(tmp_path):
    """A throwaway repo shaped like the real one, holding a copy of gate.sh."""
    scripts = tmp_path / "module_5" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(SCRIPTS / "gate.sh", scripts / "gate.sh")
    plan = tmp_path / "module_5" / "PLAN.md"
    plan.write_text(PLAN_TEXT, encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "M5 phase 1: packaging")
    gate_dir = tmp_path / "module_5" / ".gate"
    gate_dir.mkdir()
    tree = _git(tmp_path, "rev-parse", "HEAD^{tree}")
    (gate_dir / "phase-1.pass").write_text(
        f"tree={tree}\ntests=114\ncoverage=100.00%\npylint=8.30\n", encoding="utf-8")
    return tmp_path, plan, gate_dir


def _gate(repo, *args):
    return subprocess.run(["bash", str(repo / "module_5" / "scripts" / "gate.sh"), *args],
                          cwd=repo, capture_output=True, text=True, check=False)


def test_gate_log_marks_a_heading_that_ends_in_a_parenthesis_and_appends_the_row(gate_repo):
    repo, plan, _ = gate_repo
    result = _gate(repo, "log", "1", "a note")
    assert result.returncode == 0, result.stderr
    text = plan.read_text(encoding="utf-8")
    assert "### Phase 1: Packaging (CHG-01, CHG-02) (COMPLETE)" in text
    last = text.strip().splitlines()[-1]
    assert last.startswith("| 1 | ") and "| 114 | 100.00% | 8.30 | a note |" in last


def test_gate_log_is_not_fooled_by_rows_outside_the_gate_log(gate_repo):
    """The Pylint table above has a row that begins '| 1 |'; it is not a Gate Log row."""
    repo, _plan, _ = gate_repo
    assert _gate(repo, "log", "1", "n").returncode == 0


def test_gate_log_refuses_a_second_row_for_the_same_phase(gate_repo):
    repo, plan, _ = gate_repo
    assert _gate(repo, "log", "1", "n").returncode == 0
    before = plan.read_text(encoding="utf-8")
    again = _gate(repo, "log", "1", "n")
    assert again.returncode == 1 and "already has a row for phase 1" in again.stderr
    assert plan.read_text(encoding="utf-8") == before


def test_gate_log_refuses_when_head_differs_from_what_passed(gate_repo):
    repo, plan, gate_dir = gate_repo
    (gate_dir / "phase-1.pass").write_text("tree=0000\ntests=1\ncoverage=1%\npylint=1\n", encoding="utf-8")
    result = _gate(repo, "log", "1", "n")
    assert result.returncode == 1 and "differ from what passed the gate" in result.stderr
    assert plan.read_text(encoding="utf-8") == PLAN_TEXT


def test_gate_log_refuses_without_a_recorded_pass(gate_repo):
    repo, _plan, gate_dir = gate_repo
    (gate_dir / "phase-1.pass").unlink()
    result = _gate(repo, "log", "1", "n")
    assert result.returncode == 1 and "no recorded gate pass" in result.stderr


def test_gate_log_refuses_when_head_is_not_that_phases_commit(gate_repo):
    repo, plan, _ = gate_repo
    _git(repo, "commit", "-q", "--allow-empty", "-m", "unrelated work")
    result = _gate(repo, "log", "1", "n")
    assert result.returncode == 1 and "not the phase 1 commit" in result.stderr
    assert plan.read_text(encoding="utf-8") == PLAN_TEXT
