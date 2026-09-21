"""
models.py: SQLAlchemy ORM representation of the applicants table.

EN 605.256 Modern Software Concepts in Python, Module 3.
Joshua Latz (jlatz1)

Contains:
    Base:            declarative base for the ORM models
    Applicant:       model mapped to the existing applicants table
    get_engine():    the SQLAlchemy Engine, built from the same PG* settings as load_data.py
    get_session():   a new Session bound to that Engine

The table is created and loaded by load_data.py. This module maps it and does
not create, alter, or copy it: there is one applicants table, read by both the
raw SQL and ORM code.

Usage:
    python3 models.py    # verify the model against the live table
"""

from datetime import date
from functools import lru_cache

from sqlalchemy import Date, Engine, Float, Integer, Text, URL, create_engine, func, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from load_data import get_db_config


class Base(DeclarativeBase):
    """Declarative base for the Module 3 ORM models."""


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

    # Additional columns carried over from Module 2 (README section 5.2).
    program_name: Mapped[str | None] = mapped_column(Text)
    university: Mapped[str | None] = mapped_column(Text)
    decision_date: Mapped[str | None] = mapped_column(Text)

    def __repr__(self):
        return (f"Applicant(p_id={self.p_id!r}, program={self.program!r}, "
                f"term={self.term!r}, status={self.status!r})")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the application's Engine, created once on first use.

    Built from the same PG* environment variables (via .env) as load_data.py,
    so the ORM and the raw SQL code reach the same database and table. URL.create
    escapes the password safely, which string-formatting a URL would not.
    Created lazily rather than at import, so importing this module has no side
    effects when the variables are unset.
    """
    config = get_db_config()
    url = URL.create(
        drivername="postgresql+psycopg",  # psycopg 3; plain "postgresql" means psycopg2
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=int(config["port"]),
        database=config["dbname"],
    )
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    """Return the sessionmaker bound to the application's Engine."""
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


if __name__ == "__main__":
    _verify_mapping()