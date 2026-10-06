"""dependency.svg and the explanation that goes with it (R18 to R20).

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

The committed graph is checked three ways. It is a well-formed SVG that names
every module in src/, so it cannot silently omit one. It is the graph pydeps
produces now, regenerated and compared by its nodes and edges, so it cannot
quietly go stale after an import changes. And the structural claims the report
makes about it (a hub, a shared leaf, no cycles) are recomputed from its edges,
so the prose cannot drift from the picture.

Graphviz's dot must be installed, as the README's Fresh Install section says.
"""

import html
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

MODULE_DIR = Path(__file__).resolve().parent.parent
SVG = MODULE_DIR / "dependency.svg"
SUMMARY = MODULE_DIR / "report" / "dependency_summary.md"
SRC_MODULES = {"app_py" if p.stem == "app" else p.stem for p in (MODULE_DIR / "src").glob("*.py")}
PYDEPS = [str(Path(sys.executable).parent / "pydeps"), "src/app.py", "--noshow", "-T", "svg",
          "--max-module-depth=1"]


def graph(svg_text):
    """(nodes, edges) from a pydeps SVG; an edge is (imported, importer)."""
    titles = [html.unescape(t) for t in re.findall(r"<title>([^<]*)</title>", svg_text)]
    edges = {tuple(t.split("->")) for t in titles if "->" in t}
    nodes = {t for t in titles if "->" not in t and t != "G"}
    return nodes, edges


def project_imports():
    """{module: set of project modules it imports}, from the committed graph."""
    _nodes, edges = graph(SVG.read_text(encoding="utf-8"))
    imports = {module: set() for module in SRC_MODULES}
    for imported, importer in edges:
        if imported in SRC_MODULES and importer in SRC_MODULES:
            imports[importer].add(imported)
    return imports


def test_the_svg_is_well_formed_and_not_empty():
    root = ET.fromstring(SVG.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")
    assert SVG.stat().st_size > 5000


def test_every_src_module_is_a_node():
    nodes, _edges = graph(SVG.read_text(encoding="utf-8"))
    assert SRC_MODULES <= nodes
    assert {"db_safety", "applicant_search"} <= nodes, "the two Module 5 modules must appear"


def test_the_graph_names_the_external_packages_the_report_discusses():
    nodes, _edges = graph(SVG.read_text(encoding="utf-8"))
    assert {"flask", "psycopg", "sqlalchemy", "dotenv", "selenium"} <= nodes


def test_the_committed_graph_is_what_pydeps_produces_now(tmp_path):
    """Regenerated, it has the same nodes and edges, so it cannot go stale unnoticed."""
    out = tmp_path / "regenerated.svg"
    subprocess.run([*PYDEPS, "-o", str(out)], cwd=MODULE_DIR, check=True, capture_output=True)
    assert graph(out.read_text(encoding="utf-8")) == graph(SVG.read_text(encoding="utf-8"))


# --- the claims in the report, recomputed -----------------------------------

def test_app_is_the_hub_and_reaches_scrape_and_clean_only_through_pull_data():
    imports = project_imports()
    assert imports["app_py"] == {"applicant_search", "db_safety", "load_data", "models",
                                 "orm_queries", "pull_data", "query_data"}
    assert not {"scrape", "clean"} & imports["app_py"]
    assert {"scrape", "clean"} <= imports["pull_data"]


def test_db_safety_is_a_leaf_imported_by_seven_modules():
    imports = project_imports()
    assert imports["db_safety"] == set()
    assert {m for m, deps in imports.items() if "db_safety" in deps} == {
        "app_py", "applicant_search", "load_data", "models", "orm_queries", "pull_data", "query_data"}


def test_the_two_database_paths_share_settings_and_ranges():
    imports = project_imports()
    assert "load_data" in imports["models"]
    assert "query_data" in imports["orm_queries"]


def test_scrape_and_clean_import_no_sql_module():
    imports = project_imports()
    sql_modules = {"query_data", "load_data", "models", "orm_queries", "applicant_search", "db_safety"}
    assert imports["scrape"] == set()
    assert not sql_modules & imports["clean"]


def test_there_are_no_import_cycles_among_the_project_modules():
    imports = project_imports()
    visiting, done = set(), set()

    def has_cycle(module):
        visiting.add(module)
        for dep in imports[module]:
            if dep in visiting or (dep not in done and has_cycle(dep)):
                return True
        visiting.discard(module)
        done.add(module)
        return False

    assert not any(has_cycle(m) for m in sorted(imports) if m not in done)


def test_the_cycle_check_would_catch_a_cycle():
    imports = {"a": {"b"}, "b": {"a"}}
    visiting, done = set(), set()

    def has_cycle(module):
        visiting.add(module)
        for dep in imports[module]:
            if dep in visiting or (dep not in done and has_cycle(dep)):
                return True
        visiting.discard(module)
        done.add(module)
        return False

    assert has_cycle("a")


# --- the explanation (R20) ---------------------------------------------------

def _explanation():
    text = SUMMARY.read_text(encoding="utf-8")
    return text.split("Explanation (7 sentences, for the report):", 1)[1].strip()


def test_the_explanation_is_five_to_seven_sentences():
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z`])", _explanation())
    assert 5 <= len(sentences) <= 7, len(sentences)


def test_the_explanation_names_every_project_module_and_package():
    text = _explanation()
    for name in ("app.py", "pull_data", "scrape", "clean", "load_data", "models", "orm_queries",
                 "query_data", "applicant_search", "db_safety", "Flask", "psycopg", "SQLAlchemy",
                 "python-dotenv", "Selenium"):
        assert name in text, name


COMMAND = "pydeps src/app.py --noshow -T svg -o dependency.svg --max-module-depth=1"


def test_the_summary_records_the_exact_command():
    assert COMMAND in SUMMARY.read_text(encoding="utf-8")


def test_the_documented_command_is_the_one_these_tests_regenerate_with():
    """If the flags change, the documentation, the summary, and this test change together."""
    flags = set(COMMAND.split()[1:]) - {"-o", "dependency.svg"}
    assert flags == set(PYDEPS[1:])
