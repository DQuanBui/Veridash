"""Fact-check benchmark: plant wrong numbers, count how many are caught.

For every headline fact in the example datasets, the benchmark writes one
sentence with the correct number, a few correct variants (rounded, spelled
out, with a direction word) and several corrupted versions (a near miss, a 10%
error, the wrong unit, swapped digits, another group's number, a flipped sign).

* A corrupted sentence is *caught* when the fact-checker marks its number as
  unverified.
* A correct sentence is a *false alarm* when the fact-checker flags it.

Everything is deterministic: no randomness and no AI calls.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from ai.factcheck import check_text
from core.facts import Fact, FactPack
from core.formatting import fmt_value

_DISPLAY = re.compile(r"^(?P<sign>[-+])?(?P<cur>\$)?(?P<num>[\d,]+(?:\.\d+)?)(?P<suf>[KMB])?(?P<pct>%)?$")
_INDEXED = re.compile(r"^(?P<family>[a-z_]+)\.(?P<index>\d+)\.(?P<field>[a-z_]+)$")
_SCALE = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}


@dataclass(frozen=True)
class CaseType:
    """One kind of benchmark sentence."""

    key: str
    title: str
    example: str
    corrupt: bool


CORRECT_TYPES = [
    CaseType("exact", "Exact number", "Revenue is $785.3K.", False),
    CaseType("rounded", "Rounded further", "$785.3K written as $785K", False),
    CaseType("spelled", "Scale in words", "$785.3K written as $785.3 thousand", False),
    CaseType("direction", "Direction word", "-1.1% written as fell by 1.1%", False),
    CaseType("signed", "Explicit sign", "+67.1% for a 67.1% rise", False),
    CaseType("rule_text", "Veridash's own insights", "Every sentence the rule-based insights write", False),
]
CORRUPT_TYPES = [
    CaseType("near_miss", "Near miss", "$785.3K changed to $785.6K", True),
    CaseType("off_10pct", "10% too high", "$785.3K changed to $863.8K", True),
    CaseType("wrong_unit", "Wrong unit", "$785.3K changed to $785.3M", True),
    CaseType("digit_swap", "Swapped digits", "$785.3K changed to $758.3K", True),
    CaseType("wrong_group", "Another group's number", "Electronics given Apparel's $209.1K", True),
    CaseType("sign_flip", "Flipped direction", "+67.1% changed to -67.1%", True),
]
TYPES = {t.key: t for t in CORRECT_TYPES + CORRUPT_TYPES}


@dataclass
class Case:
    """One sentence to check."""

    dataset: str
    type: str
    text: str
    fact_id: str = ""

    @property
    def corrupt(self) -> bool:
        """True if the sentence contains a planted error."""
        return TYPES[self.type].corrupt


@dataclass
class TypeScore:
    """Results for one case type."""

    type: CaseType
    cases: int = 0
    flagged: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def rate(self) -> float:
        """Share of cases flagged, in percent."""
        return 100.0 * self.flagged / self.cases if self.cases else 0.0


def _parse(display: str) -> dict[str, str] | None:
    m = _DISPLAY.match(display)
    return m.groupdict(default="") if m else None


def _headline(fact: Fact) -> bool:
    """Facts a writer would quote: KPIs, chart results, row counts, the score."""
    if not fact.is_numeric or fact.kind == "date":
        return False
    return fact.source not in ("profile", "health") or fact.id == "health.score"


def _is_change(fact: Fact) -> bool:
    return "change" in fact.id and float(fact.value) != 0


def _siblings(pack: FactPack) -> dict[tuple[str, str], str]:
    """(family, index) -> group label, for facts such as ``top.2.value``."""
    out = {}
    for f in pack.facts:
        m = _INDEXED.match(f.id)
        if m and m["field"] == "label":
            out[(m["family"], m["index"])] = str(f.value)
    return out


def _sentence(fact: Fact, number: str, labels: dict[tuple[str, str], str], group: str | None = None) -> str:
    m = _INDEXED.match(fact.id)
    if m and (m["family"], m["index"]) in labels:
        return f"{group or labels[(m['family'], m['index'])]} comes to {number}."
    subject = fact.label if not re.search(r"\d", fact.label) else "The figure"
    return f"{subject} is {number}."


def _with_number(parts: dict[str, str], num: str) -> str:
    return f"{parts['sign']}{parts['cur']}{num}{parts['suf']}{parts['pct']}"


def _near_miss(parts: dict[str, str]) -> str | None:
    num = parts["num"]
    idx = max(i for i, ch in enumerate(num) if ch.isdigit())
    new = num[:idx] + str((int(num[idx]) + 3) % 10) + num[idx + 1 :]
    return _with_number(parts, new)


def _digit_swap(parts: dict[str, str]) -> str | None:
    digits = [i for i, ch in enumerate(parts["num"]) if ch.isdigit()]
    num = list(parts["num"])
    for a, b in itertools.pairwise(digits):
        if num[a] != num[b]:
            num[a], num[b] = num[b], num[a]
            return _with_number(parts, "".join(num))
    return None


def _wrong_unit(fact: Fact, parts: dict[str, str]) -> str | None:
    if parts["pct"]:
        return None
    swap = {"K": "M", "M": "B", "B": "K"}
    if parts["suf"]:
        return _with_number({**parts, "suf": swap[parts["suf"]]}, parts["num"])
    if abs(float(fact.value)) >= 1:
        return fmt_value(float(fact.value) * 1000, fact.kind)
    return None


def _rounded(fact: Fact, parts: dict[str, str]) -> str | None:
    if "." not in parts["num"]:
        return None
    decimals = len(parts["num"].split(".")[1]) - 1
    body = abs(float(fact.value)) / _SCALE[parts["suf"]]
    return _with_number(parts, f"{body:,.{decimals}f}")


def _spelled(fact: Fact) -> str | None:
    v = abs(float(fact.value))
    if fact.kind not in ("currency", "number") or v < 1000:
        return None
    sign = "-" if float(fact.value) < 0 else ""
    cur = "$" if fact.kind == "currency" else ""
    if v >= 1e6:
        return f"{sign}{cur}{v / 1e6:,.2f} million"
    return f"{sign}{cur}{v / 1e3:,.1f} thousand"


def _signed(fact: Fact, flip: bool = False) -> str:
    v = float(fact.value)
    sign = "+" if (v > 0) != flip else "-"
    return sign + fmt_value(abs(v), fact.kind)


def build_cases(key: str, pack: FactPack, rule_texts: list[str]) -> list[Case]:
    """All benchmark sentences for one dataset."""
    labels = _siblings(pack)
    by_id = pack.by_id()
    cases = [Case(key, "rule_text", t) for t in rule_texts if re.search(r"\d", t)]
    for fact in filter(_headline, pack.facts):
        parts = _parse(fact.display)
        if parts is None:
            continue

        def add(kind: str, number: str | None, group: str | None = None, fact: Fact = fact) -> None:
            if number:
                cases.append(Case(key, kind, _sentence(fact, number, labels, group), fact.id))

        add("exact", fact.display)
        add("rounded", _rounded(fact, parts))
        add("spelled", _spelled(fact))
        if _is_change(fact):
            word = "rose" if float(fact.value) > 0 else "fell"
            add("direction", f"{word} by {fmt_value(abs(float(fact.value)), fact.kind)}")
            add("signed", _signed(fact))
            add("sign_flip", _signed(fact, flip=True))
        add("near_miss", _near_miss(parts))
        if float(fact.value) != 0:
            add("off_10pct", fmt_value(float(fact.value) * 1.1, fact.kind))
        add("wrong_unit", _wrong_unit(fact, parts))
        add("digit_swap", _digit_swap(parts))
        m = _INDEXED.match(fact.id)
        if m and (m["family"], m["index"]) in labels:
            for other in (int(m["index"]) + 1, int(m["index"]) - 1):
                sib = by_id.get(f"{m['family']}.{other}.{m['field']}")
                if sib is not None and sib.display != fact.display:
                    add("wrong_group", sib.display, labels[(m["family"], m["index"])])
                    break
    return cases


def flagged(case: Case, pack: FactPack) -> bool:
    """True if the fact-checker marks any number in the sentence as unverified."""
    return any(not c.verified for c in check_text(case.text, pack))


def score(cases: list[tuple[Case, FactPack]]) -> dict[str, TypeScore]:
    """Score every case and group the results by type."""
    out = {key: TypeScore(t) for key, t in TYPES.items()}
    for case, pack in cases:
        s = out[case.type]
        s.cases += 1
        hit = flagged(case, pack)
        s.flagged += hit
        if hit != case.corrupt and len(s.misses) < 5:
            s.misses.append(f"[{case.dataset}] {case.text}")
    return out


def iter_example_cases() -> Iterator[tuple[Case, FactPack]]:
    """Benchmark cases for the three bundled example datasets."""
    from core.pipeline import analyze, prepare
    from core.samples import EXAMPLES

    for ex in EXAMPLES.values():
        analysis = analyze(prepare(ex.read_bytes(), ex.filename))
        for case in build_cases(ex.key, analysis.facts, analysis.rule_insights.texts()):
            yield case, analysis.facts


def run() -> dict:
    """Run the suite and return JSON-friendly results."""
    scores = score(list(iter_example_cases()))
    correct = [scores[t.key] for t in CORRECT_TYPES]
    corrupt = [scores[t.key] for t in CORRUPT_TYPES]
    n_correct, n_corrupt = sum(s.cases for s in correct), sum(s.cases for s in corrupt)
    false_alarms = sum(s.flagged for s in correct)
    caught = sum(s.flagged for s in corrupt)

    def row(s: TypeScore) -> dict:
        return {
            "key": s.type.key, "title": s.type.title, "example": s.type.example,
            "cases": s.cases, "flagged": s.flagged, "rate_pct": round(s.rate, 1), "misses": s.misses,
        }

    return {
        "correct_sentences": n_correct,
        "false_alarms": false_alarms,
        "false_alarm_pct": round(100.0 * false_alarms / n_correct, 2) if n_correct else 0.0,
        "planted_errors": n_corrupt,
        "caught": caught,
        "catch_pct": round(100.0 * caught / n_corrupt, 1) if n_corrupt else 0.0,
        "correct": [row(s) for s in correct],
        "corrupt": [row(s) for s in corrupt],
    }
