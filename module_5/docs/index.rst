Grad Cafe Analytics
===================

A service that scrapes Grad Cafe applicant results, loads them into
PostgreSQL, and serves an analysis page and a JSON search endpoint. Module 5
hardened it: composed and parameterized SQL with a bounded ``LIMIT`` on every
query, a least-privilege database account, credentials from the environment
only, a pinned and installable environment, 10.00/10 Pylint, a dependency
graph, Snyk scans, and a four-job CI pipeline.

The repository README is the place to start: it maps every requirement to its
evidence and to a command that checks it. These pages are the reference.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   overview
   security
   architecture
   api
   testing
   operations

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
