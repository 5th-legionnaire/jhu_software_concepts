"""Sphinx configuration for the Grad Cafe Analytics service.

EN 605.256 Modern Software Concepts in Python, Module 4.
Joshua Latz (jlatz1)
"""

import os
import sys

# Autodoc imports the application modules, which live one level up in src/.
sys.path.insert(0, os.path.abspath("../src"))

project = "Grad Cafe Analytics"
author = "Joshua Latz (jlatz1)"
copyright = "2026, Joshua Latz"
release = "4.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "flask": ("https://flask.palletsprojects.com/en/stable/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
}

# Selenium and psycopg are imported at module scope by scrape.py and
# load_data.py. Read the Docs installs them from requirements.txt, so nothing
# is mocked here; add names to autodoc_mock_imports only if a build fails.
autodoc_mock_imports = []

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "member-order": "bysource",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = []
