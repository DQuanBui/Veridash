"""Ask your data: plain-English question -> one validated DuckDB SELECT.

Validation is layered on top of the engine's sandbox (external access is
disabled and locked). A query must be a single SELECT/WITH statement, may not
use blocked keywords or file/system functions, and always carries a LIMIT.
The SQL shown to the user is exactly the SQL that runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import duckdb
import pandas as pd

from ai.client import AIError, GeminiClient
from core.engine import QueryEngine, QueryError, quote_ident, sql_literal
from core.formatting import pretty
from core.profiler import ColType, Profile
from core.recommender import Selection, period_expr
from core.settings import ASK_MAX_ROWS, CATEGORY_LABELS_FOR_AI

BLOCKED_KEYWORDS = (
    "attach", "detach", "copy", "pragma", "install", "load", "export", "import", "create",
    "insert", "update", "delete", "drop", "alter", "set", "reset", "call", "checkpoint",
    "vacuum", "use", "grant", "revoke", "truncate", "begin", "commit", "rollback", "secret",
)
BLOCKED_FUNCTIONS = (
    "read_csv", "read_csv_auto", "read_parquet", "parquet_scan", "parquet_metadata",
    "parquet_schema", "read_json", "read_json_auto", "read_json_objects", "read_ndjson",
    "read_ndjson_auto", "read_ndjson_objects", "read_text", "read_blob", "read_xlsx",
    "sniff_csv", "glob", "csv_scan", "json_scan", "st_read", "iceberg_scan", "delta_scan",
    "sqlite_scan", "postgres_scan", "mysql_scan", "query", "query_table", "getenv",
    "duckdb_secrets", "duckdb_settings", "duckdb_extensions", "load_extension", "current_setting",
)
_LITERAL = re.compile(r"'(?:[^']|'')*'")
_QUOTED_IDENT = re.compile(r'"(?:[^"]|"")*"')
_LIMIT_TAIL = re.compile(r"\blimit\s+(\d+)\s*(offset\s+\d+\s*)?$", re.IGNORECASE)


class SQLValidationError(ValueError):
    """The query was rejected. The message is safe to show to users."""


def _masked(sql: str) -> str:
    """Blank out string literals and quoted identifiers, preserving length and positions."""
    text = _LITERAL.sub(lambda m: "'" + " " * (len(m.group(0)) - 2) + "'", sql)
    return _QUOTED_IDENT.sub(lambda m: '"' + "x" * (len(m.group(0)) - 2) + '"', text)


def validate_sql(sql: str, max_rows: int = ASK_MAX_ROWS) -> str:
    """Return a safe, LIMITed version of ``sql`` or raise :class:`SQLValidationError`.

    Rules: a single statement; SELECT or WITH only; no comments; no blocked
    keywords (ATTACH, COPY, PRAGMA, INSTALL, LOAD, writes...); no file-reading or
    system functions; no string literals as table sources; and a LIMIT of at
    most ``max_rows`` (added if missing).
    """
    text = (sql or "").strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise SQLValidationError("The query is empty.")
    if "--" in _masked(text) or "/*" in _masked(text):
        raise SQLValidationError("Comments are not allowed in queries.")
    masked = _masked(text)
    if ";" in masked:
        raise SQLValidationError("Only one statement is allowed.")
    lowered = masked.lower()
    if not re.match(r"^\(*\s*(select|with)\b", lowered):
        raise SQLValidationError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    for word in BLOCKED_KEYWORDS:
        if re.search(rf"\b{word}\b", lowered):
            raise SQLValidationError(f"The keyword {word.upper()} is not allowed.")
    for func in BLOCKED_FUNCTIONS:
        if re.search(rf"\b{func}\s*\(", lowered):
            raise SQLValidationError(f"The function {func}() is not allowed.")
    if re.search(r"\b(from|join)\s*\(?\s*'", lowered):
        raise SQLValidationError("Reading from files or URLs is not allowed.")

    try:
        with duckdb.connect(":memory:") as con:
            statements = con.extract_statements(text)
    except duckdb.Error as exc:
        raise SQLValidationError(f"The query could not be parsed: {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise SQLValidationError("Only one statement is allowed.")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise SQLValidationError("Only SELECT queries are allowed.")

    tail = _LIMIT_TAIL.search(masked)
    if tail is None:
        return f"{text}\nLIMIT {max_rows}"
    if int(tail.group(1)) > max_rows:
        start, end = tail.span(1)
        return text[:start] + str(max_rows) + text[end:]
    return text


def schema_context(profile: Profile) -> dict[str, Any]:
    """Schema for the model: names, types and up to 10 labels per category column.

    No raw rows are included. Category/boolean columns list their most common
    labels (at most ``CATEGORY_LABELS_FOR_AI``); numeric columns list min/max.
    """
    cols = []
    for c in profile.columns:
        entry: dict[str, Any] = {"name": c.name, "type": str(c.col_type), "distinct": c.n_unique}
        if c.col_type in (ColType.CATEGORY, ColType.BOOLEAN):
            entry["labels"] = [v for v, _ in c.top_values[:CATEGORY_LABELS_FOR_AI]]
        elif c.col_type == ColType.NUMBER and c.stats:
            entry["min"], entry["max"] = round(c.stats["min"], 4), round(c.stats["max"], 4)
        elif c.col_type == ColType.DATE and c.stats:
            entry["range"] = [
                pd.Timestamp(c.stats["min"], unit="s").strftime("%Y-%m-%d"),
                pd.Timestamp(c.stats["max"], unit="s").strftime("%Y-%m-%d"),
            ]
        cols.append(entry)
    return {"table": "data", "rows": profile.n_rows, "columns": cols}


NL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sql": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["sql", "explanation"],
}

NL_SYSTEM = """You translate a business question into ONE DuckDB SQL query.
The only table is named data. Its columns are described in the schema JSON.
Rules:
- Write a single SELECT (WITH ... SELECT is fine). Never modify data.
- Quote every column name with double quotes, exactly as given.
- Never use file, URL or system functions.
- Aggregate when the question asks for totals, averages, counts or rankings,
  give result columns clear snake_case aliases, and ORDER BY sensibly.
- For "top N" questions use LIMIT N. Otherwise LIMIT 100 at most.
- For dates use date_trunc('month', "col") etc. Category labels in the schema are exact values.
- If the question cannot be answered from these columns, return an empty sql string
  and say why in the explanation.
explanation: one plain-English sentence describing what the query returns."""


@dataclass
class AskResult:
    """The outcome of one question."""

    question: str
    sql: str = ""
    explanation: str = ""
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    elapsed_ms: float = 0.0
    truncated: bool = False
    error: str | None = None


def run_validated(engine: QueryEngine, sql: str, question: str = "", explanation: str = "") -> AskResult:
    """Validate and run ``sql``; errors are captured in the result."""
    result = AskResult(question=question, sql=sql, explanation=explanation)
    try:
        result.sql = validate_sql(sql)
        qr = engine.run(result.sql, max_rows=ASK_MAX_ROWS)
        result.data, result.elapsed_ms, result.truncated = qr.df, qr.elapsed_ms, qr.truncated
    except (SQLValidationError, QueryError) as exc:
        result.error = str(exc)
    return result


def ask(client: GeminiClient, engine: QueryEngine, profile: Profile, question: str) -> AskResult:
    """Turn ``question`` into SQL with Gemini, validate it and run it."""
    prompt = "SCHEMA (JSON):\n" + json.dumps(schema_context(profile), default=str) + f"\n\nQUESTION: {question}"
    try:
        payload = client.generate_json(prompt, NL_SCHEMA, NL_SYSTEM)
    except AIError as exc:
        return AskResult(question=question, error=str(exc))
    sql = str(payload.get("sql", "")).strip()
    explanation = str(payload.get("explanation", "")).strip()
    if not sql:
        return AskResult(question=question, explanation=explanation,
                         error=explanation or "That question cannot be answered from this file's columns.")
    return run_validated(engine, sql, question, explanation)


def example_questions(selection: Selection) -> list[str]:
    """Three starter questions tailored to the dataset's shape."""
    metric = pretty(selection.metric).lower() if selection.metric else "records"
    agg_word = "total" if selection.agg == "SUM" else "average" if selection.agg == "AVG" else "number of"
    cats = selection.categories
    qs = []
    if cats:
        qs.append(f"What is the {agg_word} {metric} by {pretty(cats[0]).lower()}?")
    if len(cats) > 1:
        qs.append(f"What are the top 5 values of {pretty(cats[1]).lower()} by {agg_word} {metric}?")
    elif cats:
        qs.append(f"Which {pretty(cats[0]).lower()} has the most records?")
    if selection.date_col:
        qs.append(f"How did the {agg_word} {metric} change by month?")
    if selection.booleans and cats:
        qs.append(f"What share of records have {pretty(selection.booleans[0]).lower()} true, by {pretty(cats[0]).lower()}?")
    if len(qs) < 3:
        qs.append(f"What are the minimum, average and maximum {metric}?")
    return qs[:3]


@dataclass
class Starter:
    """A ready-made question with hand-built SQL, runnable without an AI key."""

    question: str
    sql: str
    explanation: str


MAX_STARTER_COLUMNS = 15


def starter_queries(profile: Profile, selection: Selection) -> list[Starter]:
    """Up to five useful questions answered by plain SQL built from the schema."""
    sel = selection
    expr, alias = sel.metric_expr(), quote_ident(sel.metric_alias)
    label = sel.metric_label
    cats = sel.categories
    out: list[Starter] = []
    if cats:
        c = quote_ident(cats[0])
        out.append(Starter(
            f"{label} by {pretty(cats[0]).lower()}",
            f"SELECT {c}, {expr} AS {alias}, COUNT(*) AS records\nFROM data\nWHERE {c} IS NOT NULL\n"
            "GROUP BY 1\nORDER BY 2 DESC",
            f"Every {pretty(cats[0]).lower()} value, largest first, with its record count.",
        ))
    if sel.date_col:
        d = quote_ident(sel.date_col)
        out.append(Starter(
            f"{label} by {sel.grain}",
            f"SELECT {period_expr(sel.date_col, sel.grain)} AS {sel.grain}, {expr} AS {alias}\nFROM data\n"
            f"WHERE {d} IS NOT NULL\nGROUP BY 1\nORDER BY 1",
            f"The trend as a table, one row per {sel.grain}.",
        ))
    if len(cats) >= 2:
        a, b = quote_ident(cats[0]), quote_ident(cats[1])
        out.append(Starter(
            f"{label} by {pretty(cats[0]).lower()} and {pretty(cats[1]).lower()}",
            f"SELECT {a}, {b}, {expr} AS {alias}\nFROM data\nWHERE {a} IS NOT NULL AND {b} IS NOT NULL\n"
            "GROUP BY 1, 2\nORDER BY 3 DESC\nLIMIT 20",
            "The 20 largest combinations of the two main groups.",
        ))
    if sel.metric:
        m = quote_ident(sel.metric)
        out.append(Starter(
            f"10 largest records by {pretty(sel.metric).lower()}",
            f"SELECT *\nFROM data\nWHERE {m} IS NOT NULL\nORDER BY {m} DESC\nLIMIT 10",
            "Full rows for the biggest values, useful for spotting outliers.",
        ))
    columns = [col.name for col in profile.columns][:MAX_STARTER_COLUMNS]
    if columns:
        parts = [
            f"SELECT {sql_literal(name)} AS column_name, COUNT(*) - COUNT({quote_ident(name)}) AS missing, "
            f"COUNT(DISTINCT {quote_ident(name)}) AS distinct_values FROM data"
            for name in columns
        ]
        more = f" (the first {MAX_STARTER_COLUMNS})" if len(profile.columns) > MAX_STARTER_COLUMNS else ""
        out.append(Starter(
            "Missing and distinct values per column",
            "SELECT * FROM (\n  " + "\n  UNION ALL ".join(parts) + "\n)\nORDER BY missing DESC, column_name",
            f"A quick quality check: blanks and distinct values for each column{more}.",
        ))
    return out[:5]
