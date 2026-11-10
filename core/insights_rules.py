"""Rule-based insights: the no-API-key path, with the same structure as AI output.

Every sentence is assembled from facts in the fact pack and formatted with
``core.formatting``, so rule-based text always passes the fact-check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from core.facts import Fact, FactPack
from core.formatting import fmt_signed_pct, pretty
from core.health import HealthReport
from core.recommender import ChartSpec, Selection, strength


@dataclass
class Statement:
    """A sentence plus the IDs of the facts it relies on."""

    text: str
    fact_ids: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """A recommendation framed as a testable hypothesis."""

    hypothesis: str
    evidence: str
    how_to_validate: str
    fact_ids: list[str] = field(default_factory=list)


@dataclass
class Insights:
    """Summary, findings, recommendations and caveats from either source."""

    summary: list[Statement]
    findings: list[Statement]
    recommendations: list[Recommendation]
    caveats: list[str]
    source: str = "rules"  # "rules" | "ai"
    model: str | None = None
    notice: str | None = None
    language: str = "English"

    def texts(self) -> list[str]:
        """All prose fields, in display order (used by the fact-checker)."""
        out = [s.text for s in self.summary] + [s.text for s in self.findings]
        for r in self.recommendations:
            out += [r.hypothesis, r.evidence, r.how_to_validate]
        return out + list(self.caveats)

    def cited_ids(self) -> set[str]:
        """Every fact ID cited anywhere."""
        ids: set[str] = set()
        for s in [*self.summary, *self.findings]:
            ids.update(s.fact_ids)
        for r in self.recommendations:
            ids.update(r.fact_ids)
        return ids

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form."""
        return asdict(self)


def _v(facts: dict[str, Fact], fid: str) -> str:
    return facts[fid].display


def _chart(charts: list[ChartSpec], key: str) -> ChartSpec | None:
    return next((c for c in charts if c.key == key), None)


def generate_rule_insights(
    pack: FactPack,
    selection: Selection,
    health: HealthReport,
    charts: list[ChartSpec],
) -> Insights:
    """Write insights deterministically from the fact pack."""
    f = pack.by_id()
    metric = selection.metric_label
    summary: list[Statement] = []
    findings: list[Statement] = []
    recs: list[Recommendation] = []
    caveats: list[str] = []

    # Summary 1: dataset and health
    period = ""
    ids = ["dataset.rows", "dataset.columns", "health.score"]
    if "dataset.date_start" in f:
        period = f" from {_v(f, 'dataset.date_start')} to {_v(f, 'dataset.date_end')}"
        ids += ["dataset.date_start", "dataset.date_end"]
    summary.append(
        Statement(
            f"The dataset has {_v(f, 'dataset.rows')} records across {_v(f, 'dataset.columns')} columns{period}, "
            f"with a data health score of {_v(f, 'health.score')}/{_v(f, 'health.score_max')} (grade {health.grade}).",
            ids,
        )
    )

    # Summary 2: headline metric and trend
    trend = _chart(charts, "trend")
    if "kpi.metric" in f:
        text = f"{metric} is {_v(f, 'kpi.metric')}"
        ids = ["kpi.metric"]
        if trend and "trend.change_pct" in f:
            change = float(f["trend.change_pct"].value)
            text += (
                f", and it changed {fmt_signed_pct(change)} between {_v(f, 'trend.first_period')} "
                f"and {_v(f, 'trend.last_period')}"
            )
            ids += ["trend.change_pct", "trend.first_period", "trend.last_period"]
        summary.append(Statement(text + ".", ids))
    else:
        summary.append(Statement(f"There is no numeric metric, so counts of the {_v(f, 'dataset.rows')} records are analysed.",
                                 ["dataset.rows"]))

    # Summary 3: concentration or rate
    rate = _chart(charts, "rate")
    top = _chart(charts, "top")
    share = _chart(charts, "share")
    # Share statements only make sense for additive metrics (SUM or COUNT).
    lead = top if top and "top.1.share_pct" in f else share if share and selection.agg != "AVG" else None
    if rate:
        cat = pretty(rate.meta["category"]).lower()
        flag = rate.y.replace("_rate_pct", "").replace("_", " ")
        summary.append(
            Statement(
                f"{_v(f, 'rate.1.label')} has the highest {flag} rate by {cat} at {_v(f, 'rate.1.rate_pct')}, "
                f"compared with {_v(f, 'rate.overall_pct')} overall.",
                ["rate.1.label", "rate.1.rate_pct", "rate.overall_pct"],
            )
        )
    elif lead:
        k = lead.key
        cat = pretty(lead.meta["category"]).lower()
        summary.append(
            Statement(
                f"{_v(f, f'{k}.1.label')} is the largest {cat}, contributing {_v(f, f'{k}.1.share_pct')} of the total.",
                [f"{k}.1.label", f"{k}.1.share_pct"],
            )
        )
    elif top:
        cat = pretty(top.meta["category"]).lower()
        summary.append(
            Statement(f"{_v(f, 'top.1.label')} has the highest {metric.lower()} by {cat} at {_v(f, 'top.1.value')}.",
                      ["top.1.label", "top.1.value"])
        )

    # Findings
    if trend:
        findings.append(
            Statement(
                f"{metric} peaked in {_v(f, 'trend.peak_period')} at {_v(f, 'trend.peak_value')}, versus "
                f"{_v(f, 'trend.first_value')} in {_v(f, 'trend.first_period')}.",
                ["trend.peak_period", "trend.peak_value", "trend.first_value", "trend.first_period"],
            )
        )
    drivers = _chart(charts, "drivers")
    if drivers and "drivers.1.change" in f:
        cat = pretty(drivers.meta["category"]).lower()
        moved = "added" if float(f["drivers.1.change"].value) > 0 else "removed"
        findings.append(
            Statement(
                f"From {_v(f, 'drivers.prev_period')} to {_v(f, 'drivers.last_period')}, {metric.lower()} changed by "
                f"{_v(f, 'drivers.total_change')}; by {cat}, {_v(f, 'drivers.1.label')} {moved} the most "
                f"({_v(f, 'drivers.1.change')}).",
                ["drivers.prev_period", "drivers.last_period", "drivers.total_change", "drivers.1.label",
                 "drivers.1.change"],
            )
        )
    for chart in (top, _chart(charts, "top_secondary")):
        if chart is None:
            continue
        k = chart.key
        cat = pretty(chart.meta["category"]).lower()
        n = sum(1 for fid in f if fid.startswith(f"{k}.") and fid.endswith(".label"))
        last = f"{k}.{n}"
        if f"{k}.1.share_pct" in f:
            text = (
                f"By {cat}, {_v(f, f'{k}.1.label')} leads with {_v(f, f'{k}.1.value')} "
                f"({_v(f, f'{k}.1.share_pct')} of the total), while {_v(f, last + '.label')} contributes "
                f"{_v(f, last + '.share_pct')}."
            )
            ids = [f"{k}.1.label", f"{k}.1.value", f"{k}.1.share_pct", f"{last}.label", f"{last}.share_pct"]
        else:
            text = (
                f"By {cat}, {_v(f, f'{k}.1.label')} has the highest {metric.lower()} ({_v(f, f'{k}.1.value')}) "
                f"and {_v(f, last + '.label')} the lowest shown ({_v(f, last + '.value')})."
            )
            ids = [f"{k}.1.label", f"{k}.1.value", f"{last}.label", f"{last}.value"]
        findings.append(Statement(text, ids))
    if rate:
        n = sum(1 for fid in f if fid.startswith("rate.") and fid.endswith(".label"))
        findings.append(
            Statement(
                f"The {rate.y.replace('_rate_pct', '').replace('_', ' ')} rate ranges from {_v(f, f'rate.{n}.rate_pct')} "
                f"({_v(f, f'rate.{n}.label')}) to {_v(f, 'rate.1.rate_pct')} ({_v(f, 'rate.1.label')}).",
                [f"rate.{n}.rate_pct", f"rate.{n}.label", "rate.1.rate_pct", "rate.1.label"],
            )
        )
    corr = _chart(charts, "correlation")
    if corr and len(findings) < 5:
        a, b, r = corr.meta["strongest"]
        fid = next(x.id for x in corr.facts if x.value == r)
        findings.append(
            Statement(
                f"{pretty(a)} and {pretty(b).lower()} have the strongest correlation in the data "
                f"({strength(r)}, r = {_v(f, fid)}).",
                [fid],
            )
        )
    dist = _chart(charts, "distribution")
    if dist and len(findings) < 5 and "distribution.median" in f:
        findings.append(
            Statement(
                f"The median {pretty(selection.metric or '').lower()} is {_v(f, 'distribution.median')}, and "
                f"{_v(f, 'distribution.mode_share_pct')} of values fall between {_v(f, 'distribution.mode_bin_start')} "
                f"and {_v(f, 'distribution.mode_bin_end')}.",
                ["distribution.median", "distribution.mode_share_pct", "distribution.mode_bin_start", "distribution.mode_bin_end"],
            )
        )

    # Recommendations (hypotheses)
    if lead:
        k = lead.key
        cat = pretty(lead.meta["category"]).lower()
        recs.append(
            Recommendation(
                hypothesis=f"{_v(f, f'{k}.1.label')} may be the main driver of {metric.lower()}, so changes there "
                "could have an outsized effect.",
                evidence=f"{_v(f, f'{k}.1.label')} contributes {_v(f, f'{k}.1.share_pct')} of the total by {cat}.",
                how_to_validate=f"Split the trend by {cat} and check whether the lead holds in every {selection.grain}, "
                "not just in aggregate.",
                fact_ids=[f"{k}.1.label", f"{k}.1.share_pct"],
            )
        )
    if rate:
        cat = pretty(rate.meta["category"]).lower()
        recs.append(
            Recommendation(
                hypothesis=f"Something specific to {_v(f, 'rate.1.label')} may be raising its rate above the rest.",
                evidence=f"{_v(f, 'rate.1.label')} is at {_v(f, 'rate.1.rate_pct')} versus {_v(f, 'rate.overall_pct')} overall, "
                f"based on {_v(f, 'rate.1.records')} records.",
                how_to_validate=f"Compare other columns for {_v(f, 'rate.1.label')} against other {cat} values, and test "
                "whether the gap is larger than chance given the group size.",
                fact_ids=["rate.1.label", "rate.1.rate_pct", "rate.overall_pct", "rate.1.records"],
            )
        )
    if trend and "trend.peak_period" in f:
        recs.append(
            Recommendation(
                hypothesis=f"{metric} may follow a seasonal or event-driven pattern around {_v(f, 'trend.peak_period')}.",
                evidence=f"The peak {selection.grain} reached {_v(f, 'trend.peak_value')}.",
                how_to_validate=f"Compare the same {selection.grain} across years and check for one-off events or large "
                "single records in that period.",
                fact_ids=["trend.peak_period", "trend.peak_value"],
            )
        )
    if corr and abs(corr.meta["strongest"][2]) >= 0.4:
        a, b, r = corr.meta["strongest"]
        fid = next(x.id for x in corr.facts if x.value == r)
        recs.append(
            Recommendation(
                hypothesis=f"{pretty(a)} and {pretty(b).lower()} may be linked, or one may be derived from the other.",
                evidence=f"Their correlation is r = {_v(f, fid)}.",
                how_to_validate="Check how each column is calculated; if they are independent, compare groups "
                "or run a controlled test before acting on the relationship.",
                fact_ids=[fid],
            )
        )
    if health.score < 90:
        recs.insert(
            0,
            Recommendation(
                hypothesis="Fixing the flagged data issues may change some of these figures.",
                evidence=f"The health score is {_v(f, 'health.score')}/{_v(f, 'health.score_max')} with "
                f"{_v(f, 'health.issues')} issue(s) flagged.",
                how_to_validate="Resolve the issues listed on the Overview tab, re-upload the file and compare the results.",
                fact_ids=["health.score", "health.issues"],
            ),
        )

    # Caveats
    for issue in health.issues:
        if issue.severity in ("high", "medium"):
            caveats.append(f"{issue.title}. {issue.why}")
    for chart in charts:
        caveats.extend(n + "." for n in chart.notes if n.startswith(("Sampled", "Latest")))
    caveats.append("Correlations show association, not causation.")
    caveats.append("Insights describe this file only; they do not account for data outside it.")

    return Insights(
        summary=summary[:3],
        findings=findings[:5],
        recommendations=recs[:4],
        caveats=list(dict.fromkeys(caveats))[:6],
        source="rules",
    )
