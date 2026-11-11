"""Human-friendly number and period formatting.

The fact-checker (``ai.factcheck``) parses every format produced here, so text
written with these helpers can always be verified against the fact pack.
"""

from __future__ import annotations

import math

import pandas as pd

CURRENCY_HINTS = (
    "revenue", "sales", "price", "cost", "amount", "profit", "value", "salary", "income",
    "spend", "budget", "gain", "loss", "fee", "payment", "margin_usd", "basis", "pay",
)


def _trim(text: str) -> str:
    return text[:-3] if text.endswith(".00") else text


def compact(value: float) -> str:
    """Format a number compactly: 12.34, 1,234, 12.3K, 1.23M, 4.56B."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    v = abs(float(value))
    sign = "-" if value < 0 else ""
    if v < 1_000:
        body = _trim(f"{v:,.2f}")
    elif v < 100_000:
        body = f"{v:,.0f}"
    elif v < 1_000_000:
        body = f"{v / 1_000:,.1f}K"
    elif v < 1_000_000_000:
        body = f"{v / 1_000_000:,.2f}M"
    else:
        body = f"{v / 1_000_000_000:,.2f}B"
    return sign + body


def fmt_value(value: float | None, kind: str = "number") -> str:
    """Format ``value`` according to ``kind``.

    Kinds: ``currency`` ($), ``percent`` (value already in percent points),
    ``int`` (thousands separators), ``ratio`` (two decimals) and ``number``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if kind == "currency":
        text = compact(value)
        return f"-${text[1:]}" if text.startswith("-") else f"${text}"
    if kind == "percent":
        return f"{value:,.1f}%"
    if kind == "int":
        return f"{round(value):,}"
    if kind == "ratio":
        return f"{value:.2f}"
    return compact(value)


def fmt_signed_pct(value: float | None) -> str:
    """Format a percent change with an explicit sign, e.g. ``+12.3%``."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:+,.1f}%"


def fmt_period(ts: object, grain: str) -> str:
    """Format a period start timestamp for display at the given grain."""
    t = pd.Timestamp(ts)
    if grain == "quarter":
        return f"Q{t.quarter} {t.year}"
    if grain == "month":
        return t.strftime("%b %Y")
    if grain == "week":
        return f"week of {t.strftime('%Y-%m-%d')}"
    return t.strftime("%Y-%m-%d")


def metric_kind(name: str, unit: str | None = None) -> str:
    """Infer the display kind of a numeric column from its unit or name."""
    if unit == "percent":
        return "percent"
    if unit == "currency":
        return "currency"
    lowered = name.lower()
    if any(h in lowered for h in CURRENCY_HINTS):
        return "currency"
    return "number"


def plural(n: int, word: str, many: str | None = None) -> str:
    """``1 issue``, ``4 issues``: a count with the right form of the word."""
    return f"{n:,} {word if n == 1 else (many or word + 's')}"


def pretty(name: str) -> str:
    """Turn a column name into a readable label: ``unit_price`` -> ``Unit price``."""
    text = str(name).replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else text


def human_bytes(n: int) -> str:
    """Format a byte count, e.g. ``1.4 MB``."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.0f} {unit}" if unit == "B" else f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover
