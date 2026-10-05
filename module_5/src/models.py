"""
models.py: SQLAlchemy ORM representation of the applicants table.

EN 605.256 Modern Software Concepts in Python, Module 4.
Joshua Latz (jlatz1)
Written for Module 3; see the README for what Module 4 changed.

Contains:
    Base:                   declarative base for the ORM models
    Applicant:              model mapped to the existing applicants table
    build_url():            the SQLAlchemy URL, from DATABASE_URL or the PG* fallbacks
    make_engine():          a new Engine for a given URL
    make_session_factory(): a sessionmaker bound to a new Engine for a given URL
    get_engine():           the application's default Engine, built once
    get_session():          a new Session bound to that default Engine

The table is created and loaded by load_data.py. This module maps it and does
not create, alter, or copy it: there is one applicants table, read by both the
raw SQL and ORM code.

Usage (from module_4/):
    python3 src/models.py    # verify the model against the live table
"""

import os
from datetime import date
from functools import lru_cache

from sqlalchemy import Date, Engine, Float, Integer, Text, URL, create_engine, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from load_data import get_db_config

# psycopg 3. A bare "postgresql://" URL sends SQLAlchemy looking for psycopg2,
# which this project does not install, so the driver is always named.
DRIVER = "postgresql+psycopg"


class Base(DeclarativeBase):
    """Declarative base for the Grad Cafe ORM models."""


class Applicant(Base):
    """One Grad Cafe applicant entry, mapped to the existing applicants table."""

    __tablename__ = "applicants"

    # Required columns, in the order and with the types of the assignment schema.
    # p_id is the Grad Cafe result id, not a generated sequence, so autoincrement
    # is off: the ORM must never try to mint ids of its own.
    p_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    program: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    date_added: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(Text, unique=True)
    status: Mapped[str | None] = mapped_column(Text)
    term: Mapped[str | None] = mapped_column(Text)
    us_or_international: Mapped[str | None] = mapped_column(Text)
    gpa: Mapped[float | None] = mapped_column(Float)
    gre: Mapped[float | None] = mapped_column(Float)
    gre_v: Mapped[float | None] = mapped_column(Float)
    gre_aw: Mapped[float | None] = mapped_column(Float)
    degree: Mapped[str | None] = mapped_column(Text)
    llm_generated_program: Mapped[str | None] = mapped_column(Text)
    llm_generated_university: Mapped[str | None] = mapped_column(Text)

    # Additional columns carried over from Module 2; see "Additional columns"
    # in the README for why no parsed field is dropped.
    program_name: Mapped[str | None] = mapped_column(Text)
    university: Mapped[str | None] = mapped_column(Text)
    decision_date: Mapped[str | None] = mapped_column(Text)

    def __repr__(self):
        return (f"Applicant(p_id={self.p_id!r}, program={self.program!r}, "
                f"term={self.term!r}, status={self.status!r})")


def build_url(database_url=None):
    """Return the SQLAlchemy URL for the database.

    An explicit argument wins, then DATABASE_URL, then the PG* settings
    load_data.py reads, so the ORM and the raw SQL code always reach the same
    database and table. URL.create escapes the password safely, which
    string-formatting a URL would not.

    Args:
        database_url: an explicit URL, as create_app() passes in tests.

    Returns:
        sqlalchemy.URL: the connection URL, with the psycopg 3 driver named.
    """
    url = database_url or os.environ.get("DATABASE_URL")
    if url:
        parsed = make_url(url)
        # Respect a driver the caller named; supply ours when they named none.
        return parsed if "+" in parsed.drivername else parsed.set(drivername=DRIVER)

    config = get_db_config()
    return URL.create(
        drivername=DRIVER,
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=int(config["port"]),
        database=config["dbname"],
    )


def make_engine(database_url=None) -> Engine:
    """Return a new Engine for the given URL.

    pool_pre_ping checks a pooled connection before handing it out, so a
    connection the server has since closed surfaces as a reconnect rather
    than a failed request.
    """
    return create_engine(build_url(database_url), pool_pre_ping=True)


def make_session_factory(database_url=None) -> sessionmaker[Session]:
    """Return a sessionmaker bound to a new Engine for the given URL.

    create_app() calls this, which is what lets a test point the whole
    application at a disposable database without touching the environment.
    Deliberately uncached: two callers asking for different URLs must get
    factories reaching different databases.
    """
    return sessionmaker(bind=make_engine(database_url), expire_on_commit=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the application's default Engine, created once on first use.

    Created lazily rather than at import, so importing this module has no side
    effects when no connection settings are set.
    """
    return make_engine()


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    """Return the sessionmaker bound to the application's default Engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Session:
    """Return a new Session. Use as a context manager: `with get_session() as session:`."""
    return _session_factory()()


def _verify_mapping():
    """Compare the model with the live table, then read a row back through the ORM."""
    live = {col["name"] for col in inspect(get_engine()).get_columns("applicants")}
    mapped = {col.name for col in Applicant.__table__.columns}
    print(f"Columns in table: {len(live)}; mapped by Applicant: {len(mapped)}")
    if live != mapped:
        print(f"  In table but not mapped: {sorted(live - mapped) or 'none'}")
        print(f"  Mapped but not in table: {sorted(mapped - live) or 'none'}")
        raise SystemExit(1)
    print("Model matches the table.")

    with get_session() as session:
        total = session.scalar(select(func.count()).select_from(Applicant))
        newest = session.scalars(select(Applicant).order_by(Applicant.p_id.desc()).limit(1)).first()
    print(f"Rows via ORM: {total:,}")
    print(f"Newest entry: {newest!r}")


if __name__ == "__main__":  # pragma: no cover - command line entry point
    _verify_mapping()