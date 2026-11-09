"""Data health score: a transparent 0-100 score with an itemised issues list.

Formula::

    score = 100 - sum(min(cap_i, points_per_unit_i * measure_i))

Each check's weight and cap live in :data:`HEALTH_WEIGHTS`, which the Guide
page renders directly so the documentation can never drift from the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.profiler import ColType, Profile

HEALTH_WEIGHTS: dict[str, dict[str, Any]] = {
    "missing_cells": {
        "label": "Missing cells",
        "unit": "% of all cells",
        "points_per_unit": 1.5,
        "cap": 30,
    },
    "duplicate_rows": {
        "label": "Duplicate rows",
        "unit": "% of rows",
        "points_per_unit": 2.0,
        "cap": 20,
    },
    "mixed_types": {
        "label": "Mixed-type columns",
        "unit": "columns",
        "points_per_unit": 5.0,
        "cap": 20,
    },
    "constant_columns": {
        "label": "Constant columns",
        "unit": "columns",
        "points_per_unit": 3.0,
        "cap": 10,
    },
    "outlier_columns": {
        "label": "High-outlier columns",
        "unit": "numeric columns with more than 5% IQR outliers",
        "points_per_unit": 3.0,
        "cap": 15,
    },
}
OUTLIER_SHARE_THRESHOLD = 5.0  # percent of a column's values outside 1.5 x IQR
GRADE_BANDS: list[tuple[int, str]] = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]

WHY = {
    "missing_cells": "Missing values shrink the sample behind every total and average, "
    "and can bias results when they are not random.",
    "duplicate_rows": "Duplicate rows count the same record twice, inflating totals and counts.",
    "mixed_types": "Values that are not numbers are left out of sums and averages, "
    "so totals for these columns may be understated.",
    "constant_columns": "A column with a single value carries no information for analysis.",
    "outlier_columns": "A few extreme values can dominate averages and stretch chart axes. "
    "Check whether they are errors or real events.",
    "id_columns": "Identifier columns are unique per row, so charting them is meaningless.",
}


@dataclass
class CheckResult:
    """Outcome of one weighted health check."""

    key: str
    label: str
    measure: float
    points_per_unit: float
    cap: float
    penalty: float


@dataclass
class Issue:
    """A user-facing data issue with a severity and a "why it matters" line."""

    severity: str  # high | medium | low | info
    title: str
    detail: str
    why: str
    check: str
    columns: list[str] = field(default_factory=list)


@dataclass
class HealthReport:
    """Overall score, grade, per-check penalties and issues."""

    score: int
    grade: str
    checks: list[CheckResult]
    issues: list[Issue]
    missing_cells: int
    total_cells: int
    duplicate_rows: int

    @property
    def missing_pct(self) -> float:
        """Missing cells as a percent of all cells."""
        return 100.0 * self.missing_cells / self.total_cells if self.total_cells else 0.0


def grade_for(score: float) -> str:
    """Map a 0-100 score to a letter grade A-F."""
    for floor, letter in GRADE_BANDS:
        if score >= floor:
            return letter
    return "F"


def _severity(penalty: float) -> str:
    if penalty >= 10:
        return "high"
    if penalty >= 4:
        return "medium"
    return "low"


def _fmt_cols(items: list[tuple[str, float]], suffix: str = "%") -> str:
    shown = ", ".join(f"{name} ({value:.1f}{suffix})" for name, value in items[:5])
    more = f" and {len(items) - 5} more" if len(items) > 5 else ""
    return shown + more


def assess_health(profile: Profile) -> HealthReport:
    """Compute the health score and issues for a profiled dataset."""
    df = profile.df
    total_cells = profile.n_rows * profile.n_cols
    missing_cells = int(sum(c.n_missing for c in profile.columns))
    duplicate_rows = int(df.duplicated().sum()) if profile.n_rows else 0

    mixed = [c for c in profile.columns if c.mixed_type]
    constant = [c for c in profile.columns if c.is_constant]
    outlier_cols = [
        c
        for c in profile.columns
        if c.col_type == ColType.NUMBER and c.stats.get("outlier_pct", 0) > OUTLIER_SHARE_THRESHOLD
    ]
    measures = {
        "missing_cells": 100.0 * missing_cells / total_cells if total_cells else 0.0,
        "duplicate_rows": 100.0 * duplicate_rows / profile.n_rows if profile.n_rows else 0.0,
        "mixed_types": float(len(mixed)),
        "constant_columns": float(len(constant)),
        "outlier_columns": float(len(outlier_cols)),
    }

    checks: list[CheckResult] = []
    for key, cfg in HEALTH_WEIGHTS.items():
        penalty = min(cfg["cap"], cfg["points_per_unit"] * measures[key])
        checks.append(
            CheckResult(key, cfg["label"], measures[key], cfg["points_per_unit"], cfg["cap"], round(penalty, 1))
        )
    score = max(0, round(100 - sum(c.penalty for c in checks)))
    penalty_of = {c.key: c.penalty for c in checks}

    issues: list[Issue] = []
    missing_cols = sorted(
        ((c.name, c.missing_pct) for c in profile.columns if c.n_missing), key=lambda t: -t[1]
    )
    if missing_cols:
        issues.append(
            Issue(
                _severity(penalty_of["missing_cells"]),
                f"{measures['missing_cells']:.1f}% of cells are missing",
                f"{len(missing_cols)} column(s) have gaps: {_fmt_cols(missing_cols)}.",
                WHY["missing_cells"],
                "missing_cells",
                [n for n, _ in missing_cols],
            )
        )
    if duplicate_rows:
        issues.append(
            Issue(
                _severity(penalty_of["duplicate_rows"]),
                f"{duplicate_rows:,} duplicate rows",
                f"{measures['duplicate_rows']:.1f}% of rows are exact copies of an earlier row.",
                WHY["duplicate_rows"],
                "duplicate_rows",
            )
        )
    for col in mixed:
        n = f"{col.n_unparsed:,} value(s)" if col.n_unparsed else "Some values"
        issues.append(
            Issue(
                _severity(HEALTH_WEIGHTS["mixed_types"]["points_per_unit"]),
                f"Mixed types in '{col.name}'",
                f"{n} could not be read as {col.col_type}; they are treated as missing.",
                WHY["mixed_types"],
                "mixed_types",
                [col.name],
            )
        )
    if constant:
        issues.append(
            Issue(
                _severity(penalty_of["constant_columns"]),
                f"{len(constant)} constant column(s)",
                "Only one distinct value: " + ", ".join(c.name for c in constant[:5]) + ".",
                WHY["constant_columns"],
                "constant_columns",
                [c.name for c in constant],
            )
        )
    if outlier_cols:
        items = [(c.name, c.stats["outlier_pct"]) for c in outlier_cols]
        issues.append(
            Issue(
                _severity(penalty_of["outlier_columns"]),
                f"High outlier share in {len(outlier_cols)} column(s)",
                f"Values outside 1.5 x IQR: {_fmt_cols(items)}.",
                WHY["outlier_columns"],
                "outlier_columns",
                [c.name for c in outlier_cols],
            )
        )
    ids = profile.names(ColType.ID)
    if ids:
        issues.append(
            Issue(
                "info",
                f"{len(ids)} identifier column(s) excluded from charts",
                ", ".join(ids[:5]) + ".",
                WHY["id_columns"],
                "id_columns",
                ids,
            )
        )
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    issues.sort(key=lambda i: order[i.severity])

    return HealthReport(
        score=score,
        grade=grade_for(score),
        checks=checks,
        issues=issues,
        missing_cells=missing_cells,
        total_cells=total_cells,
        duplicate_rows=duplicate_rows,
    )
