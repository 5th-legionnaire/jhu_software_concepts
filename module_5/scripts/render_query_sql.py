"""render_query_sql.py: print the SQL every analysis builder composes, with its parameters.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

The text comes from ``Composed.as_string(None)``, which renders without a
connection, so it is exactly what query_data.py hands to the driver and cannot
drift from it. tests/snapshots/m5_query_sql.txt is this output, and the README
quotes from it.

Usage (from module_5/, with the editable install active):
    python scripts/render_query_sql.py > tests/snapshots/m5_query_sql.txt
"""

import query_data


def render():
    """Return the rendered statement and parameters of every analysis builder.

    Returns:
        str: one block per question, in QUESTIONS order, ending in a newline.
    """
    blocks = []
    for name, build in query_data.QUESTIONS.items():
        statement, params = build()
        blocks.append(f"-- {name}\n{statement.as_string(None)}\nparameters: {params}")
    return "\n\n".join(blocks) + "\n"


if __name__ == "__main__":
    print(render(), end="")
