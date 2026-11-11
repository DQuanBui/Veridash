"""Trust benchmark: measures how well Veridash's safety checks work.

Three independent suites run on the bundled example datasets:

* ``factcheck_bench``: plants wrong numbers in sentences and measures how many
  the fact-checker catches, and how often it wrongly flags correct numbers.
* ``sql_guard_bench``: sends harmful and harmless SQL through the query guard
  and the sandbox and counts what is blocked or allowed.
* ``crosscheck``: recomputes every headline number with pandas, independently
  of the DuckDB SQL, and checks that the two agree.

Run ``python -m bench`` to print the results and refresh ``bench/results.json``.
"""
