"""Compare two versions of a dataset: what changed, and where.

Typical use: last month's export against this month's. Both files go through
the normal pipeline (load, type, health check). The comparison then reports:

* **Columns:** added, removed, and columns whose detected type changed.
* **Rows and health:** row counts and the health score on each side, plus
  which health checks got better or worse.
* **The main metric:** its value in each file, and which groups moved it most.
* **Records:** when both files share an ID column, which records are new,
  which are gone, and how many kept records changed value.

The two typed tables are stacked into one DuckDB table, ``data``, with a
``_file`` column saying which file each row came from (``before`` or
``after``). Every comparison number comes from one SQL query on that table,
shown to the user like everything else in Veridash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.engine import QueryEngine, quote_ident, sql_literal
from core.pipeline import Prepared
from core.profiler import ColType
from core.recommender import TOP_N, Selection, make_selection

SIDE = "_file"
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
        if name == SIDE:
            continue  # reserved for the side column
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


@dataclass
class MetricChange:
    """The main metric in each file, overall and by group."""

    selection: Selection
    sql: str
    before: float | None
    after: float | None
    group_col: str | None = None
    groups_sql: str = ""
    groups: pd.DataFrame = field(default_factory=pd.DataFrame)  # label, before, after, change

    @property
    def change(self) -> float | None:
        """After minus before."""
        if self.before is None or self.after is None:
            return None
        return self.after - self.before

    @property
    def change_pct(self) -> float | None:
        """Change as a percent of the before value."""
        if self.change is None or not self.before:
            return None
        return 100.0 * self.change / abs(self.before)


def pick_selection(after: Prepared, diff: ColumnDiff) -> Selection:
    """The metric and groups to compare, chosen from columns both files share."""
    profile = after.profile
    numeric = [n for n in diff.common if profile.get(n).col_type == ColType.NUMBER and not profile.get(n).is_constant]
    auto = make_selection(profile, use_date=False)
    metric = auto.metric if auto.metric in numeric else (numeric[0] if numeric else None)
    sel = make_selection(profile, metric=metric, use_date=False) if metric else auto
    if metric is None:
        sel = Selection(None, "COUNT", None, auto.grain, auto.categories, [], auto.booleans, "int")
    sel.categories = [c for c in sel.categories if c in diff.common]
    return sel


def _side(expr: str, side: str) -> str:
    return f"{expr} FILTER (WHERE {quote_ident(SIDE)} = {sql_literal(side)})"


def metric_change(engine: QueryEngine, sel: Selection) -> MetricChange:
    """Overall value on each side, then the groups that moved the most."""
    expr = sel.metric_expr()
    sql = f"SELECT {_side(expr, BEFORE)} AS before,\n       {_side(expr, AFTER)} AS after\nFROM data"
    row = engine.run(sql).df.iloc[0]
    num = lambda v: None if pd.isna(v) else float(v)  # noqa: E731
    out = MetricChange(sel, sql, num(row["before"]), num(row["after"]))
    if not sel.categories:
        return out
    cat = sel.categories[0]
    c = quote_ident(cat)
    additive = sel.agg != "AVG"
    b, a = _side(expr, BEFORE), _side(expr, AFTER)
    if additive:  # a group missing from one file counts as zero
        b, a = f"COALESCE({b}, 0)", f"COALESCE({a}, 0)"
    out.group_col = cat
    keep = "after <> before" if additive else "before IS NOT NULL AND after IS NOT NULL AND after <> before"
    out.groups_sql = (
        "SELECT label, before, after, after - before AS change\n"
        "FROM (\n"
        f"  SELECT {c} AS label,\n"
        f"         {b} AS before,\n"
        f"         {a} AS after\n"
        "  FROM data\n"
        f"  WHERE {c} IS NOT NULL\n"
        "  GROUP BY 1\n"
        ")\n"
        f"WHERE {keep}\n"
        f"ORDER BY abs(after - before) DESC, 1\nLIMIT {TOP_N}"
    )
    df = engine.run(out.groups_sql).df
    df["label"] = df["label"].astype(str)
    out.groups = df
    return out


@dataclass
class RecordChange:
    """Records matched by an ID column shared by both files."""

    id_col: str
    sql: str
    added: int
    removed: int
    kept: int
    changed: int | None = None  # kept records whose metric value changed (IDs must be unique)
    added_examples: list[str] = field(default_factory=list)
    removed_examples: list[str] = field(default_factory=list)


def _unique_ids(prepared: Prepared, col: str) -> bool:
    c = prepared.profile.get(col)
    return c.n_unique == prepared.profile.n_rows - c.n_missing


def record_change(
    engine: QueryEngine, before: Prepared, after: Prepared, diff: ColumnDiff, sel: Selection
) -> RecordChange | None:
    """Match records on the first ID column both files share, or return ``None``."""
    ids = [n for n in diff.common if after.profile.get(n).col_type == ColType.ID]
    if not ids:
        return None
    col = ids[0]
    k, f = quote_ident(col), quote_ident(SIDE)
    unique = _unique_ids(before, col) and _unique_ids(after, col)
    lines = [
        "WITH b AS (",
        f"  SELECT DISTINCT {k} AS id FROM data WHERE {f} = 'before' AND {k} IS NOT NULL",
        "), a AS (",
        f"  SELECT DISTINCT {k} AS id FROM data WHERE {f} = 'after' AND {k} IS NOT NULL",
        ")",
        "SELECT (SELECT COUNT(*) FROM a WHERE id NOT IN (SELECT id FROM b)) AS added,",
        "       (SELECT COUNT(*) FROM b WHERE id NOT IN (SELECT id FROM a)) AS removed,",
        "       (SELECT COUNT(*) FROM a WHERE id IN (SELECT id FROM b)) AS kept",
    ]
    if unique and sel.metric:
        m = quote_ident(sel.metric)
        lines[-1] += ","
        lines += [
            "       (SELECT COUNT(*)",
            f"        FROM (SELECT {k}, {m} FROM data WHERE {f} = 'before') AS old",
            f"        JOIN (SELECT {k}, {m} FROM data WHERE {f} = 'after') AS new USING ({k})",
            f"        WHERE new.{m} IS DISTINCT FROM old.{m}) AS changed",
        ]
    sql = "\n".join(lines)
    row = engine.run(sql).df.iloc[0]
    out = RecordChange(col, sql, int(row["added"]), int(row["removed"]), int(row["kept"]),
                       int(row["changed"]) if "changed" in row else None)

    def examples(side: str, other: str) -> list[str]:
        q = (f"SELECT DISTINCT CAST({k} AS VARCHAR) AS id FROM data WHERE {f} = '{side}' AND {k} IS NOT NULL "
             f"AND {k} NOT IN (SELECT {k} FROM data WHERE {f} = '{other}' AND {k} IS NOT NULL) ORDER BY 1 LIMIT 5")
        return engine.run(q).df["id"].tolist()

    out.added_examples = examples(AFTER, BEFORE) if out.added else []
    out.removed_examples = examples(BEFORE, AFTER) if out.removed else []
    return out
