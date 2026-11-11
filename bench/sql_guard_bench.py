"""SQL guard benchmark: harmful queries must be blocked, harmless ones must run.

Ask your data runs SQL written by an AI or typed by a visitor, so it has two
layers of protection:

1. The guard (``ai.nl2sql.validate_sql``) rejects anything that is not a single,
   read-only SELECT, and caps the number of rows.
2. The sandbox (``core.engine.QueryEngine``) has file, network and extension
   access switched off and locked, so a query that slips past the guard still
   cannot reach the machine.

This suite sends each harmful query through the guard, and the ones that touch
files, URLs, extensions or settings also straight to the sandbox with the
guard turned off, to show that the second layer holds on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ai.nl2sql import SQLValidationError, run_validated, validate_sql
from core.engine import QueryEngine, QueryError
from core.pipeline import prepare
from core.settings import ASK_MAX_ROWS, SAMPLES_DIR

FILE = "{file}"  # replaced with a real file on disk, so a block is never "file not found"


@dataclass(frozen=True)
class Attack:
    """A harmful query and what it tries to do."""

    category: str
    sql: str
    sandbox: bool = False  # also run it with the guard off


ATTACKS = [
    Attack("Read a file", f"SELECT * FROM read_csv('{FILE}')", True),
    Attack("Read a file", f"SELECT * FROM '{FILE}'", True),
    Attack("Read a file", f"SELECT * FROM read_text('{FILE}')", True),
    Attack("Read a file", f"SELECT * FROM read_blob('{FILE}')", True),
    Attack("Read a file", f"SELECT * FROM data JOIN '{FILE}' USING (store)", True),
    Attack("Read a file", f"SELECT * FROM read_parquet('{FILE}')", True),
    Attack("Read a file", "SELECT * FROM glob('*')", True),
    Attack("Read a file", f"SELECT * FROM sniff_csv('{FILE}')", True),
    Attack("Reach the internet", "SELECT * FROM read_csv('https://example.com/data.csv')", True),
    Attack("Reach the internet", "SELECT * FROM 'https://example.com/data.parquet'", True),
    Attack("Write a file", "COPY (SELECT * FROM data) TO 'stolen.csv'", True),
    Attack("Write a file", "EXPORT DATABASE 'dump'", True),
    Attack("Attach a database", "ATTACH 'other.db' AS other", True),
    Attack("Load an extension", "INSTALL httpfs", True),
    Attack("Load an extension", "LOAD httpfs", True),
    Attack("Change a setting", "SET enable_external_access = true", True),
    Attack("Change a setting", "RESET lock_configuration", True),
    Attack("Read settings", "SELECT * FROM duckdb_settings()"),
    Attack("Read settings", "SELECT current_setting('home_directory')"),
    Attack("Read settings", "SELECT getenv('PATH')"),
    Attack("Read settings", "PRAGMA version"),
    Attack("Change data", "DELETE FROM data"),
    Attack("Change data", "UPDATE data SET revenue = 0"),
    Attack("Change data", "INSERT INTO data SELECT * FROM data"),
    Attack("Change data", "DROP TABLE data"),
    Attack("Change data", "CREATE TABLE copy AS SELECT * FROM data"),
    Attack("Change data", "ALTER TABLE data RENAME TO gone"),
    Attack("Change data", "TRUNCATE data"),
    Attack("Smuggle a second statement", "SELECT 1; DROP TABLE data"),
    Attack("Smuggle a second statement", "SELECT * FROM data; COPY data TO 'x.csv'"),
    Attack("Smuggle a second statement", "WITH t AS (SELECT 1) SELECT * FROM t; DELETE FROM data"),
    Attack("Hide code in a comment", "SELECT * FROM data -- ; DROP TABLE data"),
    Attack("Hide code in a comment", "SELECT /* sneaky */ * FROM data"),
    Attack("Run a transaction", "BEGIN TRANSACTION"),
    Attack("Run a transaction", "CHECKPOINT"),
    Attack("Call a procedure", "CALL pragma_version()"),
    Attack("Query by text", "SELECT * FROM query('SELECT * FROM data')"),
    Attack("Query by text", "SELECT * FROM query_table('data')"),
]

HARMLESS = [
    "SELECT * FROM data",
    'SELECT "region", SUM("revenue") AS revenue FROM data GROUP BY 1 ORDER BY 2 DESC',
    'SELECT "category", AVG("unit_price") AS avg_price, COUNT(*) AS n FROM data GROUP BY 1',
    'SELECT date_trunc(\'month\', "date") AS month, SUM("revenue") AS revenue FROM data GROUP BY 1 ORDER BY 1',
    'WITH by_store AS (SELECT "store", SUM("revenue") AS r FROM data GROUP BY 1) '
    "SELECT * FROM by_store ORDER BY r DESC LIMIT 3",
    'SELECT "store", "revenue", RANK() OVER (ORDER BY "revenue" DESC) AS rnk FROM data LIMIT 10',
    'SELECT "region", SUM("revenue") FILTER (WHERE "discount" > 0) AS discounted FROM data GROUP BY 1',
    'SELECT CASE WHEN "revenue" > 500 THEN \'big\' ELSE \'small\' END AS size, COUNT(*) FROM data GROUP BY 1',
    "SELECT COUNT(*) FROM data WHERE \"product\" = 'drop shipping; delete everything'",
    "SELECT COUNT(*) AS n FROM data WHERE \"category\" ILIKE '%update%'",
    'SELECT "region" AS "select", COUNT(*) AS "drop" FROM data GROUP BY 1',
    'SELECT MIN("date"), MAX("date") FROM data',
    'SELECT "category", median("revenue") AS med, quantile_cont("revenue", 0.9) AS p90 FROM data GROUP BY 1',
    'SELECT corr("revenue", "cost") AS r FROM data',
    'SELECT * FROM (SELECT "store", SUM("units") AS u FROM data GROUP BY 1) WHERE u > 100',
    'SELECT "region", "category", SUM("revenue") AS r FROM data GROUP BY ALL ORDER BY r DESC LIMIT 5',
    'SELECT COUNT(DISTINCT "product") FROM data',
    'SELECT "store", SUM("revenue") - SUM("cost") AS profit FROM data GROUP BY 1 ORDER BY profit DESC',
    'SELECT strftime("date", \'%Y\') AS year, SUM("revenue") FROM data GROUP BY 1 ORDER BY 1',
    'SELECT * FROM data WHERE "revenue" IS NULL',
    'SELECT * FROM data ORDER BY "revenue" DESC LIMIT 5000',
    'SELECT "region", SUM("revenue") AS r FROM data GROUP BY 1 HAVING SUM("revenue") > 1000;',
    'SELECT "category", ROUND(100.0 * SUM("revenue") / SUM(SUM("revenue")) OVER (), 1) AS share FROM data GROUP BY 1',
    'SELECT COUNT(*) - COUNT("discount") AS missing_discount FROM data',
    'SELECT "region", list_distinct(list("category")) AS cats FROM data GROUP BY 1',
]


def _sample() -> tuple[pd.DataFrame, str]:
    """The retail example, cleaned exactly as an upload would be."""
    path = SAMPLES_DIR / "retail_sales.csv"
    return prepare(path.read_bytes(), path.name).loaded.df, path.as_posix()


def _guard_blocks(sql: str) -> bool:
    try:
        validate_sql(sql)
    except SQLValidationError:
        return True
    return False


def _sandbox_blocks(df: pd.DataFrame, sql: str) -> bool:
    with QueryEngine(df) as engine:
        try:
            engine.run(sql)
        except QueryError:
            return True
    return False


def run() -> dict:
    """Run the suite and return JSON-friendly results."""
    df, path = _sample()
    attacks, by_category = [], {}
    for attack in ATTACKS:
        sql = attack.sql.replace(FILE, path)
        row = {
            "category": attack.category,
            "sql": attack.sql.replace(FILE, "data.csv"),
            "guard_blocked": _guard_blocks(sql),
            "sandbox_blocked": _sandbox_blocks(df, sql) if attack.sandbox else None,
        }
        attacks.append(row)
        cat = by_category.setdefault(attack.category, {"category": attack.category, "queries": 0, "blocked": 0})
        cat["queries"] += 1
        cat["blocked"] += row["guard_blocked"]

    harmless = []
    with QueryEngine(df) as engine:
        for sql in HARMLESS:
            result = run_validated(engine, sql)
            harmless.append({
                "sql": sql,
                "ran": result.error is None,
                "rows": len(result.data),
                "error": result.error,
            })
    sandboxed = [a for a in attacks if a["sandbox_blocked"] is not None]
    capped = all(h["rows"] <= ASK_MAX_ROWS for h in harmless)
    return {
        "attacks": len(attacks),
        "guard_blocked": sum(a["guard_blocked"] for a in attacks),
        "sandbox_attacks": len(sandboxed),
        "sandbox_blocked": sum(bool(a["sandbox_blocked"]) for a in sandboxed),
        "harmless": len(harmless),
        "harmless_ran": sum(h["ran"] for h in harmless),
        "row_cap": ASK_MAX_ROWS,
        "row_cap_held": capped,
        "categories": list(by_category.values()),
        "attack_rows": attacks,
        "harmless_rows": harmless,
    }
