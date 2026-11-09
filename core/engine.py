"""In-memory DuckDB session that runs SQL against the uploaded table.

Security model (defence in depth):

1. The connection is created with ``enable_external_access = false``, so SQL
   cannot read or write files, URLs or extensions, even if a query slips past
   validation. The setting is locked for the life of the connection.
2. User-facing SQL (Ask your data) is additionally checked by
   ``ai.nl2sql.validate_sql`` before it gets here.
3. Every query runs under a timeout and a row cap.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import duckdb
import pandas as pd

from core.settings import QUERY_TIMEOUT_S

TABLE = "data"


class QueryError(RuntimeError):
    """A query failed or timed out. The message is safe to show to users."""


@dataclass
class QueryResult:
    """The exact SQL that ran, its result and timing."""

    sql: str
    df: pd.DataFrame
    elapsed_ms: float
    truncated: bool = False


def quote_ident(name: str) -> str:
    """Quote a column name as a DuckDB identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    """Quote a string as a SQL literal."""
    return "'" + str(value).replace("'", "''") + "'"


class QueryEngine:
    """A sandboxed DuckDB connection with one registered table, ``data``."""

    def __init__(self, df: pd.DataFrame, table: str = TABLE) -> None:
        self.table = table
        self._con = duckdb.connect(
            database=":memory:",
            config={"enable_external_access": False, "threads": 2},
        )
        self._con.register(table, df)
        self._con.execute("SET lock_configuration = true")

    def run(self, sql: str, max_rows: int | None = None, timeout_s: float = QUERY_TIMEOUT_S) -> QueryResult:
        """Execute ``sql`` and return a :class:`QueryResult`.

        Args:
            sql: A single SQL statement.
            max_rows: Optional cap; extra rows are dropped and ``truncated`` is set.
            timeout_s: The query is interrupted after this many seconds.

        Raises:
            QueryError: If the query fails or exceeds the timeout.
        """
        statement = sql.strip().rstrip(";").strip()
        timer = threading.Timer(timeout_s, self._con.interrupt)
        start = time.perf_counter()
        timer.start()
        try:
            df = self._con.execute(statement).df()
        except duckdb.InterruptException as exc:
            raise QueryError(f"The query took longer than {timeout_s:g} seconds and was stopped.") from exc
        except duckdb.Error as exc:
            raise QueryError(f"The query could not run: {str(exc).splitlines()[0]}") from exc
        finally:
            timer.cancel()
        elapsed = (time.perf_counter() - start) * 1000
        truncated = False
        if max_rows is not None and len(df) > max_rows:
            df, truncated = df.head(max_rows), True
        return QueryResult(sql=statement, df=df, elapsed_ms=elapsed, truncated=truncated)

    def scalar(self, sql: str) -> object:
        """Run ``sql`` and return the first cell of the result (or ``None``)."""
        df = self.run(sql).df
        return None if df.empty else df.iat[0, 0]

    def close(self) -> None:
        """Close the underlying connection."""
        self._con.close()

    def __enter__(self) -> QueryEngine:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
