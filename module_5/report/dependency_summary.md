# Dependency graph summary

The graph is `dependency.svg` in `module_5/`, built from the entry point with:

```bash
pydeps src/app.py --noshow -T svg -o dependency.svg --max-module-depth=1
```

Explanation (7 sentences, for the report):

`app.py` is the hub: it is the application's entry point and imports seven of the other nine project modules directly, reaching `scrape` and `clean` only through `pull_data`. Two parallel database paths meet at one table, the psycopg path (`query_data`, `load_data`, `applicant_search`) that composes SQL with psycopg's `sql` module and the ORM path (`models`, `orm_queries`) built on SQLAlchemy, and they stay consistent because `models` reads its connection settings from `load_data` while `orm_queries` reuses `query_data`'s validity ranges and patterns. The ETL chain is orchestrated by `pull_data`, which imports `scrape` to fetch pages, `clean` to parse them (and `clean` itself imports `scrape`), `load_data` to insert the records, and `models` to find the newest stored entry, and only `app.py` reaches that chain. `db_safety` is the shared leaf: it imports no other project module and is imported by seven, every module that builds or runs SQL, so a single definition of the 1 to 100 limit governs the raw SQL, the ORM statements and the search endpoint. There are no import cycles among the project modules, and the browser code (`scrape`, with Selenium) imports nothing that touches SQL. Flask, with its Jinja2 and Werkzeug dependencies, serves the page and the API from `app.py`; psycopg is the PostgreSQL driver and SQL composer used by five modules; SQLAlchemy provides the ORM in `models`, `orm_queries` and `pull_data` and uses psycopg as its driver; python-dotenv loads `.env` in `load_data`; and Selenium drives Chrome in `scrape` and `pull_data`. Arrows point from an imported module to the module that imports it, each third-party package is a single node because of `--max-module-depth=1`, and the graph stops two imports from `app.py`, so BeautifulSoup, which `clean` uses, lies just beyond its edge.
