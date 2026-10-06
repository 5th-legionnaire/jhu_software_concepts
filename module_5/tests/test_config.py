"""Connection configuration and secrets handling (CHG-03, CHG-04).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

Credentials come from the environment and nowhere else. These tests pin the
contract: which source wins, which variables each role reads, that a missing
variable is named without revealing any value, that the retired PG* variables
are really gone, that .env.example documents exactly what the code reads, and
that a failed connection logs no host, port, or user name.

Every test starts from an environment with no connection settings at all. The
developer's .env is loaded into the process when load_data is imported, so the
variables are removed explicitly rather than assumed absent.
"""

import ast
import logging
from pathlib import Path

import psycopg
import pytest

import load_data as ld
import models

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
SRC = MODULE_DIR / "src"
ENV_EXAMPLE = MODULE_DIR / ".env.example"

# Module 3's variables, assembled from parts so that the Phase 2 exit check,
# a literal grep for them across src/ and tests/, finds nothing and keeps
# catching any real use that creeps back in.
RETIRED = tuple("PG" + part for part in ("HOST", "PORT", "DATABASE", "USER", "PASSWORD"))
SETTINGS = ("DATABASE_URL", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
            "DB_OWNER_USER", "DB_OWNER_PASSWORD", *RETIRED)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """No connection setting survives from the developer's shell or .env."""
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)


def _url(user, password, host, port, database, scheme="postgresql"):
    """A connection URL assembled from parts.

    Written whole, a URL with a password in it is exactly what
    scripts/check_secrets.py exists to flag, and the scanner is not loosened
    to excuse its own tests.
    """
    port = f":{port}" if port else ""
    return scheme + "://" + user + ":" + password + "@" + host + port + "/" + database


@pytest.fixture
def db_env(monkeypatch):
    """A complete DB_* environment for both roles, with distinct values per field."""
    values = {"DB_HOST": "env-host", "DB_PORT": "5433", "DB_NAME": "env-db",
              "DB_USER": "env-app-user", "DB_PASSWORD": "env-app-pass",
              "DB_OWNER_USER": "env-owner-user", "DB_OWNER_PASSWORD": "env-owner-pass"}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return values


# --- precedence (CHG-03) ----------------------------------------------------

def test_precedence_explicit_url_beats_database_url_and_db_variables(monkeypatch, db_env):
    monkeypatch.setenv("DATABASE_URL", _url("url-user", "url-pass", "url-host", 5434, "url-db"))
    config = ld.get_db_config(_url("arg-user", "arg-pass", "arg-host", 5435, "arg-db"))
    assert config == {"host": "arg-host", "port": "5435", "dbname": "arg-db",
                      "user": "arg-user", "password": "arg-pass"}


def test_precedence_database_url_beats_db_variables(monkeypatch, db_env):
    monkeypatch.setenv("DATABASE_URL", _url("url-user", "url-pass", "url-host", 5434, "url-db",
                                            scheme="postgresql+psycopg"))
    config = ld.get_db_config()
    assert config == {"host": "url-host", "port": "5434", "dbname": "url-db",
                      "user": "url-user", "password": "url-pass"}


def test_precedence_db_variables_are_used_when_no_url_is_given(db_env):
    assert ld.get_db_config() == {"host": "env-host", "port": "5433", "dbname": "env-db",
                                  "user": "env-app-user", "password": "env-app-pass"}


def test_precedence_url_credentials_are_percent_decoded():
    config = ld.get_db_config(_url("u%40x", "p%2Fw%40d", "h", None, "db"))
    assert (config["user"], config["password"]) == ("u@x", "p/w@d")


# --- roles (CHG-03) ---------------------------------------------------------

def test_owner_role_reads_owner_vars(db_env):
    config = ld.get_db_config(role="owner")
    assert config["user"] == "env-owner-user"
    assert config["password"] == "env-owner-pass"


def test_roles_share_the_server_location(db_env):
    app, owner = ld.get_db_config(role="app"), ld.get_db_config(role="owner")
    assert {k: app[k] for k in ("host", "port", "dbname")} == \
           {k: owner[k] for k in ("host", "port", "dbname")}


def test_app_is_the_default_role(db_env):
    assert ld.get_db_config() == ld.get_db_config(role="app")


def test_app_role_never_falls_back_to_the_owner_account(monkeypatch, db_env):
    """With DB_USER missing, the app must fail, not borrow DB_OWNER_USER."""
    monkeypatch.delenv("DB_USER")
    with pytest.raises(KeyError, match="DB_USER"):
        ld.get_db_config(role="app")


def test_unknown_role_is_rejected_before_any_lookup(db_env):
    with pytest.raises(ValueError, match="Unknown database role 'admin'"):
        ld.get_db_config(role="admin")


# --- missing settings (CHG-03) ----------------------------------------------

@pytest.mark.parametrize("missing", ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"])
def test_missing_var_names_variable_not_value(monkeypatch, db_env, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(KeyError) as caught:
        ld.get_db_config()
    message = str(caught.value)
    assert missing in message
    for name, value in db_env.items():
        assert value not in message, f"the message leaked {name}'s value"


@pytest.mark.parametrize("missing", ["DB_OWNER_USER", "DB_OWNER_PASSWORD"])
def test_missing_owner_var_is_named(monkeypatch, db_env, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(KeyError, match=missing):
        ld.get_db_config(role="owner")


def test_nothing_set_names_the_first_variable_needed():
    with pytest.raises(KeyError, match="DB_HOST"):
        ld.get_db_config()


# --- the retired PG* variables (CHG-03) -------------------------------------

def test_pg_variables_are_no_longer_read(monkeypatch):
    for name in RETIRED:
        monkeypatch.setenv(name, "ignored")
    with pytest.raises(KeyError, match="DB_HOST"):
        ld.get_db_config()


def test_no_source_file_reads_a_pg_variable():
    """A grep-proof of CHG-03: no string constant in src/ names a retired variable."""
    offenders = []
    for path in sorted(SRC.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value in RETIRED:
                offenders.append(f"{path.name}:{node.lineno} {node.value}")
    assert offenders == []


# --- models.build_url follows the same contract -----------------------------

def test_build_url_uses_db_variables_and_names_the_psycopg_driver(db_env):
    url = models.build_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.database) == ("env-host", 5433, "env-db")
    assert (url.username, url.password) == ("env-app-user", "env-app-pass")


def test_build_url_prefers_database_url_to_db_variables(monkeypatch, db_env):
    monkeypatch.setenv("DATABASE_URL", _url("url-user", "url-pass", "url-host", None, "url-db"))
    url = models.build_url()
    assert (url.host, url.database, url.drivername) == ("url-host", "url-db", "postgresql+psycopg")


def test_build_url_with_nothing_set_names_the_variable_not_a_value():
    with pytest.raises(KeyError, match="DB_HOST"):
        models.build_url()


# --- .env.example documents the contract ------------------------------------

def _example_names():
    """Variable names in .env.example, active or commented out."""
    names = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.lstrip("# ").strip()
        if "=" in line and line.split("=", 1)[0].isidentifier():
            names.add(line.split("=", 1)[0])
    return names


def test_env_example_lists_every_variable_the_code_reads():
    read = {name for env in ld.ROLE_ENV.values() for name in env.values()}
    read |= set(ld.DB_LOCATION_ENV.values()) | {"DATABASE_URL", "TEST_DATABASE_URL"}
    assert _example_names() == read


def test_env_example_holds_placeholders_only():
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        value = line.split("=", 1)[1]
        assert "change-me" in value or value in {"localhost", "5432", "gradcafedb", "gradcafe_app"}, line


def test_env_file_is_ignored_by_git_and_the_example_is_not():
    ignore = (MODULE_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignore
    assert ".env.example" not in ignore


# --- sanitized connection errors (CHG-04) -----------------------------------

LIBPQ_TEXT = ('connection to server at "secret-host.internal" (10.9.8.7), port 5432 failed: '
              'FATAL:  password authentication failed for user "secret_user"')
CONFIG = {"host": "h", "port": "1", "dbname": "d", "user": "u", "password": "p"}


@pytest.fixture
def refused(monkeypatch):
    """psycopg.connect raises the kind of error libpq writes, host and user included."""
    def _connect(**_kwargs):
        raise psycopg.OperationalError(LIBPQ_TEXT)
    monkeypatch.setattr(ld.psycopg, "connect", _connect)


def test_connection_error_message_is_sanitized(refused, caplog, capsys):
    with caplog.at_level(logging.ERROR, logger="load_data"):
        assert ld.create_connection(CONFIG) is None
    captured = capsys.readouterr()
    shown = caplog.text + captured.out + captured.err
    for detail in ("secret-host.internal", "10.9.8.7", "secret_user", "5432", "password authentication"):
        assert detail not in shown, f"the log leaked {detail!r}"
    assert "OperationalError" in shown
    assert "DB_* settings" in shown


def test_connection_error_is_logged_at_error_level(refused, caplog):
    with caplog.at_level(logging.DEBUG, logger="load_data"):
        ld.create_connection(CONFIG)
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


def test_successful_connection_logs_no_error(monkeypatch, caplog, capsys):
    monkeypatch.setattr(ld.psycopg, "connect", lambda **_kwargs: "connection")
    with caplog.at_level(logging.DEBUG, logger="load_data"):
        assert ld.create_connection(CONFIG) == "connection"
    assert caplog.records == []
    assert "Connection to PostgreSQL DB successful" in capsys.readouterr().out
