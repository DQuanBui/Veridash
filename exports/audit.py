"""Audit trail: every computed number, its ID and the query behind it.

The CSV lets anyone re-check Veridash's work outside the app: each row is one
fact from the fact pack, with the exact SQL that produced it (for KPIs and
charts) or a note on where it was computed (health check, profile, dataset).
"""

from __future__ import annotations

import pandas as pd

from core.insights_rules import Insights
from core.pipeline import Analysis

_PYTHON_SOURCES = {
    "dataset": "Counted when the file was loaded (Python, full data)",
    "health": "Health check (Python, full data); see the Guide for the formula",
    "profile": "Column profile (Python, full data)",
}

COLUMNS = ["fact_id", "label", "value", "display", "kind", "source", "cited_in_insights", "computed_by", "sql"]


def audit_table(analysis: Analysis, insights: Insights | None = None) -> pd.DataFrame:
    """One row per fact, with the SQL or step that produced it."""
    sql_by_source = {chart.key: chart.sql for chart in analysis.charts}
    kpi_sql = {f"kpi.{kpi.key}": kpi.sql for kpi in analysis.kpis}
    cited = insights.cited_ids() if insights is not None else set()
    rows = []
    for fact in analysis.facts.facts:
        sql = kpi_sql.get(fact.id) or sql_by_source.get(fact.source, "")
        if sql:
            computed_by = "DuckDB SQL on the full data"
        else:
            computed_by = _PYTHON_SOURCES.get(fact.source, "Python")
        rows.append(
            {
                "fact_id": fact.id,
                "label": fact.label,
                "value": round(float(fact.value), 6) if fact.is_numeric else fact.value,
                "display": fact.display,
                "kind": fact.kind,
                "source": fact.source,
                "cited_in_insights": "yes" if fact.id in cited else "",
                "computed_by": computed_by,
                "sql": sql,
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def build_audit_csv(analysis: Analysis, insights: Insights | None = None) -> bytes:
    """The audit table as UTF-8 CSV (with a BOM so Excel opens it cleanly)."""
    return audit_table(analysis, insights).to_csv(index=False).encode("utf-8-sig")
