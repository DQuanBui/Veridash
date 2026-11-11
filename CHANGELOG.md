# Changelog

Notable changes to Veridash. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-11-11

### Added
- **Compare two files:** a new page that lines up a before and an after file, such as two monthly exports. It
  shows the change in rows, columns, data health and the main metric, a diverging chart and a table of the
  groups that moved it most, and, with a shared ID column, the records that are new, gone or changed. Each
  figure is one SQL query on the two files stacked together.
- **Fact-checked comparison summary:** plain-English sentences built from a fact pack, so every number in them
  passes the fact-check. Changes that round to zero are worded plainly.
- **Comparison download:** a CSV with every compared figure, its before, after and change, and its SQL.
- **Compare examples:** retail 2023 vs 2024 and the portfolio in November vs December 2024, one click each.
- **Check someone else's numbers:** paste any text on the Insights tab and every number in it is checked
  against the file, with a short status and the full reason for any that fail.
- **Benchmark:** the pandas cross-check also recomputes both Compare examples (258 of 258 numbers agree).

### Changed
- Home shows a Compare button, a comparison-table row for a new month's file and updated use cases.
- The Guide explains comparisons and the text checker; the README demo GIF includes both.

## [1.2.0] - 2026-11-11

### Added
- **Trust benchmark:** a deterministic benchmark that plants 1,004 wrong numbers in sentences built from the
  example datasets, sends 38 harmful and 25 harmless queries through the query guard and the sandbox, and
  recomputes 214 headline numbers with pandas. Results are published in `bench/results.json` and checked in CI.
- **Benchmark page:** the scores by error type and attack type, false alarms, safe queries that still run, and
  the story of the two blind spots the first run found. The Home page shows the headline scores.
- **Shareable web report:** one HTML file with no JavaScript that opens in any browser, offline. Verified
  numbers in the insights link to the fact and SQL behind them.
- **Demo GIF** at the top of the README.

### Changed
- **Stricter fact-check:** an explicit sign or a direction word ("rose", "fell by") must match the fact, and a
  group's number must belong to the group named next to it. Planted errors caught rose from 77.9% to 96.0%,
  with no false alarms.
- Unverified numbers now explain why they failed, for example "Wrong group: $209.1K is the figure for
  Apparel, not Electronics".
- The Guide answers how the fact-check is measured and how to share results.

### Removed
- The year next to the author credit in the footer.

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

[1.3.0]: https://github.com/DQuanBui/Veridash/compare/568aefc...main
[1.2.0]: https://github.com/DQuanBui/Veridash/compare/d7600e3...568aefc
[1.1.0]: https://github.com/DQuanBui/Veridash/compare/6e9501d...d7600e3
[1.0.0]: https://github.com/DQuanBui/Veridash/commit/6e9501d
