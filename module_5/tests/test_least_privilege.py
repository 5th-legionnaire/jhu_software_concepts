"""The runtime database account can read and add applicants, and do nothing else (CHG-11 to CHG-13).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

These tests connect as the real accounts and ask PostgreSQL what each may do,
so they check the privileges that exist and not the scripts that were meant to
create them. They need sql/roles.sql and sql/grants.sql applied to the test
database, as the README's database setup and the CI workflow do.

Running the whole suite as the runtime account is the other half of the proof:
every web, button, and integration test uses it, so the application is shown
to work with exactly these privileges and no more.
"""

import pytest
from psycopg import errors, sql

import load_data as ld
import pull_data
from app import Services, create_app
from spies import SpyConnection, rendered

pytestmark = [pytest.mark.db, pytest.mark.security]

APP_ROLE, OWNER_ROLE = "gradcafe_app", "gradcafe_owner"


def _scalar(connection, statement, params=None):
    """The first column of the first row of a composed statement."""
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchone()[0]


@pytest.fixture
def as_app(clean_db, db_url):
    """A connection as the runtime account, on the seeded-empty test database."""
    connection = ld.create_connection(ld.get_db_config(db_url))
    yield connection
    connection.close()


@pytest.fixture
def as_owner(clean_db, admin_url):
    """A connection as the owner account."""
    connection = ld.create_connection(ld.get_db_config(admin_url))
    yield connection
    connection.close()


# --- who the harness really is (CHG-13) -------------------------------------

def test_app_fixture_connects_as_app_role(as_app):
    """Guards against the harness quietly running as a superuser, which would prove nothing."""
    assert _scalar(as_app, sql.SQL("SELECT current_user")) == APP_ROLE


def test_owner_fixture_connects_as_owner_role(as_owner):
    assert _scalar(as_owner, sql.SQL("SELECT current_user")) == OWNER_ROLE


def test_the_application_database_url_is_not_the_owner_url(db_url, admin_url):
    assert db_url != admin_url


# --- the roles themselves (CHG-12) ------------------------------------------

ATTRIBUTES = sql.SQL("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication "
                     "FROM pg_roles WHERE rolname = current_user LIMIT {limit}"
                     ).format(limit=sql.Placeholder("limit"))


@pytest.mark.parametrize("who", ["as_app", "as_owner"])
def test_role_attributes(request, who):
    """Neither account is a superuser, and neither can create roles, databases, or bypass RLS."""
    connection = request.getfixturevalue(who)
    with connection.cursor() as cursor:
        cursor.execute(ATTRIBUTES, {"limit": 1})
        assert cursor.fetchone() == (False, False, False, False, False)


def test_the_owner_owns_the_table_and_the_app_does_not(as_owner):
    statement = sql.SQL("SELECT tableowner FROM pg_tables WHERE tablename = {name} LIMIT {limit}"
                        ).format(name=sql.Placeholder("name"), limit=sql.Placeholder("limit"))
    assert _scalar(as_owner, statement, {"name": "applicants", "limit": 1}) == OWNER_ROLE


PRIVILEGE = sql.SQL("SELECT has_table_privilege(current_user, {table}, {privilege}) LIMIT {limit}"
                    ).format(table=sql.Placeholder("table"), privilege=sql.Placeholder("privilege"),
                             limit=sql.Placeholder("limit"))


@pytest.mark.parametrize("privilege, allowed", [
    ("SELECT", True), ("INSERT", True),
    ("UPDATE", False), ("DELETE", False), ("TRUNCATE", False), ("REFERENCES", False),
    ("TRIGGER", False),
])
def test_table_privileges(as_app, privilege, allowed):
    got = _scalar(as_app, PRIVILEGE, {"table": "applicants", "privilege": privilege, "limit": 1})
    assert got is allowed


def test_the_app_role_cannot_create_in_the_schema(as_app):
    statement = sql.SQL("SELECT has_schema_privilege(current_user, {schema}, {privilege}) LIMIT {limit}"
                        ).format(schema=sql.Placeholder("schema"), privilege=sql.Placeholder("privilege"),
                                 limit=sql.Placeholder("limit"))
    assert _scalar(as_app, statement, {"schema": "public", "privilege": "USAGE", "limit": 1}) is True
    assert _scalar(as_app, statement, {"schema": "public", "privilege": "CREATE", "limit": 1}) is False


def test_public_has_no_privileges_on_the_table(as_owner):
    """PUBLIC is everyone, so a grant to it would reach every account on the server."""
    statement = sql.SQL("SELECT COUNT(*) FROM information_schema.role_table_grants "
                        "WHERE table_name = {table} AND grantee = {grantee} LIMIT {limit}"
                        ).format(table=sql.Placeholder("table"), grantee=sql.Placeholder("grantee"),
                                 limit=sql.Placeholder("limit"))
    assert _scalar(as_owner, statement, {"table": "applicants", "grantee": "PUBLIC", "limit": 1}) == 0


# --- what the app role is refused -------------------------------------------

DENIED = [
    "DROP TABLE applicants",
    "ALTER TABLE applicants ADD COLUMN injected TEXT",
    "CREATE TABLE injected (id INTEGER)",
    "TRUNCATE applicants",
    "COMMENT ON TABLE applicants IS 'changed'",
    "UPDATE applicants SET status = 'Rejected'",
    "DELETE FROM applicants",
    "CREATE ROLE injected_role LOGIN",
    "CREATE DATABASE injected_db",
    "CREATE TEMP TABLE injected_temp (id INTEGER)",
]


@pytest.mark.parametrize("statement", DENIED)
def test_ddl_denied(as_app, statement):
    """Each raises InsufficientPrivilege, the database's own refusal."""
    with pytest.raises(errors.InsufficientPrivilege):
        with as_app.cursor() as cursor:
            cursor.execute(sql.SQL(statement))


def test_a_grant_by_the_app_role_is_ignored(as_app, as_owner):
    """PostgreSQL answers a GRANT the role cannot make with a warning, not an error. It must do nothing."""
    with as_app.cursor() as cursor:
        cursor.execute(sql.SQL("GRANT ALL ON applicants TO PUBLIC"))
    public = sql.SQL("SELECT COUNT(*) FROM information_schema.role_table_grants "
                     "WHERE table_name = {table} AND grantee = {grantee} LIMIT {limit}"
                     ).format(table=sql.Placeholder("table"), grantee=sql.Placeholder("grantee"),
                              limit=sql.Placeholder("limit"))
    assert _scalar(as_owner, public, {"table": "applicants", "grantee": "PUBLIC", "limit": 1}) == 0
    assert _scalar(as_app, PRIVILEGE, {"table": "applicants", "privilege": "UPDATE", "limit": 1}) is False


def test_a_refused_statement_changed_nothing(as_app, as_owner, fake_rows):
    ld.insert_records(as_app, fake_rows)
    with pytest.raises(errors.InsufficientPrivilege):
        with as_app.cursor() as cursor:
            cursor.execute(sql.SQL("TRUNCATE applicants"))
    assert ld._count_rows(as_owner) == len(fake_rows)


def test_the_owner_can_do_what_the_app_cannot(as_owner):
    """The owner can create and drop objects and TRUNCATE, which is the whole point of having one."""
    with as_owner.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE TABLE owner_scratch (id INTEGER)"))
        cursor.execute(sql.SQL("DROP TABLE owner_scratch"))
        cursor.execute(sql.SQL("TRUNCATE applicants"))


# --- the minimum is also sufficient (CHG-11) --------------------------------

def test_pull_succeeds_as_app_role(db_url, fake_rows, clean_db):
    """Pull Data adds entries through the real loader with only SELECT and INSERT."""
    config = ld.get_db_config(db_url)
    inserted = pull_data.load_records(fake_rows, connect=lambda: ld.create_connection(config))
    assert inserted == len(fake_rows)


def test_pull_route_succeeds_end_to_end_as_app_role(db_url, fake_scraper, clean_db):
    client = create_app(Services(scraper=fake_scraper), database_url=db_url,
                        testing=True).test_client()
    response = client.post("/pull-data")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "inserted": 2}


def test_load_records_issues_no_ddl(as_app, fake_rows):
    """Every statement the pull sends is a SELECT or an INSERT: CREATE and COMMENT are gone."""
    seen = []
    spy = SpyConnection(as_app, seen)
    pull_data.load_records(fake_rows, connect=lambda: spy)
    verbs = {rendered(statement).split()[0].upper() for statement in seen}
    assert verbs == {"SELECT", "INSERT"}


def test_the_app_role_cannot_create_the_table_if_it_is_missing(clean_db, db_url, admin_url):
    """With the table gone, a pull fails with a clear message and does not try to create it."""
    owner = ld.create_connection(ld.get_db_config(admin_url))
    with owner.cursor() as cursor:
        cursor.execute(sql.SQL("DROP TABLE applicants"))
    try:
        config = ld.get_db_config(db_url)
        with pytest.raises(pull_data.PullError, match="applicants table does not exist"):
            pull_data.load_records([{"url": "https://www.thegradcafe.com/result/1"}],
                                   connect=lambda: ld.create_connection(config))
    finally:
        ld.create_table(owner)
        ld.execute_query(owner, sql.SQL("GRANT SELECT, INSERT ON applicants TO gradcafe_app"))
        owner.close()


def test_load_data_main_uses_the_owner_role(monkeypatch, admin_url, fake_rows, tmp_path, clean_db):
    """The bulk loader connects as the owner, so it can create the table."""
    import json
    path = tmp_path / "records.json"
    path.write_text(json.dumps(fake_rows), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", admin_url)
    monkeypatch.setattr("sys.argv", ["load_data.py", str(path)])
    seen_roles = []
    real = ld.get_db_config
    monkeypatch.setattr(ld, "get_db_config", lambda *a, **k: (seen_roles.append(k.get("role")), real(*a, **k))[1])
    ld.main()
    assert seen_roles == ["owner"]

