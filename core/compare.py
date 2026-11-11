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

:func:`compare` runs all of it and also returns a fact pack and a short
plain-English summary built only from those facts, so the summary passes the
same fact-check as every other piece of text in the app.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.engine import QueryEngine, quote_ident, sql_literal
from core.facts import Fact, FactPack
from core.formatting import fmt_signed_pct, fmt_value, pretty
from core.pipeline import Prepared
from core.profiler import ColType
from core.recommender import TOP_N, ChartSpec, Selection, make_selection

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


@dataclass
class Comparison:
    """Everything the Compare page shows."""

    before_name: str
    after_name: str
    before: Prepared
    after: Prepared
    columns: ColumnDiff
    health: HealthDiff
    metric: MetricChange
    records: RecordChange | None
    facts: FactPack
    summary: list[str]

    @property
    def rows_before(self) -> int:
        """Rows in the before file."""
        return self.before.profile.n_rows

    @property
    def rows_after(self) -> int:
        """Rows in the after file."""
        return self.after.profile.n_rows

    def chart(self) -> ChartSpec | None:
        """The group changes as a diverging bar chart, if there are any."""
        m = self.metric
        if m.groups.empty or not m.group_col:
            return None
        sel = m.selection
        title = f"Where the change came from, by {pretty(m.group_col).lower()}"
        if sel.agg == "AVG":
            title = f"Change in {sel.metric_label.lower()}, by {pretty(m.group_col).lower()}"
        return ChartSpec("compare_groups", "bar", title, m.groups_sql, "label", "change", sel.value_kind, m.groups,
                         meta={"category": m.group_col, "diverging": True})


def _signed(value: float, kind: str) -> str:
    return ("+" if value >= 0 else "-") + fmt_value(abs(value), kind)


def _names(names: list[str]) -> str:
    shown = ", ".join(names[:3])
    return shown + (" and others" if len(names) > 3 else "")


def _facts_and_summary(c: Comparison) -> tuple[FactPack, list[str]]:
    """Facts for every number in the summary, then the summary itself."""
    m, sel, kind = c.metric, c.metric.selection, c.metric.selection.value_kind
    facts = [
        Fact("files.before", "Before file", c.before_name, "text", "compare"),
        Fact("files.after", "After file", c.after_name, "text", "compare"),
        Fact("rows.before", "Rows in the before file", c.rows_before, "int", "compare"),
        Fact("rows.after", "Rows in the after file", c.rows_after, "int", "compare"),
        Fact("rows.change", "Change in rows", c.rows_after - c.rows_before, "int", "compare"),
        Fact("columns.common", "Columns in both files", len(c.columns.common), "int", "compare"),
        Fact("columns.added", "Columns added", len(c.columns.added), "int", "compare"),
        Fact("columns.removed", "Columns removed", len(c.columns.removed), "int", "compare"),
        Fact("columns.retyped", "Columns that changed type", len(c.columns.retyped), "int", "compare"),
        Fact("health.before", "Health score of the before file", c.health.before, "int", "compare"),
        Fact("health.after", "Health score of the after file", c.health.after, "int", "compare"),
        Fact("health.score_max", "Maximum health score", 100, "int", "compare"),
    ]
    names = c.columns.added + c.columns.removed + [n for n, _, _ in c.columns.retyped]
    facts += [Fact(f"columns.name_{i}", "Column name", n, "text", "compare") for i, n in enumerate(names)]
    summary: list[str] = []

    diff = c.rows_after - c.rows_before
    if diff:
        summary.append(f"{c.after_name} has {c.rows_after:,} rows, {abs(diff):,} {'more' if diff > 0 else 'fewer'} "
                       f"than {c.before_name} ({c.rows_before:,}).")
    else:
        summary.append(f"Both files have {c.rows_after:,} rows.")

    cols = c.columns
    if cols.unchanged:
        summary.append(f"Both files have the same {len(cols.common)} columns.")
    else:
        parts = []
        if cols.added:
            parts.append(f"{len(cols.added)} added ({_names(cols.added)})")
        if cols.removed:
            parts.append(f"{len(cols.removed)} removed ({_names(cols.removed)})")
        if cols.retyped:
            parts.append(f"{len(cols.retyped)} changed type ({_names([n for n, _, _ in cols.retyped])})")
        summary.append("Columns: " + "; ".join(parts) + ".")

    if m.before is not None and m.after is not None:
        facts += [
            Fact("metric.before", f"{sel.metric_label} in the before file", m.before, kind, "compare"),
            Fact("metric.after", f"{sel.metric_label} in the after file", m.after, kind, "compare"),
            Fact("metric.change", f"Change in {sel.metric_label.lower()}", m.change, kind, "compare"),
        ]
        text = (f"{sel.metric_label} went from {fmt_value(m.before, kind)} to {fmt_value(m.after, kind)}, "
                f"a change of {_signed(m.change, kind)}")
        if m.change_pct is not None:
            facts.append(Fact("metric.change_pct", f"Change in {sel.metric_label.lower()}, %", m.change_pct,
                              "percent", "compare"))
            text += f" ({fmt_signed_pct(m.change_pct)})"
        summary.append(text + ".")

    if not m.groups.empty and m.group_col:
        facts.append(Fact("groups.column", "Grouped by", m.group_col, "text", "compare"))
        for i, row in enumerate(m.groups.itertuples(index=False), start=1):
            facts += [
                Fact(f"groups.{i}.label", f"#{i} mover by {m.group_col}", str(row.label), "text", "compare"),
                Fact(f"groups.{i}.before", f"{sel.metric_label} for {row.label}, before", float(row.before), kind, "compare"),
                Fact(f"groups.{i}.after", f"{sel.metric_label} for {row.label}, after", float(row.after), kind, "compare"),
                Fact(f"groups.{i}.change", f"Change for {row.label}", float(row.change), kind, "compare"),
            ]
        top = m.groups.iloc[0]
        text = f"By {pretty(m.group_col).lower()}, {top['label']} moved the most ({_signed(float(top['change']), kind)})"
        if m.change:
            against = m.groups[(m.groups["change"] > 0) != (m.change > 0)]
            if len(against) and against.index[0] != top.name:
                o = against.iloc[0]
                text += f", while {o['label']} moved the other way ({_signed(float(o['change']), kind)})"
        summary.append(text + ".")

    h = c.health
    if h.before != h.after:
        text = f"The data health score went from {h.before} to {h.after} out of 100"
    else:
        text = f"The data health score is {h.after} out of 100 in both files"
    details = []
    if h.better:
        details.append("better: " + ", ".join(x.lower() for x in h.better))
    if h.worse:
        details.append("worse: " + ", ".join(x.lower() for x in h.worse))
    summary.append(text + (f" ({'; '.join(details)})" if details else "") + ".")

    r = c.records
    if r is not None:
        facts += [
            Fact("records.id_column", "Matched on", r.id_col, "text", "compare"),
            Fact("records.added", "New records", r.added, "int", "compare"),
            Fact("records.removed", "Records no longer present", r.removed, "int", "compare"),
            Fact("records.kept", "Records in both files", r.kept, "int", "compare"),
        ]
        text = (f"Matching on {r.id_col}, {r.added:,} records are new, {r.removed:,} are gone and "
                f"{r.kept:,} appear in both")
        if r.changed is not None and sel.metric:
            facts.append(Fact("records.changed", f"Kept records whose {sel.metric} changed", r.changed, "int", "compare"))
            text += f"; {r.changed:,} of those changed {pretty(sel.metric).lower()}"
        summary.append(text + ".")

    dataset = {"before": c.before_name, "after": c.after_name, "metric": sel.metric, "aggregation": sel.agg}
    return FactPack(dataset=dataset, schema=[], facts=facts), summary


def compare(before: Prepared, after: Prepared, before_name: str = "Before", after_name: str = "After") -> Comparison:
    """Compare two prepared files (see the module docstring)."""
    cols = column_diff(before, after)
    sel = pick_selection(after, cols)
    with QueryEngine(stacked(before, after, cols.common)) as engine:
        metric = metric_change(engine, sel)
        records = record_change(engine, before, after, cols, sel)
    out = Comparison(before_name, after_name, before, after, cols, health_diff(before, after), metric, records,
                     FactPack({}, [], []), [])
    out.facts, out.summary = _facts_and_summary(out)
    return out
