"""Facts: numbers computed by code, each with a stable ID.

A :class:`Fact` is the unit of trust in Veridash. Charts, KPIs, the health
check and the profile all emit facts; the fact pack bundles them for the AI,
and the fact-checker verifies AI text against them.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from core.formatting import fmt_value, metric_kind
from core.profiler import ColType

if TYPE_CHECKING:
    from core.health import HealthReport
    from core.profiler import Profile
    from core.recommender import KPI, ChartSpec, Selection


@dataclass
class Fact:
    """One computed value.

    Attributes:
        id: Stable dotted identifier, e.g. ``kpi.total`` or ``top_region.1.value``.
        label: Plain-English description of the value.
        value: The number (or a short string for labels/periods).
        kind: Display kind: currency, number, int, percent, ratio, date or text.
        source: Which component produced it (``kpi``, a chart key, ``health``...).
    """

    id: str
    label: str
    value: float | int | str
    kind: str = "number"
    source: str = ""

    @property
    def is_numeric(self) -> bool:
        """True if the value is a number (not a label)."""
        return isinstance(self.value, int | float) and not isinstance(self.value, bool)

    @property
    def display(self) -> str:
        """The value formatted for display."""
        if not self.is_numeric:
            return str(self.value)
        return fmt_value(float(self.value), self.kind)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict including the formatted display string."""
        out = asdict(self)
        if self.is_numeric:
            out["value"] = round(float(self.value), 6)
        out["display"] = self.display
        return out


@dataclass
class FactPack:
    """Everything the AI is allowed to see: schema plus computed facts.

    Raw rows are never included. Group labels appear only where they are part
    of an aggregated result (for example, the top 10 categories by revenue).
    """

    dataset: dict[str, Any]
    schema: list[dict[str, Any]]
    facts: list[Fact]

    def by_id(self) -> dict[str, Fact]:
        """Facts keyed by ID."""
        return {f.id: f for f in self.facts}

    def numeric(self) -> list[Fact]:
        """Only the facts that hold numbers."""
        return [f for f in self.facts if f.is_numeric]

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly representation used in prompts and exports."""
        return {
            "dataset": self.dataset,
            "schema": self.schema,
            "facts": [f.to_dict() for f in self.facts],
        }

    def to_json(self) -> str:
        """Compact JSON string for prompts."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"), default=str)


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", str(name).lower()).strip("_") or "col"


def build_fact_pack(
    name: str,
    profile: Profile,
    health: HealthReport,
    selection: Selection,
    kpis: list[KPI],
    charts: list[ChartSpec],
) -> FactPack:
    """Assemble the fact pack from results the code has already computed."""
    facts: list[Fact] = [
        Fact("dataset.rows", "Number of records", profile.n_rows, "int", "dataset"),
        Fact("dataset.columns", "Number of columns", profile.n_cols, "int", "dataset"),
        Fact("health.score", "Data health score (0-100)", health.score, "int", "health"),
        Fact("health.grade", "Data health grade", health.grade, "text", "health"),
        Fact("health.missing_pct", "Missing cells, % of all cells", health.missing_pct, "percent", "health"),
        Fact("health.duplicate_rows", "Duplicate rows", health.duplicate_rows, "int", "health"),
        Fact(
            "health.duplicate_pct",
            "Duplicate rows, % of rows",
            100.0 * health.duplicate_rows / profile.n_rows if profile.n_rows else 0.0,
            "percent",
            "health",
        ),
    ]
    dataset: dict[str, Any] = {
        "name": name,
        "rows": profile.n_rows,
        "columns": profile.n_cols,
        "primary_metric": selection.metric,
        "aggregation": selection.agg,
        "date_column": selection.date_col,
        "grain": selection.grain,
    }
    if selection.date_col:
        stats = profile.get(selection.date_col).stats
        start = datetime.fromtimestamp(stats["min"], tz=UTC).strftime("%Y-%m-%d")
        end = datetime.fromtimestamp(stats["max"], tz=UTC).strftime("%Y-%m-%d")
        dataset["date_range"] = [start, end]
        facts += [
            Fact("dataset.date_start", f"Earliest {selection.date_col}", start, "date", "dataset"),
            Fact("dataset.date_end", f"Latest {selection.date_col}", end, "date", "dataset"),
        ]
    for check in health.checks:
        facts.append(Fact(f"health.{check.key}.penalty", f"Penalty for {check.label}", check.penalty, "number", "health"))
    for kpi in kpis:
        if kpi.value is not None:
            kind = "percent" if kpi.kind == "signed_percent" else kpi.kind
            facts.append(Fact(f"kpi.{kpi.key}", kpi.label, kpi.value, kind, "kpi"))
    for chart in charts:
        facts.extend(chart.facts)

    schema: list[dict[str, Any]] = []
    for col in profile.columns:
        schema.append(
            {
                "name": col.name,
                "type": str(col.col_type),
                "missing_pct": round(col.missing_pct, 2),
                "distinct": col.n_unique,
                "unit": col.unit,
            }
        )
    for col in profile.columns[:30]:
        s = _slug(col.name)
        if col.missing_pct:
            facts.append(Fact(f"profile.{s}.missing_pct", f"Missing share of {col.name}", col.missing_pct, "percent", "profile"))
        if col.col_type == ColType.NUMBER and col.stats:
            kind = metric_kind(col.name, col.unit)
            for stat in ("mean", "median", "min", "max"):
                facts.append(Fact(f"profile.{s}.{stat}", f"{stat.title()} of {col.name}", col.stats[stat], kind, "profile"))
            facts.append(
                Fact(f"profile.{s}.outlier_pct", f"IQR outlier share of {col.name}", col.stats["outlier_pct"], "percent", "profile")
            )
        elif col.col_type in (ColType.CATEGORY, ColType.BOOLEAN):
            facts.append(Fact(f"profile.{s}.distinct", f"Distinct values of {col.name}", col.n_unique, "int", "profile"))
    return FactPack(dataset=dataset, schema=schema, facts=facts)
