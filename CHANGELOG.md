# Changelog

Notable changes to Veridash. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-10

### Added
- **What drove the latest change:** for totals and counts, a chart shows how much each group added or removed
  between the last two complete periods. The bars add up to the total change, decreases are shown in red, and
  every number is fact-checked.
- **Quick questions:** up to five one-click questions on the Ask tab, answered with ready-made SQL and no
  AI key.
- **Audit trail export:** a CSV of every computed number with its fact ID, whether the insights cite it, and
  the exact SQL behind it.
- **How to fix:** each data-health issue has a practical next step with Excel and Power Query pointers. It
  appears on the Overview tab and in the Excel and PDF reports.
- **Insights in eight languages:** AI insights can be written in English, Spanish, French, German,
  Portuguese, Italian, Dutch or Vietnamese, and the fact-check keeps working.
- **Data tab downloads:** the cleaned data (or only the rows matching a search) and a data dictionary.
- **Example files:** each example can be previewed and downloaded so its layout can be reused.
- **Accessibility:** visible keyboard focus, support for reduced motion, a text alternative for the health
  score, and screen-reader text for unverified numbers.
- **Project tooling:** GitHub Actions CI (Ruff and pytest), Dependabot and optional pre-commit hooks.

### Changed
- The Export tab shows four cards in a two-by-two grid.
- The Home use cases mention the change breakdown, the fix tips and the audit trail.

## [1.0.0] - 2026-11-09

### Added
- Upload a CSV or Excel file, or pick an example: retail sales, HR workforce or investment portfolio.
- A data health score with weighted, capped checks and plain-English issues.
- Recommended charts and KPIs, each showing the DuckDB SQL that produced it.
- Rule-based insights, plus optional Gemini insights with a number-by-number fact-check.
- Ask your data: plain-English questions turned into validated, sandboxed SQL, plus a SQL box.
- Exports: an Excel report with native charts, a PDF summary and a Power BI Starter Kit.
- Light and dark themes, a Home page with use cases and a comparison, a Guide and an Examples page.

[1.1.0]: https://github.com/DQuanBui/Veridash/compare/6e9501d...main
[1.0.0]: https://github.com/DQuanBui/Veridash/commit/6e9501d
