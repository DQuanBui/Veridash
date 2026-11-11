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

    @property
    def file_kind(self) -> str:
        """``CSV`` or ``Excel``, for labels."""
        return "Excel" if self.filename.endswith((".xlsx", ".xls")) else "CSV"

    def read_bytes(self) -> bytes:
        """Return the raw file bytes (loaded like any upload)."""
        return (SAMPLES_DIR / self.filename).read_bytes()


EXAMPLES: dict[str, Example] = {
    "retail": Example(
        key="retail",
        title="Retail sales",
        filename="retail_sales.csv",
        summary="Two years of transactions from fictional stores across regions and product "
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
        summary="Monthly holdings across fictional tickers and sectors, with shares, price, "
        "market value, cost basis and gain or loss.",
        rows_hint="~2,000 rows · CSV",
    ),
}


@dataclass(frozen=True)
class CompareExample:
    """Two slices of one bundled example, compared on the Compare page."""

    key: str
    title: str
    source: str  # key in EXAMPLES
    date_col: str
    before: str  # period prefix such as "2023" or "2024-11"
    after: str
    before_name: str
    after_name: str


COMPARE_EXAMPLES: dict[str, CompareExample] = {
    "retail_years": CompareExample(
        "retail_years", "Retail: 2023 vs 2024", "retail", "date", "2023", "2024",
        "retail_sales_2023.csv", "retail_sales_2024.csv",
    ),
    "portfolio_months": CompareExample(
        "portfolio_months", "Portfolio: Nov vs Dec 2024", "portfolio", "date", "2024-11", "2024-12",
        "portfolio_2024_11.csv", "portfolio_2024_12.csv",
    ),
}


def compare_example_files(key: str) -> tuple[tuple[str, bytes], tuple[str, bytes]]:
    """The before and after files for a compare example, as CSV bytes.

    Both slices come from the same bundled example, cleaned the same way an
    upload would be, and are split on the date column.
    """
    from core.pipeline import prepare  # local import: pipeline imports this module's neighbours

    ex = COMPARE_EXAMPLES[key]
    source = EXAMPLES[ex.source]
    df = prepare(source.read_bytes(), source.filename).profile.df
    stamp = df[ex.date_col].dt.strftime("%Y-%m-%d")
    out = []
    for prefix, name in ((ex.before, ex.before_name), (ex.after, ex.after_name)):
        part = df[stamp.str.startswith(prefix)]
        out.append((name, part.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")))
    return out[0], out[1]
