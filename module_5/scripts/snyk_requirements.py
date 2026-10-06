"""snyk_requirements.py: split the universal lock into what Snyk can scan on this machine.

EN 605.256 Modern Software Concepts in Python, Module 5.
Joshua Latz (jlatz1)

requirements.txt is a universal lock: a few lines carry an environment marker
such as ``colorama==0.4.6 ; sys_platform == 'win32'``, so one file serves macOS,
Linux, and Windows. Snyk inspects the *installed* environment, does not evaluate
markers, and so stops with "Missing required packages" for every line that does
not apply to the machine running it. Nothing is wrong with the lock; this is a
limit of the scanner.

This script evaluates each marker with the same ``packaging`` library pip uses
and writes two marker-free files:

    applies   the lines that apply here and are installed in this environment
    excluded  the lines a marker excludes here (other platforms)

``snyk test`` runs against ``applies`` in the project's own environment, and
against ``excluded`` in a scratch environment that installs just those pins, so
every one of the lock's packages is scanned and none is skipped.

Contains:
    split_lock():  the two lists of requirement lines
    main():        write both files

Usage (from module_5/):
    python scripts/snyk_requirements.py <applies.txt> <excluded.txt>
"""

import sys
from pathlib import Path

from packaging.requirements import Requirement

LOCK = Path(__file__).resolve().parent.parent / "requirements.txt"


def split_lock(lines, environment=None):
    """Split lock lines into those whose marker applies in an environment and those it excludes.

    Args:
        lines: the text lines of a requirements file.
        environment: marker variables to evaluate against; None means this machine.

    Returns:
        tuple[list[str], list[str]]: ``name==version`` lines that apply, and lines excluded.
    """
    applies, excluded = [], []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        requirement = Requirement(text)
        pin = f"{requirement.name}=={next(iter(requirement.specifier)).version}"
        if requirement.marker is None or requirement.marker.evaluate(environment):
            applies.append(pin)
        else:
            excluded.append(pin)
    return applies, excluded


def main():
    """Write the two files named on the command line and report the counts."""
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    applies, excluded = split_lock(LOCK.read_text(encoding="utf-8").splitlines())
    Path(sys.argv[1]).write_text("\n".join(applies) + "\n", encoding="utf-8")
    Path(sys.argv[2]).write_text("\n".join(excluded) + "\n", encoding="utf-8")
    print(f"{len(applies)} apply here, {len(excluded)} excluded by a marker: {', '.join(excluded)}")


if __name__ == "__main__":
    main()
