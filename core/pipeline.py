"""End-to-end analysis pipeline shared by the UI, exports and tests.

``prepare`` loads and profiles a file once; ``analyze`` builds everything that
depends on the user's metric/date/grain choices.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.engine import QueryEngine
from core.facts import FactPack, build_fact_pack
from core.health import HealthReport, assess_health
from core.insights_rules import Insights, generate_rule_insights
from core.loader import LoadedFile, load_file
from core.profiler import Profile, profile_dataframe
from core.recommender import KPI, ChartSpec, Selection, build_kpis, make_selection, recommend_charts


@dataclass
class Prepared:
    """A loaded, profiled and health-checked file.

    ``loaded.df`` holds the typed (cleaned) frame; the raw frame is dropped to
    keep memory use down.
    """

    loaded: LoadedFile
    profile: Profile
    health: HealthReport


@dataclass
class Analysis:
    """Everything shown on the Analyze page for one set of choices."""

    prepared: Prepared
    selection: Selection
    kpis: list[KPI]
    charts: list[ChartSpec]
    facts: FactPack
    rule_insights: Insights

    @property
    def name(self) -> str:
        """Original file name."""
        return self.prepared.loaded.name

    @property
    def profile(self) -> Profile:
        """Column profile."""
        return self.prepared.profile

    @property
    def health(self) -> HealthReport:
        """Health report."""
        return self.prepared.health


def prepare(data: bytes, filename: str, sheet: str | None = None) -> Prepared:
    """Load, type and health-check a file from raw bytes."""
    loaded = load_file(data, filename, sheet)
    profile = profile_dataframe(loaded.df)
    health = assess_health(profile)
    return Prepared(loaded=replace(loaded, df=profile.df), profile=profile, health=health)


def analyze(
    prepared: Prepared,
    metric: str | None = None,
    date_col: str | None = None,
    grain: str | None = None,
    use_date: bool = True,
) -> Analysis:
    """Select columns, compute KPIs and charts, and write rule-based insights."""
    profile = prepared.profile
    selection = make_selection(profile, metric=metric, date_col=date_col, grain=grain, use_date=use_date)
    with QueryEngine(profile.df) as engine:
        kpis = build_kpis(engine, profile, selection)
        charts = recommend_charts(engine, profile, selection)
    pack = build_fact_pack(prepared.loaded.name, profile, prepared.health, selection, kpis, charts)
    rules = generate_rule_insights(pack, selection, prepared.health, charts)
    return Analysis(prepared, selection, kpis, charts, pack, rules)
