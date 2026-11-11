"""Cross-check: recompute the headline numbers with pandas, without any SQL.

Veridash computes every KPI and chart with DuckDB SQL. This suite rebuilds the
same numbers a second, independent way (plain pandas group-bys on the same
cleaned table) and checks that both agree. A bug in a SQL template would show
up here as a mismatch.

Covered: row and column counts, the KPIs, the trend (first, last, peak and
change), the top and share charts (values and shares), the change breakdown,
the rate chart, medians and every correlation.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from core.pipeline import Analysis
from core.recommender import ChartSpec, Selection, _slug
from core.settings import HEAVY_VISUAL_ROW_LIMIT

_FREQ = {"day": "D", "week": "W-SUN", "month": "M", "quarter": "Q"}
_INDEXED = re.compile(r"^(?P<family>[a-z_]+)\.(?P<index>\d+)\.(?P<field>[a-z_]+)$")


@dataclass
class CrossCheck:
    """Outcome for one dataset."""

    dataset: str
    checked: int = 0
    matched: int = 0
    mismatches: list[dict] = field(default_factory=list)
    headline: int = 0  # headline facts in the fact pack

    def compare(self, fact_id: str, sql_value: float, pandas_value: float) -> None:
        """Record one comparison."""
        self.checked += 1
        if abs(float(sql_value) - float(pandas_value)) <= 1e-6 * max(1.0, abs(float(pandas_value))):
            self.matched += 1
        else:
            self.mismatches.append({"fact_id": fact_id, "sql": float(sql_value), "pandas": float(pandas_value)})


def _agg(sel: Selection) -> Callable[[pd.Series], float]:
    if sel.agg == "COUNT" or sel.metric is None:
        return lambda s: float(len(s))
    if sel.agg == "AVG":
        return lambda s: float(s[sel.metric].mean())
    return lambda s: float(s[sel.metric].sum())


def _grouped(df: pd.DataFrame, by: str | pd.Series, sel: Selection) -> pd.Series:
    fn = _agg(sel)
    return df.groupby(by, dropna=True, observed=True).apply(fn, include_groups=False)


def _periods(df: pd.DataFrame, sel: Selection) -> tuple[pd.Series, pd.Series, bool]:
    """Metric by period, plus whether the last period is incomplete."""
    assert sel.date_col is not None
    dated = df[df[sel.date_col].notna()]
    period = dated[sel.date_col].dt.to_period(_FREQ[sel.grain]).dt.start_time
    series = _grouped(dated, period, sel).sort_index()
    last_end = pd.Period(series.index[-1], freq=_FREQ[sel.grain]).end_time.normalize()
    partial = dated[sel.date_col].max().normalize() < last_end
    return series, period, partial


def _facts(chart: ChartSpec) -> dict[str, float]:
    return {f.id: float(f.value) for f in chart.facts if f.is_numeric}


def _labels(chart: ChartSpec) -> dict[str, str]:
    """index -> group label for a chart's indexed facts."""
    out = {}
    for f in chart.facts:
        m = _INDEXED.match(f.id)
        if m and m["field"] == "label":
            out[m["index"]] = str(f.value)
    return out


def _check_groups(res: CrossCheck, chart: ChartSpec, values: pd.Series) -> None:
    """Compare ``family.i.value`` and ``family.i.share_pct`` with pandas."""
    facts, labels = _facts(chart), _labels(chart)
    total = float(values.sum())
    lookup = {str(k): float(v) for k, v in values.items()}
    for idx, label in labels.items():
        if label not in lookup:
            continue
        if (fid := f"{chart.key}.{idx}.value") in facts:
            res.compare(fid, facts[fid], lookup[label])
        if (fid := f"{chart.key}.{idx}.share_pct") in facts:
            res.compare(fid, facts[fid], 100.0 * lookup[label] / total)


def cross_check(key: str, analysis: Analysis) -> CrossCheck:
    """Recompute ``analysis``'s headline numbers with pandas and compare."""
    df, sel = analysis.prepared.loaded.df, analysis.selection
    res = CrossCheck(key)
    res.headline = sum(1 for f in analysis.facts.facts if f.is_numeric and f.source not in ("profile", "health"))
    kpis = {k.key: k.value for k in analysis.kpis if k.value is not None}

    facts_all = {f.id: float(f.value) for f in analysis.facts.facts if f.is_numeric}
    res.compare("dataset.rows", facts_all["dataset.rows"], float(len(df)))
    res.compare("dataset.columns", facts_all["dataset.columns"], float(df.shape[1]))
    if "metric" in kpis:
        res.compare("kpi.metric", kpis["metric"], _agg(sel)(df))
    if "metric_secondary" in kpis and sel.metric:
        second = df[sel.metric].mean() if sel.agg == "SUM" else df[sel.metric].median()
        res.compare("kpi.metric_secondary", kpis["metric_secondary"], float(second))
    res.compare("kpi.records", kpis["records"], float(len(df)))
    if "bool_rate" in kpis and sel.booleans:
        res.compare("kpi.bool_rate", kpis["bool_rate"], 100.0 * df[sel.booleans[0]].dropna().astype(float).mean())

    complete = None
    if sel.date_col:
        series, _, partial = _periods(df, sel)
        complete = series.iloc[:-1] if partial else series
        if "period_change" in kpis and len(complete) >= 2:
            prev, last = complete.iloc[-2], complete.iloc[-1]
            res.compare("kpi.period_change", kpis["period_change"], 100.0 * (last - prev) / abs(prev))

    for chart in analysis.charts:
        facts = _facts(chart)
        cat = chart.meta.get("category")
        if chart.key == "trend" and complete is not None:
            res.compare("trend.first_value", facts["trend.first_value"], complete.iloc[0])
            res.compare("trend.last_value", facts["trend.last_value"], complete.iloc[-1])
            res.compare("trend.peak_value", facts["trend.peak_value"], series.max())
            res.compare("trend.periods", facts["trend.periods"], float(len(series)))
            if "trend.change_pct" in facts:
                first, last = complete.iloc[0], complete.iloc[-1]
                res.compare("trend.change_pct", facts["trend.change_pct"], 100.0 * (last - first) / abs(first))
        elif chart.key in ("top", "top_secondary") and cat:
            values = _grouped(df[df[cat].notna()], cat, sel)
            _check_groups(res, chart, values)
        elif chart.key == "share" and cat:
            share_sel = sel if sel.agg != "AVG" else Selection(None, "COUNT", None, sel.grain, [], [], [])
            _check_groups(res, chart, _grouped(df[df[cat].notna()], cat, share_sel))
        elif chart.key == "drivers" and cat and complete is not None:
            dated = df[df[sel.date_col].notna() & df[cat].notna()]
            period = dated[sel.date_col].dt.to_period(_FREQ[sel.grain]).dt.start_time
            prev_p, last_p = complete.index[-2], complete.index[-1]
            prev = _grouped(dated[period == prev_p], cat, sel)
            last = _grouped(dated[period == last_p], cat, sel)
            res.compare("drivers.total_change", facts["drivers.total_change"], complete.iloc[-1] - complete.iloc[-2])
            for idx, label in _labels(chart).items():
                p, latest = float(prev.get(label, 0.0)), float(last.get(label, 0.0))
                res.compare(f"drivers.{idx}.change", facts[f"drivers.{idx}.change"], latest - p)
                res.compare(f"drivers.{idx}.latest", facts[f"drivers.{idx}.latest"], latest)
        elif chart.key == "rate" and cat:
            flag = sel.booleans[0]
            sub = df[df[cat].notna() & df[flag].notna()]
            rates = sub.groupby(cat, observed=True)[flag].apply(lambda s: 100.0 * s.astype(float).mean())
            counts = sub.groupby(cat, observed=True)[flag].size()
            res.compare("rate.overall_pct", facts["rate.overall_pct"], 100.0 * sub[flag].astype(float).mean())
            for idx, label in _labels(chart).items():
                res.compare(f"rate.{idx}.rate_pct", facts[f"rate.{idx}.rate_pct"], float(rates[label]))
                res.compare(f"rate.{idx}.records", facts[f"rate.{idx}.records"], float(counts[label]))
        elif chart.key == "spread" and cat and sel.metric:
            medians = df[df[cat].notna()].groupby(cat, observed=True)[sel.metric].median()
            for idx, label in _labels(chart).items():
                res.compare(f"spread.{idx}.median", facts[f"spread.{idx}.median"], float(medians[label]))
        elif chart.key == "distribution" and sel.metric and len(df) <= HEAVY_VISUAL_ROW_LIMIT:
            if "distribution.median" in facts:
                res.compare("distribution.median", facts["distribution.median"], float(df[sel.metric].median()))
        elif chart.key == "correlation":
            for a, b in itertools.permutations(chart.meta["columns"], 2):
                if (fid := f"correlation.{_slug(a)}~{_slug(b)}") in facts:
                    res.compare(fid, facts[fid], float(df[a].corr(df[b])))
        elif chart.key == "scatter":
            a, b = chart.x, chart.y
            res.compare("scatter.r", facts["scatter.r"], float(df[a].corr(df[b])))
    return res


def run() -> dict:
    """Cross-check the three example datasets and return JSON-friendly results."""
    from core.pipeline import analyze, prepare
    from core.samples import EXAMPLES

    rows = []
    for ex in EXAMPLES.values():
        res = cross_check(ex.key, analyze(prepare(ex.read_bytes(), ex.filename)))
        rows.append({
            "dataset": ex.title, "checked": res.checked, "matched": res.matched,
            "headline": res.headline, "mismatches": res.mismatches,
        })
    return {
        "checked": sum(r["checked"] for r in rows),
        "matched": sum(r["matched"] for r in rows),
        "datasets": rows,
    }
