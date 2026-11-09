"""Fact-check numbers in generated text against the fact pack.

Every number in AI (or rule-based) prose is extracted and compared with the
numeric facts the code computed. A number is *verified* when some fact rounds
to it at the precision it was written with, for example:

* ``$785.3K`` matches 785,312.4 (step 0.1K, so tolerance +/- 50)
* ``35%`` matches 34.6 (step 1, tolerance +/- 0.5), but ``35.0%`` does not
* ``-1.1%`` matches -1.08 (sign is ignored, so "fell 1.1%" also matches)

Percent claims only match percent facts. Years and ISO dates are verified when
they fall inside the dataset's date range. Labels that contain digits (such as
``Q1 2023`` or ``Store 01``) are recognised from text facts and skipped.
Anything that cannot be matched is reported as unverified, never hidden.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from core.facts import Fact, FactPack

_FACT_ID = re.compile(r"\b[a-z_]+(?:\.[a-z0-9_~]+)+\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})(?:-(\d{2}))?\b")
_NUMBER = re.compile(
    r"(?P<cur>[$€£])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suffix>(?-i:[KMB])\b|\s?(?:thousand|million|billion)\b)?"
    r"(?P<pct>\s?%|\s?percent\b|\s?percentage points\b)?",
    re.IGNORECASE,
)
# When several facts match equally well, prefer headline facts over penalties.
_SOURCE_RANK = {"kpi": 0, "dataset": 0, "health": 2, "profile": 2}
_SCALES = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


@dataclass
class NumberClaim:
    """One number found in text and the outcome of checking it."""

    raw: str
    start: int
    end: int
    value: float
    decimals: int
    scale: float = 1.0
    is_percent: bool = False
    kind: str = "number"  # number | year | date
    verified: bool = False
    fact_id: str | None = None


@dataclass
class FactCheckReport:
    """Results for every text that was checked."""

    by_text: dict[str, list[NumberClaim]] = field(default_factory=dict)

    @property
    def claims(self) -> list[NumberClaim]:
        """All claims across texts."""
        return [c for claims in self.by_text.values() for c in claims]

    @property
    def total(self) -> int:
        """How many numbers were found."""
        return len(self.claims)

    @property
    def verified(self) -> int:
        """How many numbers matched a fact."""
        return sum(c.verified for c in self.claims)

    @property
    def unverified(self) -> list[NumberClaim]:
        """Numbers that could not be matched."""
        return [c for c in self.claims if not c.verified]


def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def _label_spans(text: str, pack: FactPack) -> list[tuple[int, int]]:
    """Spans of text facts (labels, periods) that contain digits."""
    spans = []
    labels = {str(f.value) for f in pack.facts if not f.is_numeric and re.search(r"\d", str(f.value))}
    for label in sorted(labels, key=len, reverse=True):
        for m in re.finditer(re.escape(label), text):
            spans.append((m.start(), m.end()))
    return spans


def _date_bounds(pack: FactPack) -> tuple[str, str] | None:
    facts = pack.by_id()
    if "dataset.date_start" in facts and "dataset.date_end" in facts:
        return str(facts["dataset.date_start"].value), str(facts["dataset.date_end"].value)
    return None


def extract_numbers(text: str, pack: FactPack | None = None) -> list[NumberClaim]:
    """Find numeric claims in ``text`` (dates and digit-bearing labels excluded)."""
    spans = [(m.start(), m.end()) for m in _FACT_ID.finditer(text)]
    if pack is not None:
        spans += _label_spans(text, pack)
    masked = _mask(text, spans)
    claims: list[NumberClaim] = []
    for m in _ISO_DATE.finditer(masked):
        claims.append(NumberClaim(m.group(0), m.start(), m.end(), 0.0, 0, kind="date"))
    masked = _mask(masked, [(c.start, c.end) for c in claims])

    for m in _NUMBER.finditer(masked):
        start, end = m.start(), m.end()
        before = masked[start - 1] if start else " "
        after = masked[end] if end < len(masked) else " "
        if before.isalpha() or before in "_." or (after.isalpha() and not m.group("suffix")):
            continue  # part of a word or code such as B6, 12pk, v2
        num = m.group("num")
        value = float(num.replace(",", ""))
        decimals = len(num.split(".")[1]) if "." in num else 0
        suffix = (m.group("suffix") or "").strip().lower()
        scale = _SCALES.get(suffix, 1.0)
        is_pct = bool(m.group("pct"))
        kind = "number"
        if (
            not m.group("cur") and not suffix and not is_pct and decimals == 0
            and "," not in num and 1900 <= value <= 2100
        ):
            kind = "year"
        negative = before in "-−" or (start >= 2 and masked[start - 2 : start] in ("- ", "−"))
        claims.append(
            NumberClaim(
                raw=text[start:end].strip(),
                start=start,
                end=end,
                value=-value if negative else value,
                decimals=decimals,
                scale=scale,
                is_percent=is_pct,
                kind=kind,
            )
        )
    return sorted(claims, key=lambda c: c.start)


def _matches(claim: NumberClaim, fact: Fact) -> bool:
    if claim.is_percent != (fact.kind == "percent"):
        return False
    target = abs(float(fact.value))
    value = abs(claim.value) * claim.scale
    step = (10 ** -claim.decimals) * claim.scale
    return abs(value - target) <= step / 2 + 1e-9 * max(1.0, target)


def verify(claims: list[NumberClaim], pack: FactPack) -> list[NumberClaim]:
    """Mark each claim verified or not, recording the matching fact ID."""
    numeric = pack.numeric()
    bounds = _date_bounds(pack)
    for claim in claims:
        if claim.kind == "date":
            if bounds:
                padded = claim.raw if len(claim.raw) == 10 else f"{claim.raw}-01"
                claim.verified = bounds[0][:7] <= padded[:7] <= bounds[1][:7]
                claim.fact_id = "dataset.date_start/date_end" if claim.verified else None
            continue
        candidates = [f for f in numeric if _matches(claim, f)]
        match = min(
            candidates,
            key=lambda f: (abs(abs(claim.value) * claim.scale - abs(float(f.value))), _SOURCE_RANK.get(f.source, 1)),
            default=None,
        )
        if match:
            claim.verified, claim.fact_id = True, match.id
        elif claim.kind == "year" and bounds:
            claim.verified = int(bounds[0][:4]) <= claim.value <= int(bounds[1][:4])
            claim.fact_id = "dataset.date_start/date_end" if claim.verified else None
    return claims


def check_text(text: str, pack: FactPack) -> list[NumberClaim]:
    """Extract and verify the numbers in one piece of text."""
    return verify(extract_numbers(text, pack), pack)


def fact_check(texts: list[str], pack: FactPack) -> FactCheckReport:
    """Check many texts and return a :class:`FactCheckReport`."""
    return FactCheckReport(by_text={t: check_text(t, pack) for t in texts})


def highlight_html(text: str, claims: list[NumberClaim]) -> str:
    """Escape ``text`` and wrap each number in a verified/unverified span."""
    out, pos = [], 0
    for c in claims:
        out.append(html.escape(text[pos : c.start]))
        cls = "vd-num-ok" if c.verified else "vd-num-bad"
        title = f"Verified: {c.fact_id}" if c.verified else "Not found in the fact pack"
        out.append(f'<span class="{cls}" title="{html.escape(title)}">{html.escape(text[c.start : c.end])}</span>')
        pos = c.end
    out.append(html.escape(text[pos:]))
    return "".join(out)
