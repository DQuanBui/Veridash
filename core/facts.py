"""Facts: numbers computed by code, each with a stable ID.

A :class:`Fact` is the unit of trust in Veridash. Charts, KPIs, the health
check and the profile all emit facts; the fact pack bundles them for the AI,
and the fact-checker verifies AI text against them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from core.formatting import fmt_value


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
