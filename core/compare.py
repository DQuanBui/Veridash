"""Compare two versions of a dataset: what changed, and where.

Typical use: last month's export against this month's. Both files go through
the normal pipeline (load, type, health check). The comparison then reports:

* **Columns:** added, removed, and columns whose detected type changed.
* **Rows and health:** row counts and the health score on each side, plus
  which health checks got better or worse.

The two typed tables are stacked into one DuckDB table with a side column
(``before`` / ``after``), so every comparison number comes from a single SQL
query that is shown to the user, like everything else in Veridash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.pipeline import Prepared

SIDE = "__veridash_side"
BEFORE, AFTER = "before", "after"


@dataclass
class ColumnDiff:
    """How the column sets differ."""

    common: list[str] = field(default_factory=list)  # same name and type on both sides
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    retyped: list[tuple[str, str, str]] = field(default_factory=list)  # (name, before type, after type)

    @property
    def unchanged(self) -> bool:
        """True when both files have the same columns with the same types."""
        return not (self.added or self.removed or self.retyped)


@dataclass
class HealthDiff:
    """Health score on each side, and checks that improved or got worse."""

    before: int
    after: int
    better: list[str] = field(default_factory=list)  # check labels whose penalty went down
    worse: list[str] = field(default_factory=list)


def column_diff(before: Prepared, after: Prepared) -> ColumnDiff:
    """Compare column names and detected types, keeping the after file's order."""
    b = {c.name: str(c.col_type) for c in before.profile.columns}
    a = {c.name: str(c.col_type) for c in after.profile.columns}
    diff = ColumnDiff()
    for name, kind in a.items():
        if name not in b:
            diff.added.append(name)
        elif b[name] != kind:
            diff.retyped.append((name, b[name], kind))
        else:
            diff.common.append(name)
    diff.removed = [name for name in b if name not in a]
    return diff


def health_diff(before: Prepared, after: Prepared) -> HealthDiff:
    """Score change plus the checks whose penalty moved."""
    hb, ha = before.health, after.health
    penalties = {c.key: c.penalty for c in hb.checks}
    out = HealthDiff(hb.score, ha.score)
    for check in ha.checks:
        old = penalties.get(check.key)
        if old is None or abs(check.penalty - old) < 0.05:
            continue
        (out.better if check.penalty < old else out.worse).append(check.label)
    return out


def stacked(before: Prepared, after: Prepared, columns: list[str]) -> pd.DataFrame:
    """Both typed tables, limited to ``columns``, stacked with a side column."""
    parts = []
    for side, prepared in ((BEFORE, before), (AFTER, after)):
        part = prepared.profile.df[columns].copy()
        for col in part.columns:
            if isinstance(part[col].dtype, pd.CategoricalDtype):
                part[col] = part[col].astype(object)
        part[SIDE] = side
        parts.append(part)
    return pd.concat(parts, ignore_index=True)
