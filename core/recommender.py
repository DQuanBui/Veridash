"""Choose KPIs and charts from the shape of the data, each backed by real SQL.

Every :class:`KPI` and :class:`ChartSpec` carries the exact DuckDB SQL that
produced its numbers. The UI shows that SQL verbatim in "How this was
calculated", and the one-sentence insight on each chart is written from the
query result, never estimated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.engine import QueryEngine, quote_ident, sql_literal
from core.facts import Fact
from core.formatting import fmt_period, fmt_signed_pct, fmt_value, metric_kind, pretty
from core.profiler import ColType, Profile
from core.settings import HEAVY_VISUAL_ROW_LIMIT, SCATTER_MAX_POINTS

GRAINS = ("day", "week", "month", "quarter")
METRIC_PRIORITY = (
    "revenue", "sales", "amount", "profit", "market_value", "value", "gain", "income", "cost",
    "spend", "quantity", "units", "price", "salary", "satisfaction", "rating", "score", "tenure",
)
AVG_HINTS = (
    "price", "rate", "ratio", "pct", "percent", "score", "rating", "satisfaction", "age",
    "tenure", "salary", "margin", "discount", "avg", "mean", "nps", "temperature",
)
CATEGORY_HINTS = (
    "region", "category", "segment", "channel", "department", "sector", "type", "country",
    "state", "city", "team", "product", "store", "role", "ticker", "brand", "class", "group",
    "band", "status",
)
BOOLEAN_HINTS = ("attrition", "churn", "returned", "return", "converted", "default", "fraud", "cancel")
TOP_N = 10
MAX_CHARTS = 8
MAX_CORR_COLUMNS = 8
HIST_BINS = 20
SAMPLE_SEED = 42


@dataclass
class Selection:
    """The columns and aggregation the analysis is built around."""

    metric: str | None
    agg: str  # SUM | AVG | COUNT
    date_col: str | None
    grain: str
    categories: list[str]
    numerics: list[str]
    booleans: list[str]
    metric_kind: str = "number"

    @property
    def metric_label(self) -> str:
        """Readable label such as ``Total revenue`` or ``Average satisfaction``."""
        if self.metric is None or self.agg == "COUNT":
            return "Records"
        prefix = "Total" if self.agg == "SUM" else "Average"
        return f"{prefix} {pretty(self.metric).lower()}"

    @property
    def metric_alias(self) -> str:
        """SQL alias for the aggregated metric, e.g. ``total_revenue``."""
        return re.sub(r"\W+", "_", self.metric_label.lower()).strip("_")

    def metric_expr(self) -> str:
        """SQL aggregate expression for the metric."""
        if self.metric is None or self.agg == "COUNT":
            return "COUNT(*)"
        return f"{self.agg}({quote_ident(self.metric)})"

    @property
    def value_kind(self) -> str:
        """Display kind of the aggregated metric."""
        return "int" if self.agg == "COUNT" or self.metric is None else self.metric_kind


@dataclass
class KPI:
    """A headline number with the SQL that produced it."""

    key: str
    label: str
    value: float | None
    kind: str
    sql: str
    note: str = ""

    @property
    def display(self) -> str:
        """Formatted value."""
        if self.value is None:
            return "n/a"
        if self.kind == "signed_percent":
            return fmt_signed_pct(self.value)
        return fmt_value(self.value, self.kind)


@dataclass
class ChartSpec:
    """A recommended chart: its SQL, result data, insight and facts."""

    key: str
    kind: str  # line | bar | donut | histogram | box | heatmap | scatter
    title: str
    sql: str
    x: str
    y: str
    value_kind: str = "number"
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    insight: str = ""
    facts: list[Fact] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- selection


def _usable_numeric(profile: Profile) -> list[str]:
    return [c.name for c in profile.columns if c.col_type == ColType.NUMBER and not c.is_constant]


def _priority_index(name: str, hints: tuple[str, ...]) -> int:
    lowered = name.lower()
    for i, hint in enumerate(hints):
        if lowered == hint:
            return i * 2
        if hint in lowered:
            return i * 2 + 1
    return len(hints) * 2 + 1


def pick_metric(profile: Profile, override: str | None = None) -> str | None:
    """Pick the primary metric from a priority list (or honour an override)."""
    numerics = _usable_numeric(profile)
    if override in numerics:
        return override
    if not numerics:
        return None
    return min(numerics, key=lambda n: (_priority_index(n, METRIC_PRIORITY), numerics.index(n)))


def aggregation_for(metric: str | None) -> str:
    """SUM for additive measures, AVG for rates, scores and prices."""
    if metric is None:
        return "COUNT"
    return "AVG" if any(h in metric.lower() for h in AVG_HINTS) else "SUM"


def pick_date(profile: Profile, override: str | None = None) -> str | None:
    """Pick the date column with the most non-missing values (or the override)."""
    dates = [c for c in profile.columns if c.col_type == ColType.DATE and c.n_unique > 1]
    names = [c.name for c in dates]
    if override in names:
        return override
    if not dates:
        return None
    return min(dates, key=lambda c: c.n_missing).name


def default_grain(profile: Profile, date_col: str | None) -> str:
    """Choose a grain that gives a readable number of periods."""
    if date_col is None:
        return "month"
    span = profile.get(date_col).stats.get("span_days", 0)
    if span <= 62:
        return "day"
    if span <= 270:
        return "week"
    if span <= 1100:
        return "month"
    return "quarter"


def rank_categories(profile: Profile) -> list[str]:
    """Categories suitable for grouping, best first (hint order, then fewer values)."""
    candidates = [
        c
        for c in profile.columns
        if c.col_type == ColType.CATEGORY and 2 <= c.n_unique <= 50 and c.missing_pct < 50
    ]
    candidates.sort(key=lambda c: (_priority_index(c.name, CATEGORY_HINTS), c.n_unique))
    return [c.name for c in candidates]


def make_selection(
    profile: Profile,
    metric: str | None = None,
    date_col: str | None = None,
    grain: str | None = None,
    use_date: bool = True,
) -> Selection:
    """Build the analysis :class:`Selection`, applying any sidebar overrides."""
    chosen_metric = pick_metric(profile, metric)
    chosen_date = pick_date(profile, date_col) if use_date else None
    booleans = sorted(
        profile.names(ColType.BOOLEAN), key=lambda n: _priority_index(n, BOOLEAN_HINTS)
    )
    numerics = sorted(
        _usable_numeric(profile), key=lambda n: (n != chosen_metric, _priority_index(n, METRIC_PRIORITY))
    )
    unit = profile.get(chosen_metric).unit if chosen_metric else None
    return Selection(
        metric=chosen_metric,
        agg=aggregation_for(chosen_metric),
        date_col=chosen_date,
        grain=grain if grain in GRAINS else default_grain(profile, chosen_date),
        categories=rank_categories(profile),
        numerics=numerics,
        booleans=booleans,
        metric_kind=metric_kind(chosen_metric, unit) if chosen_metric else "int",
    )


# ---------------------------------------------------------------- helpers


def period_expr(date_col: str, grain: str) -> str:
    """SQL expression truncating ``date_col`` to the start of each period."""
    col = quote_ident(date_col)
    if grain == "day":
        return f"CAST({col} AS DATE)"
    return f"CAST(date_trunc('{grain}', {col}) AS DATE)"


def _source(profile: Profile) -> tuple[str, str | None]:
    """FROM clause for heavy visuals, sampled above the row limit."""
    if profile.n_rows > HEAVY_VISUAL_ROW_LIMIT:
        note = f"Sampled {HEAVY_VISUAL_ROW_LIMIT:,} of {profile.n_rows:,} rows"
        return (
            f"(SELECT * FROM data USING SAMPLE reservoir({HEAVY_VISUAL_ROW_LIMIT} ROWS) "
            f"REPEATABLE ({SAMPLE_SEED}))",
            note,
        )
    return "data", None


_FREQ = {"day": "D", "week": "W-SUN", "month": "M", "quarter": "Q"}


def _is_partial(period_start: object, grain: str, max_date: pd.Timestamp) -> bool:
    end = pd.Period(pd.Timestamp(period_start), freq=_FREQ[grain]).end_time.normalize()
    return max_date.normalize() < end


def _pct_change(first: float, last: float) -> float | None:
    if first in (0, None) or pd.isna(first) or pd.isna(last):
        return None
    return 100.0 * (last - first) / abs(first)


def _f(chart: str, name: str, label: str, value: Any, kind: str) -> Fact:
    if isinstance(value, float | int) and not isinstance(value, bool):
        value = float(value)
    return Fact(id=f"{chart}.{name}", label=label, value=value, kind=kind, source=chart)


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", name.lower()).strip("_") or "col"


# ---------------------------------------------------------------- KPIs


def build_kpis(engine: QueryEngine, profile: Profile, sel: Selection) -> list[KPI]:
    """Compute up to four headline KPIs on the full dataset."""
    kpis: list[KPI] = []
    if sel.metric:
        m = quote_ident(sel.metric)
        sql = f"SELECT {sel.metric_expr()} AS {quote_ident(sel.metric_alias)}\nFROM data"
        kpis.append(KPI("metric", sel.metric_label, _num(engine.scalar(sql)), sel.value_kind, sql))
        if sel.agg == "SUM":
            sql2 = f"SELECT AVG({m}) AS {quote_ident('average_' + _slug(sel.metric))}\nFROM data"
            label2 = f"Average {pretty(sel.metric).lower()} per record"
        else:
            sql2 = f"SELECT median({m}) AS {quote_ident('median_' + _slug(sel.metric))}\nFROM data"
            label2 = f"Median {pretty(sel.metric).lower()}"
        kpis.append(KPI("metric_secondary", label2, _num(engine.scalar(sql2)), sel.value_kind, sql2))

    sql_rows = "SELECT COUNT(*) AS records\nFROM data"
    kpis.append(KPI("records", "Records", _num(engine.scalar(sql_rows)), "int", sql_rows))

    if sel.booleans:
        b = sel.booleans[0]
        sql_b = (
            f"SELECT 100.0 * AVG(CAST({quote_ident(b)} AS INTEGER)) AS {quote_ident(_slug(b) + '_rate_pct')}\n"
            "FROM data"
        )
        kpis.append(KPI("bool_rate", f"{pretty(b)} rate", _num(engine.scalar(sql_b)), "percent", sql_b,
                        note=f"Share of rows where {b} is true"))
    elif sel.date_col:
        kpis.append(_period_change_kpi(engine, profile, sel))
    elif sel.categories:
        c = sel.categories[0]
        sql_c = f"SELECT COUNT(DISTINCT {quote_ident(c)}) AS {quote_ident('distinct_' + _slug(c))}\nFROM data"
        kpis.append(KPI("distinct", f"Distinct {pretty(c).lower()}", _num(engine.scalar(sql_c)), "int", sql_c))
    return kpis[:4]


def _num(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _period_change_kpi(engine: QueryEngine, profile: Profile, sel: Selection) -> KPI:
    sql = _trend_sql(sel)
    df = engine.run(sql).df
    max_date = pd.Timestamp(profile.get(sel.date_col).stats["max"], unit="s")
    if len(df) and _is_partial(df["period"].iloc[-1], sel.grain, max_date):
        df = df.iloc[:-1]
    value = None
    note = ""
    if len(df) >= 2:
        prev, last = df.iloc[-2, 1], df.iloc[-1, 1]
        value = _pct_change(prev, last)
        note = f"{fmt_period(df['period'].iloc[-1], sel.grain)} vs {fmt_period(df['period'].iloc[-2], sel.grain)}"
    return KPI("period_change", f"Latest {sel.grain} vs prior", value, "signed_percent", sql, note=note)


# ---------------------------------------------------------------- charts


def _trend_sql(sel: Selection) -> str:
    assert sel.date_col is not None
    return (
        f"SELECT {period_expr(sel.date_col, sel.grain)} AS period,\n"
        f"       {sel.metric_expr()} AS {quote_ident(sel.metric_alias)}\n"
        f"FROM data\nWHERE {quote_ident(sel.date_col)} IS NOT NULL\nGROUP BY 1\nORDER BY 1"
    )


def _trend(engine: QueryEngine, profile: Profile, sel: Selection) -> ChartSpec | None:
    if not sel.date_col:
        return None
    sql = _trend_sql(sel)
    df = engine.run(sql).df
    if len(df) < 2:
        return None
    y = sel.metric_alias
    title = f"{sel.metric_label} by {sel.grain}"
    if sel.date_col.lower() != "date":
        title += f" of {pretty(sel.date_col).lower()}"
    spec = ChartSpec("trend", "line", title, sql, "period", y, sel.value_kind, df)
    max_date = pd.Timestamp(profile.get(sel.date_col).stats["max"], unit="s")
    complete = df
    if _is_partial(df["period"].iloc[-1], sel.grain, max_date):
        complete = df.iloc[:-1]
        spec.notes.append(f"Latest {sel.grain} is incomplete and excluded from the change figure")
    first, last = complete.iloc[0], complete.iloc[-1]
    peak = df.loc[df[y].idxmax()]
    change = _pct_change(first[y], last[y])
    k, g = spec.key, sel.grain
    spec.facts = [
        _f(k, "first_period", f"First {g}", fmt_period(first["period"], g), "text"),
        _f(k, "first_value", f"{sel.metric_label} in first {g}", first[y], sel.value_kind),
        _f(k, "last_period", f"Last complete {g}", fmt_period(last["period"], g), "text"),
        _f(k, "last_value", f"{sel.metric_label} in last complete {g}", last[y], sel.value_kind),
        _f(k, "peak_period", f"Peak {g}", fmt_period(peak["period"], g), "text"),
        _f(k, "peak_value", f"{sel.metric_label} in peak {g}", peak[y], sel.value_kind),
        _f(k, "periods", f"Number of {g}s", len(df), "int"),
    ]
    if change is not None:
        spec.facts.append(_f(k, "change_pct", f"Change from first to last complete {g}", change, "percent"))
    direction = "rose" if (change or 0) > 0 else "fell" if (change or 0) < 0 else "held steady"
    change_txt = f" ({fmt_signed_pct(change)})" if change is not None else ""
    spec.insight = (
        f"{sel.metric_label} {direction} from {fmt_value(first[y], sel.value_kind)} in "
        f"{fmt_period(first['period'], g)} to {fmt_value(last[y], sel.value_kind)} in "
        f"{fmt_period(last['period'], g)}{change_txt}, peaking in {fmt_period(peak['period'], g)} "
        f"at {fmt_value(peak[y], sel.value_kind)}."
    )
    return spec


def _top_sql(sel: Selection, cat: str, with_share: bool, limit: int | None) -> str:
    c = quote_ident(cat)
    alias = quote_ident(sel.metric_alias)
    lines = [f"SELECT {c} AS {c},", f"       {sel.metric_expr()} AS {alias}"]
    if with_share:
        lines[-1] += ","
        lines.append(f"       100.0 * {sel.metric_expr()} / SUM({sel.metric_expr()}) OVER () AS share_pct")
    elif sel.agg == "AVG":
        lines[-1] += ","
        lines.append("       COUNT(*) AS records")
    lines += ["FROM data", f"WHERE {c} IS NOT NULL", "GROUP BY 1", "ORDER BY 2 DESC"]
    if limit:
        lines.append(f"LIMIT {limit}")
    return "\n".join(lines)


def _top(engine: QueryEngine, profile: Profile, sel: Selection, cat: str, key: str) -> ChartSpec | None:
    with_share = sel.agg != "AVG"
    sql = _top_sql(sel, cat, with_share, TOP_N)
    df = engine.run(sql).df
    if df.empty:
        return None
    n_total = profile.get(cat).n_unique
    y = sel.metric_alias
    title = f"{sel.metric_label} by {pretty(cat).lower()}"
    if n_total > TOP_N:
        title = f"{sel.metric_label} by {pretty(cat).lower()} (top {TOP_N})"
    spec = ChartSpec(key, "bar", title, sql, cat, y, sel.value_kind, df, meta={"category": cat})
    if n_total > TOP_N:
        spec.notes.append(f"Showing top {TOP_N} of {n_total} values")
    spec.facts.append(_f(key, "distinct", f"Distinct {cat} values", n_total, "int"))
    for i, row in enumerate(df.itertuples(index=False), start=1):
        spec.facts.append(_f(key, f"{i}.label", f"#{i} {cat}", str(row[0]), "text"))
        spec.facts.append(_f(key, f"{i}.value", f"{sel.metric_label} for {row[0]}", row[1], sel.value_kind))
        if with_share:
            spec.facts.append(_f(key, f"{i}.share_pct", f"Share of total for {row[0]}", row[2], "percent"))
    top, bottom = df.iloc[0], df.iloc[-1]
    if with_share:
        spec.insight = (
            f"{top.iloc[0]} leads with {fmt_value(top[y], sel.value_kind)}, "
            f"{fmt_value(top['share_pct'], 'percent')} of the total"
        )
    else:
        spec.insight = f"{top.iloc[0]} has the highest {sel.metric_label.lower()} at {fmt_value(top[y], sel.value_kind)}"
    if len(df) > 1:
        spec.insight += f"; {bottom.iloc[0]} is lowest shown at {fmt_value(bottom[y], sel.value_kind)}."
    else:
        spec.insight += "."
    return spec


def _share(engine: QueryEngine, sel: Selection, cat: str) -> ChartSpec | None:
    share_sel = sel if sel.agg != "AVG" else Selection(None, "COUNT", None, sel.grain, [], [], [])
    sql = _top_sql(share_sel, cat, True, None)
    df = engine.run(sql).df
    if len(df) < 2:
        return None
    y = share_sel.metric_alias
    title = f"Share of {share_sel.metric_label.lower()} by {pretty(cat).lower()}"
    spec = ChartSpec("share", "donut", title, sql, cat, y, share_sel.value_kind, df, meta={"category": cat})
    for i, row in enumerate(df.itertuples(index=False), start=1):
        spec.facts.append(_f("share", f"{i}.label", f"#{i} {cat} by share", str(row[0]), "text"))
        spec.facts.append(_f("share", f"{i}.value", f"{share_sel.metric_label} for {row[0]}", row[1], share_sel.value_kind))
        spec.facts.append(_f("share", f"{i}.share_pct", f"Share for {row[0]}", row[2], "percent"))
    top = df.iloc[0]
    spec.insight = (
        f"{top.iloc[0]} accounts for the largest share at {fmt_value(top['share_pct'], 'percent')}, "
        f"across {len(df)} {pretty(cat).lower()} values."
    )
    return spec


def _rate(engine: QueryEngine, sel: Selection, flag: str, cat: str) -> ChartSpec | None:
    c, b = quote_ident(cat), quote_ident(flag)
    rate = quote_ident(_slug(flag) + "_rate_pct")
    sql = (
        f"SELECT {c} AS {c},\n"
        f"       100.0 * AVG(CAST({b} AS INTEGER)) AS {rate},\n"
        f"       COUNT({b}) AS records,\n"
        f"       100.0 * SUM(SUM(CAST({b} AS INTEGER))) OVER () / SUM(COUNT({b})) OVER () AS overall_rate_pct\n"
        f"FROM data\nWHERE {c} IS NOT NULL\nGROUP BY 1\nORDER BY 2 DESC"
    )
    df = engine.run(sql).df
    if df.empty:
        return None
    y = _slug(flag) + "_rate_pct"
    title = f"{pretty(flag)} rate by {pretty(cat).lower()}"
    spec = ChartSpec("rate", "bar", title, sql, cat, y, "percent", df, meta={"category": cat, "reference": "overall_rate_pct"})
    overall = float(df["overall_rate_pct"].iloc[0])
    spec.facts.append(_f("rate", "overall_pct", f"Overall {flag} rate", overall, "percent"))
    for i, row in enumerate(df.itertuples(index=False), start=1):
        spec.facts.append(_f("rate", f"{i}.label", f"#{i} {cat} by {flag} rate", str(row[0]), "text"))
        spec.facts.append(_f("rate", f"{i}.rate_pct", f"{pretty(flag)} rate for {row[0]}", row[1], "percent"))
        spec.facts.append(_f("rate", f"{i}.records", f"Records for {row[0]}", row[2], "int"))
    top, bottom = df.iloc[0], df.iloc[-1]
    spec.insight = (
        f"{top.iloc[0]} has the highest {flag} rate at {fmt_value(top[y], 'percent')} versus "
        f"{fmt_value(overall, 'percent')} overall; {bottom.iloc[0]} is lowest at {fmt_value(bottom[y], 'percent')}."
    )
    return spec


def _histogram(engine: QueryEngine, profile: Profile, sel: Selection, col: str) -> ChartSpec | None:
    prof = profile.get(col)
    src, sample_note = _source(profile)
    q = quote_ident(col)
    kind = metric_kind(col, prof.unit)
    integral = bool(profile.df[col].dropna().mod(1).eq(0).all()) if prof.n_unique else False
    if integral and prof.n_unique <= 30:
        sql = (
            f"SELECT {q} AS {q},\n       COUNT(*) AS records,\n"
            "       100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS share_pct\n"
            f"FROM {src}\nWHERE {q} IS NOT NULL\nGROUP BY 1\nORDER BY 1"
        )
        df = engine.run(sql).df
        if df.empty:
            return None
        spec = ChartSpec("distribution", "bar", f"Distribution of {pretty(col).lower()}", sql, col, "records", "int", df,
                         meta={"discrete": True, "x_kind": kind})
        mode = df.loc[df["records"].idxmax()]
        spec.facts += [
            _f("distribution", "mode_value", f"Most common {col}", mode.iloc[0], kind),
            _f("distribution", "mode_records", f"Records with most common {col}", mode["records"], "int"),
            _f("distribution", "mode_share_pct", f"Share with most common {col}", mode["share_pct"], "percent"),
        ]
        spec.insight = (
            f"The most common {pretty(col).lower()} is {fmt_value(mode.iloc[0], kind)}, "
            f"seen in {fmt_value(mode['records'], 'int')} records ({fmt_value(mode['share_pct'], 'percent')})."
        )
    else:
        sql = (
            f"WITH src AS (\n  SELECT {q} AS v FROM {src} WHERE {q} IS NOT NULL\n),\n"
            "bounds AS (\n  SELECT quantile_cont(v, 0.01) AS lo, quantile_cont(v, 0.99) AS hi,\n"
            "         median(v) AS median FROM src\n),\n"
            "binned AS (\n"
            f"  SELECT COALESCE(LEAST(GREATEST(FLOOR((v - lo) / NULLIF((hi - lo) / {HIST_BINS}, 0)), 0), {HIST_BINS - 1}), 0) AS bin,\n"
            "         lo, hi, median\n  FROM src, bounds\n)\n"
            "SELECT CAST(bin AS INTEGER) AS bin,\n"
            f"       ANY_VALUE(lo + bin * (hi - lo) / {HIST_BINS}) AS bin_start,\n"
            f"       ANY_VALUE(lo + (bin + 1) * (hi - lo) / {HIST_BINS}) AS bin_end,\n"
            "       COUNT(*) AS records,\n"
            "       100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS share_pct,\n"
            "       ANY_VALUE(median) AS median\n"
            "FROM binned\nGROUP BY bin\nORDER BY bin"
        )
        df = engine.run(sql).df
        if df.empty:
            return None
        spec = ChartSpec("distribution", "histogram", f"Distribution of {pretty(col).lower()}", sql, "bin_start", "records",
                         "int", df, meta={"x_kind": kind})
        spec.notes.append("Values beyond the 1st and 99th percentiles are grouped into the edge bins")
        mode = df.loc[df["records"].idxmax()]
        median = float(df["median"].iloc[0])
        spec.facts += [
            _f("distribution", "median", f"Median {col}", median, kind),
            _f("distribution", "mode_bin_start", f"Start of most common {col} range", mode["bin_start"], kind),
            _f("distribution", "mode_bin_end", f"End of most common {col} range", mode["bin_end"], kind),
            _f("distribution", "mode_records", f"Records in most common {col} range", mode["records"], "int"),
            _f("distribution", "mode_share_pct", f"Share in most common {col} range", mode["share_pct"], "percent"),
        ]
        spec.insight = (
            f"The median {pretty(col).lower()} is {fmt_value(median, kind)}; the most common range is "
            f"{fmt_value(mode['bin_start'], kind)} to {fmt_value(mode['bin_end'], kind)} "
            f"({fmt_value(mode['share_pct'], 'percent')} of values)."
        )
    if sample_note:
        spec.notes.append(sample_note)
    return spec


def _box(engine: QueryEngine, sel: Selection, cat: str) -> ChartSpec | None:
    if not sel.metric:
        return None
    c, m = quote_ident(cat), quote_ident(sel.metric)
    sql = (
        "WITH s AS (\n"
        f"  SELECT {c} AS grp,\n"
        f"         quantile_cont({m}, 0.25) AS q1, median({m}) AS median,\n"
        f"         quantile_cont({m}, 0.75) AS q3, MIN({m}) AS min_value,\n"
        f"         MAX({m}) AS max_value, COUNT({m}) AS records\n"
        f"  FROM data\n  WHERE {c} IS NOT NULL AND {m} IS NOT NULL\n  GROUP BY 1\n)\n"
        f"SELECT grp AS {c}, q1, median, q3,\n"
        "       GREATEST(min_value, q1 - 1.5 * (q3 - q1)) AS lower_fence,\n"
        "       LEAST(max_value, q3 + 1.5 * (q3 - q1)) AS upper_fence,\n"
        "       records\nFROM s\nORDER BY median DESC"
    )
    df = engine.run(sql).df
    if len(df) < 2:
        return None
    kind = sel.metric_kind
    title = f"Spread of {pretty(sel.metric).lower()} by {pretty(cat).lower()}"
    spec = ChartSpec("spread", "box", title, sql, cat, "median", kind, df, meta={"category": cat})
    for i, row in enumerate(df.itertuples(index=False), start=1):
        spec.facts.append(_f("spread", f"{i}.label", f"#{i} {cat} by median {sel.metric}", str(row[0]), "text"))
        spec.facts.append(_f("spread", f"{i}.median", f"Median {sel.metric} for {row[0]}", row[2], kind))
    top, bottom = df.iloc[0], df.iloc[-1]
    spec.insight = (
        f"{top.iloc[0]} has the highest median {pretty(sel.metric).lower()} ({fmt_value(top['median'], kind)}); "
        f"{bottom.iloc[0]} has the lowest ({fmt_value(bottom['median'], kind)})."
    )
    return spec


def strength(r: float) -> str:
    """Describe a correlation as strong, moderate or weak."""
    a = abs(r)
    return "strong" if a >= 0.7 else "moderate" if a >= 0.4 else "weak"


def _correlation(engine: QueryEngine, sel: Selection) -> ChartSpec | None:
    cols = sel.numerics[:MAX_CORR_COLUMNS]
    if len(cols) < 3:
        return None
    parts = [
        f"SELECT {sql_literal(a)} AS col_a, {sql_literal(b)} AS col_b, corr({quote_ident(a)}, {quote_ident(b)}) AS r FROM data"
        for i, a in enumerate(cols)
        for b in cols[i + 1 :]
    ]
    sql = "\nUNION ALL\n".join(parts)
    df = engine.run(sql).df.dropna(subset=["r"])
    if df.empty:
        return None
    spec = ChartSpec("correlation", "heatmap", "Correlation between numeric columns", sql, "col_a", "r", "ratio", df,
                     meta={"columns": cols})
    for row in df.itertuples(index=False):
        spec.facts.append(_f("correlation", f"{_slug(row.col_a)}~{_slug(row.col_b)}", f"Correlation of {row.col_a} and {row.col_b}", row.r, "ratio"))
    best = df.loc[df["r"].abs().idxmax()]
    spec.meta["strongest"] = (best["col_a"], best["col_b"], float(best["r"]))
    spec.insight = (
        f"The strongest relationship is between {pretty(best['col_a']).lower()} and {pretty(best['col_b']).lower()} "
        f"(r = {fmt_value(best['r'], 'ratio')}, {strength(best['r'])} {'positive' if best['r'] > 0 else 'negative'})."
    )
    spec.notes.append("Pearson correlation; it measures association, not causation")
    if abs(best["r"]) >= 0.95:
        spec.notes.append("A near-perfect correlation often means one column is derived from the other")
    return spec


def _scatter(engine: QueryEngine, profile: Profile, pair: tuple[str, str, float]) -> ChartSpec:
    a, b, r = pair
    qa, qb = quote_ident(a), quote_ident(b)
    inner = f"SELECT {qa}, {qb} FROM data WHERE {qa} IS NOT NULL AND {qb} IS NOT NULL"
    if profile.n_rows > SCATTER_MAX_POINTS:
        sql = f"SELECT {qa}, {qb}\nFROM ({inner})\nUSING SAMPLE reservoir({SCATTER_MAX_POINTS} ROWS) REPEATABLE ({SAMPLE_SEED})"
    else:
        sql = inner.replace(" FROM", "\nFROM").replace(" WHERE", "\nWHERE")
    df = engine.run(sql).df
    spec = ChartSpec("scatter", "scatter", f"{pretty(a)} vs {pretty(b).lower()}", sql, a, b,
                     metric_kind(b, profile.get(b).unit), df, meta={"r": r, "x_kind": metric_kind(a, profile.get(a).unit)})
    if profile.n_rows > SCATTER_MAX_POINTS:
        spec.notes.append(f"Sampled {len(df):,} points of {profile.n_rows:,} rows")
    spec.facts.append(_f("scatter", "r", f"Correlation of {a} and {b}", r, "ratio"))
    direction = "rises" if r > 0 else "falls"
    spec.insight = (
        f"As {pretty(a).lower()} increases, {pretty(b).lower()} generally {direction} "
        f"(r = {fmt_value(r, 'ratio')}, a {strength(r)} relationship)."
    )
    return spec


def recommend_charts(engine: QueryEngine, profile: Profile, sel: Selection) -> list[ChartSpec]:
    """Select and compute 4-8 charts based on the shape of the data."""
    cats = sel.categories
    share_cat = next((c for c in cats if profile.get(c).n_unique <= 8), None)
    top_candidates = [c for c in cats if profile.get(c).n_unique >= 3]
    top_cat = next((c for c in top_candidates if c != share_cat), top_candidates[0] if top_candidates else None)
    secondary = next((c for c in top_candidates if c not in (top_cat, share_cat)), None)
    group_cat = share_cat or top_cat

    charts: list[tuple[int, ChartSpec | None]] = []  # (priority, spec); lower priority dropped first
    charts.append((9, _trend(engine, profile, sel)))
    if top_cat:
        charts.append((8, _top(engine, profile, sel, top_cat, "top")))
    if share_cat:
        charts.append((7, _share(engine, sel, share_cat)))
    if sel.booleans and group_cat:
        charts.append((7, _rate(engine, sel, sel.booleans[0], group_cat)))
    if secondary:
        charts.append((3, _top(engine, profile, sel, secondary, "top_secondary")))
    if sel.metric:
        charts.append((6, _histogram(engine, profile, sel, sel.metric)))
    if sel.metric and group_cat:
        charts.append((2, _box(engine, sel, group_cat)))
    corr = _correlation(engine, sel)
    charts.append((5, corr))
    if corr is not None:
        charts.append((4, _scatter(engine, profile, corr.meta["strongest"])))
    elif len(sel.numerics) == 2:
        a, b = sel.numerics
        r = engine.scalar(f"SELECT corr({quote_ident(a)}, {quote_ident(b)}) FROM data")
        if r is not None and not pd.isna(r):
            charts.append((4, _scatter(engine, profile, (a, b, float(r)))))

    valid = [(p, c) for p, c in charts if c is not None and not c.data.empty]
    while len(valid) > MAX_CHARTS:
        valid.remove(min(valid, key=lambda pc: pc[0]))
    return [c for _, c in valid]
