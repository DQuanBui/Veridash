"""Column type detection and per-column statistics.

The profiler turns a raw DataFrame into:

* a *typed* DataFrame (currency/percent strings parsed to numbers, dates to
  datetimes, yes/no to booleans) that every later step queries, and
* a :class:`Profile` with one :class:`ColumnProfile` per column.

Detected types: number, date, category, boolean, text and id.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd


class ColType(StrEnum):
    """Semantic column types used throughout Veridash."""

    NUMBER = "number"
    DATE = "date"
    CATEGORY = "category"
    BOOLEAN = "boolean"
    TEXT = "text"
    ID = "id"


# A value must parse for at least this share of non-empty cells to adopt a type.
TYPE_THRESHOLD = 0.9
# Share at or above which a column that is not fully parseable counts as "mixed".
MIXED_FLOOR = 0.5
ID_UNIQUE_SHARE = 0.95
TEXT_AVG_LENGTH = 40
TOP_VALUES = 10

_TRUE = {"true", "yes", "y", "t", "1"}
_FALSE = {"false", "no", "n", "f", "0"}
_ID_NAME = re.compile(r"(?i)(^id$|[_\s\-.]id$|^id[_\s\-.]|_key$|^uuid$|_uuid$)|[a-z]ID$")
_CURRENCY = re.compile(r"^[(\-+\s]*[$€£¥]|[$€£¥]\s*\)?$")
_NUM_STRIP = re.compile(r"[$€£¥,%\s()]")


@dataclass
class ColumnProfile:
    """Profile of one column. ``stats`` keys depend on the column type."""

    name: str
    col_type: ColType
    raw_dtype: str
    n_missing: int
    missing_pct: float
    n_unique: int
    unique_pct: float
    is_constant: bool = False
    mixed_type: bool = False
    n_unparsed: int = 0
    unit: str | None = None
    stats: dict[str, float] = field(default_factory=dict)
    top_values: list[tuple[str, int]] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form (JSON-serialisable)."""
        out = asdict(self)
        out["col_type"] = str(self.col_type)
        return out


@dataclass
class Profile:
    """Profile of a whole dataset."""

    df: pd.DataFrame
    columns: list[ColumnProfile]
    n_rows: int
    n_cols: int
    memory_bytes: int

    def get(self, name: str) -> ColumnProfile:
        """Return the profile of column ``name``."""
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(name)

    def names(self, *types: ColType) -> list[str]:
        """Names of columns with any of the given types (all if none given)."""
        return [c.name for c in self.columns if not types or c.col_type in types]


def parse_numeric(series: pd.Series) -> tuple[pd.Series, float, str | None]:
    """Parse numbers stored as text, including currency, percent and accounting formats.

    Examples that parse: ``"$1,234.50"``, ``"(123)"`` (negative), ``"12.5%"``, ``" 7 "``.

    Returns:
        ``(values, parse_ratio, unit)`` where ``values`` is float with NaN for
        unparseable cells, ``parse_ratio`` is the parseable share of non-empty
        cells and ``unit`` is ``"currency"``, ``"percent"`` or ``None``.
    """
    text = series.astype("string").str.strip()
    present = text.notna() & (text != "")
    if not present.any():
        return pd.Series(np.nan, index=series.index, dtype="float64"), 0.0, None
    negative = text.str.match(r"^\(.*\)$").fillna(False).astype(bool)
    cleaned = text.str.replace(_NUM_STRIP, "", regex=True)
    values = pd.to_numeric(cleaned, errors="coerce").astype("float64")
    values = values.where(~negative, -values)
    ratio = float(values[present].notna().mean())
    pct_share = float(text[present].str.endswith("%").mean())
    cur_share = float(text[present].str.contains(_CURRENCY).mean())
    unit = "percent" if pct_share > 0.5 else "currency" if cur_share > 0.5 else None
    return values, ratio, unit


def parse_dates(series: pd.Series) -> tuple[pd.Series | None, float]:
    """Parse date-like strings. Returns ``(datetimes, parse_ratio)`` or ``(None, 0)``."""
    text = series.astype("string").str.strip()
    present = text.dropna()
    present = present[present != ""]
    if present.empty:
        return None, 0.0
    sample = present.head(500)
    # Dates need a digit and some length; pure numbers are not dates.
    plausible = sample.str.contains(r"\d") & (sample.str.len() >= 6)
    if plausible.mean() < TYPE_THRESHOLD or sample.str.fullmatch(r"[-+]?\d+(\.\d+)?").mean() > 0.5:
        return None, 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if pd.to_datetime(sample, errors="coerce", format="mixed").notna().mean() < MIXED_FLOOR:
            return None, 0.0
        parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    ratio = float(parsed[text.notna() & (text != "")].notna().mean())
    return parsed, ratio


def _as_boolean(series: pd.Series) -> pd.Series | None:
    """Return a nullable boolean Series if the column holds exactly two yes/no values."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype("boolean")
    values = series.dropna()
    if values.empty:
        return None
    lowered = values.astype(str).str.strip().str.lower()
    # Numeric 1.0 / 0.0 read from CSV should map too.
    lowered = lowered.replace({"1.0": "1", "0.0": "0"})
    uniq = set(lowered.unique())
    if len(uniq) != 2 or not uniq <= (_TRUE | _FALSE) or not (uniq & _TRUE and uniq & _FALSE):
        return None
    mapped = series.astype(str).str.strip().str.lower().replace({"1.0": "1", "0.0": "0"})
    out = mapped.map(lambda v: True if v in _TRUE else (False if v in _FALSE else pd.NA))
    return out.astype("boolean")


def _is_id_name(name: str) -> bool:
    return bool(_ID_NAME.search(name.strip()))


def _numeric_stats(values: pd.Series) -> dict[str, float]:
    v = values.dropna().astype("float64")
    if v.empty:
        return {}
    q1, median, q3 = (float(x) for x in np.percentile(v, [25, 50, 75]))
    iqr = q3 - q1
    if iqr > 0:
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = int(((v < lo) | (v > hi)).sum())
    else:
        lo = hi = median
        outliers = 0
    return {
        "count": float(len(v)),
        "sum": float(v.sum()),
        "mean": float(v.mean()),
        "median": median,
        "std": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        "min": float(v.min()),
        "max": float(v.max()),
        "p25": q1,
        "p75": q3,
        "iqr_low": lo,
        "iqr_high": hi,
        "outliers": float(outliers),
        "outlier_pct": 100.0 * outliers / len(v),
        "zeros": float((v == 0).sum()),
        "negatives": float((v < 0).sum()),
    }


def _date_stats(values: pd.Series) -> dict[str, float]:
    v = values.dropna()
    if v.empty:
        return {}
    return {
        "min": float(v.min().timestamp()),
        "max": float(v.max().timestamp()),
        "span_days": float((v.max() - v.min()).days),
        "has_time": float(bool((v.dt.normalize() != v).any())),
    }


def _top_values(series: pd.Series) -> list[tuple[str, int]]:
    counts = series.dropna().astype(str).value_counts().head(TOP_VALUES)
    return [(str(k), int(n)) for k, n in counts.items()]


def detect_column(name: str, series: pd.Series) -> tuple[ColType, pd.Series, dict[str, Any]]:
    """Detect the type of one column and return ``(type, typed_series, extras)``.

    ``extras`` may contain ``mixed_type``, ``n_unparsed`` and ``unit``.
    """
    extras: dict[str, Any] = {}
    non_null = series.dropna()
    n_present = len(non_null)

    boolean = _as_boolean(series)
    if boolean is not None:
        return ColType.BOOLEAN, boolean, extras

    if pd.api.types.is_datetime64_any_dtype(series):
        typed = series
        if getattr(series.dt, "tz", None) is not None:
            typed = series.dt.tz_convert(None)
        return ColType.DATE, typed, extras

    if pd.api.types.is_numeric_dtype(series):
        typed = series
        unique_share = non_null.nunique() / n_present if n_present else 0
        is_integral = n_present and bool((non_null.astype("float64") % 1 == 0).all())
        if _is_id_name(name) and is_integral and unique_share >= ID_UNIQUE_SHARE:
            return ColType.ID, typed, extras
        return ColType.NUMBER, typed, extras

    # Text-like column: try numbers, then dates, then id/category/text.
    values, num_ratio, unit = parse_numeric(series)
    if num_ratio >= TYPE_THRESHOLD:
        extras["unit"] = unit
        if num_ratio < 1.0:
            extras["mixed_type"] = True
            extras["n_unparsed"] = int(values.isna().sum() - series.isna().sum())
        return ColType.NUMBER, values, extras
    if num_ratio >= MIXED_FLOOR:
        extras["mixed_type"] = True

    dates, date_ratio = parse_dates(series)
    if dates is not None and date_ratio >= TYPE_THRESHOLD:
        if date_ratio < 1.0:
            extras["mixed_type"] = True
            extras["n_unparsed"] = int(dates.isna().sum() - series.isna().sum())
        return ColType.DATE, dates, extras
    if dates is not None and date_ratio >= MIXED_FLOOR:
        extras["mixed_type"] = True

    text = series.astype("string").str.strip()
    text = text.mask(text == "")
    n_unique = text.nunique()
    unique_share = n_unique / n_present if n_present else 0
    if unique_share >= ID_UNIQUE_SHARE and n_present >= 20:
        no_spaces = not text.dropna().str.contains(r"\s").any()
        if _is_id_name(name) or (unique_share == 1.0 and no_spaces and text.dropna().str.contains(r"\d").all()):
            return ColType.ID, text, extras
    avg_len = float(text.dropna().str.len().mean()) if n_present else 0.0
    if avg_len > TEXT_AVG_LENGTH or (n_unique > 100 and unique_share > 0.5):
        return ColType.TEXT, text, extras
    return ColType.CATEGORY, text, extras


def profile_dataframe(df: pd.DataFrame) -> Profile:
    """Detect column types, build the typed DataFrame and compute statistics."""
    n_rows = len(df)
    typed: dict[str, pd.Series] = {}
    columns: list[ColumnProfile] = []
    for name in df.columns:
        raw = df[name]
        col_type, series, extras = detect_column(str(name), raw)
        typed[name] = series
        n_missing = int(series.isna().sum())
        n_unique = int(series.nunique(dropna=True))
        prof = ColumnProfile(
            name=str(name),
            col_type=col_type,
            raw_dtype=str(raw.dtype),
            n_missing=n_missing,
            missing_pct=100.0 * n_missing / n_rows if n_rows else 0.0,
            n_unique=n_unique,
            unique_pct=100.0 * n_unique / max(n_rows - n_missing, 1),
            is_constant=n_rows > 1 and n_unique <= 1,
            mixed_type=bool(extras.get("mixed_type", False)),
            n_unparsed=int(extras.get("n_unparsed", 0)),
            unit=extras.get("unit"),
            examples=[str(v) for v in raw.dropna().astype(str).unique()[:3]],
        )
        if col_type == ColType.NUMBER:
            prof.stats = _numeric_stats(series)
        elif col_type == ColType.DATE:
            prof.stats = _date_stats(series)
        if col_type in (ColType.CATEGORY, ColType.BOOLEAN, ColType.TEXT):
            prof.top_values = _top_values(series)
        columns.append(prof)

    typed_df = pd.DataFrame(typed, index=df.index)
    return Profile(
        df=typed_df,
        columns=columns,
        n_rows=n_rows,
        n_cols=len(df.columns),
        memory_bytes=int(df.memory_usage(deep=True).sum()),
    )
