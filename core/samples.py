"""Registry of the bundled example datasets."""

from __future__ import annotations

from dataclasses import dataclass

from core.settings import SAMPLES_DIR


@dataclass(frozen=True)
class Example:
    """Metadata for one bundled example dataset."""

    key: str
    title: str
    filename: str
    summary: str
    rows_hint: str

    def read_bytes(self) -> bytes:
        """Return the raw file bytes (loaded like any upload)."""
        return (SAMPLES_DIR / self.filename).read_bytes()


EXAMPLES: dict[str, Example] = {
    "retail": Example(
        key="retail",
        title="Retail sales",
        filename="retail_sales.csv",
        summary="Two years of transactions across 10 fictional stores, 5 regions and 5 product "
        "categories, with units, prices, discounts, revenue and cost.",
        rows_hint="~5,000 rows · CSV",
    ),
    "hr": Example(
        key="hr",
        title="HR workforce",
        filename="hr_workforce.xlsx",
        summary="A workforce snapshot for a fictional company: departments, roles, tenure, "
        "salary bands, performance, satisfaction, overtime and attrition.",
        rows_hint="~1,500 rows · Excel, 2 sheets",
    ),
    "portfolio": Example(
        key="portfolio",
        title="Investment portfolio",
        filename="investment_portfolio.csv",
        summary="Monthly holding lots across 12 fictional tickers and 7 sectors, with shares, "
        "price, market value, cost basis and gain or loss.",
        rows_hint="~2,000 rows · CSV",
    ),
}
