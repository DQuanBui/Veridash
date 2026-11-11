"""Comparison export: every compared figure as one tidy CSV.

One row per item (rows, columns, health, the main metric, each group and the
record counts) with its before value, after value, change and the SQL that
produced it, so the comparison can be filed or re-checked outside the app.
"""

from __future__ import annotations

import pandas as pd

from core.compare import Comparison

COLUMNS = ["section", "item", "before", "after", "change", "sql"]


def compare_table(c: Comparison) -> pd.DataFrame:
    """The comparison as a long table."""
    rows: list[dict] = [
        {"section": "Rows", "item": "Row count", "before": c.rows_before, "after": c.rows_after,
         "change": c.rows_after - c.rows_before},
        {"section": "Health", "item": "Health score (0-100)", "before": c.health.before, "after": c.health.after,
         "change": c.health.after - c.health.before},
    ]
    rows += [{"section": "Columns", "item": n, "before": "", "after": "added"} for n in c.columns.added]
    rows += [{"section": "Columns", "item": n, "before": "removed", "after": ""} for n in c.columns.removed]
    rows += [{"section": "Columns", "item": n, "before": b, "after": a, "change": "type changed"}
             for n, b, a in c.columns.retyped]
    m = c.metric
    rows.append({"section": "Metric", "item": m.selection.metric_label, "before": m.before, "after": m.after,
                 "change": m.change, "sql": m.sql})
    for g in m.groups.itertuples(index=False):
        rows.append({"section": f"By {m.group_col}", "item": g.label, "before": g.before, "after": g.after,
                     "change": g.change, "sql": m.groups_sql})
    r = c.records
    if r is not None:
        for item, value in (("New records", r.added), ("Records gone", r.removed), ("Records in both", r.kept),
                            ("Kept records with a changed value", r.changed)):
            if value is not None:
                rows.append({"section": f"Records by {r.id_col}", "item": item, "after": value, "sql": r.sql})
    return pd.DataFrame(rows, columns=COLUMNS).fillna("")


def build_compare_csv(c: Comparison) -> bytes:
    """The comparison table as UTF-8 CSV with a BOM, so Excel opens it cleanly."""
    return compare_table(c).to_csv(index=False).encode("utf-8-sig")
