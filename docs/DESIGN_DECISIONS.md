# Design Decisions

The decisions that shape Veridash, with the reasoning, the alternatives considered and the trade-offs accepted.
Each section ends with where the decision lives in the code.

1. [The AI never does math](#1-the-ai-never-does-math)
2. [SQL transparency: the SQL shown is the SQL that ran](#2-sql-transparency-the-sql-shown-is-the-sql-that-ran)
3. [Fact-checking AI output](#3-fact-checking-ai-output)
4. [Schema-only prompts](#4-schema-only-prompts)
5. [DuckDB as the engine](#5-duckdb-as-the-engine)
6. [Streamlit for the interface](#6-streamlit-for-the-interface)
7. [Health score design](#7-health-score-design)
8. [A Power BI kit instead of a .pbix](#8-a-power-bi-kit-instead-of-a-pbix)
9. [Defence in depth for user SQL](#9-defence-in-depth-for-user-sql)
10. [Explaining change only where the parts add up](#10-explaining-change-only-where-the-parts-add-up)
11. [Other languages without weakening the fact-check](#11-other-languages-without-weakening-the-fact-check)
12. [Measuring the safeguards with a published benchmark](#12-measuring-the-safeguards-with-a-published-benchmark)
13. [Checking which group a number belongs to](#13-checking-which-group-a-number-belongs-to)
14. [A web report with no JavaScript](#14-a-web-report-with-no-javascript)

---

## 1. The AI never does math

**Context.** Large language models produce fluent text, but they are unreliable at arithmetic and will
confidently state numbers that were never in the data. In analytics, one invented number can discredit an
entire report.

**Decision.** Every number is computed by code (pandas for profiling, DuckDB SQL for everything shown). The
AI receives a *fact pack* of numbers that already exist, each with an ID, and is asked only to select, explain
and recommend. The system prompt forbids new calculations, including sums, differences and derived counts.

**Alternatives considered.**
- *Let the AI analyse raw data or write Python to compute results.* More flexible, but the numbers would be as
  trustworthy as the generated code, and raw rows would leave the user's machine.
- *Let the AI compute, then verify.* Catches errors after the fact instead of preventing them.

**Trade-off.** The AI cannot answer "what if" questions that need new calculations, and insights are limited
to what the engine computed. In exchange, the numbers in an insight are, by construction, numbers the code
produced.

**In the code.** `core/facts.py` builds the fact pack. `ai/insights_ai.py` holds the system prompt and the
JSON schema. Rule-based insights in `core/insights_rules.py` follow the same contract, which is why they
always score 100% on the fact-check (enforced by tests).

## 2. SQL transparency: the SQL shown is the SQL that ran

**Context.** Charts in most dashboards are opaque. Users cannot see the filter, grouping or aggregation behind
a bar, so they either trust it blindly or rebuild it themselves.

**Decision.** Every KPI and chart is a `ChartSpec` or `KPI` that carries its SQL string. The engine executes
that exact string and the UI displays the same string plus the result table in "How this was calculated".
Insight sentences are written from that result, not from a separate calculation.

**Alternatives considered.**
- *Compute with pandas and show pseudo-SQL.* Easy to drift: the shown query might not match what ran.
- *Show only a natural-language description.* Friendlier, but not auditable.

**Trade-off.** Charts are limited to what SQL expresses cleanly, and queries are formatted for readability
rather than brevity. The benefit is a direct, checkable link from every figure to its source.

**In the code.** `core/recommender.py` builds the SQL. `ui/charts.py` (`sql_expander`) renders it. A test in
`tests/test_recommender.py` re-runs every chart's SQL on a fresh engine and asserts the same result shape.

## 3. Fact-checking AI output

**Context.** Even with a strict prompt, a model can round strangely, compute a difference, or hallucinate. The
user needs to know which numbers to trust.

**Decision.** After any response, extract every number (currency, percentages, K/M/B suffixes, years and ISO
dates) and match it to a numeric fact at the precision it was written: "35%" verifies against 34.6, "35.0%"
does not. Percent claims only match percent facts. Text facts that contain digits (such as "Q1 2023" or a
product code) are recognised and skipped. Each number is highlighted green or red, and a badge reports
"Verified numbers: n/m". Unverified numbers are flagged, never removed.

**Alternatives considered.**
- *Reject any response with an unverified number.* Hides useful text and makes the AI path brittle.
- *Ask a second model to check the first.* Doubles cost and still is not deterministic.

**Trade-off.** The checker verifies numbers, not reasoning. Since version 1.2 it also checks a stated sign or
direction and which group a number belongs to (see sections 12 and 13), but a sentence can still draw a wrong
conclusion from correct numbers. This is stated in the Guide's limitations. It is deterministic, fast and explainable, and fact-ID citations give the reader a second check.

**In the code.** `ai/factcheck.py`. Tests in `tests/test_factcheck.py` cover rounding, sign, percent and date
cases, and `tests/test_pipeline.py` proves that every value formatted by `core/formatting.py` round-trips
through the checker.

## 4. Schema-only prompts

**Context.** Users may upload files with personal or commercially sensitive rows. Sending raw data to a
third-party model is a privacy risk and often against company policy.

**Decision.** For insights, the AI sees the schema (names, types, missing share, distinct counts) and
aggregated results only. For Ask your data, it additionally sees simple ranges and up to 10 distinct labels per
category column, so it can write correct `WHERE` clauses. Query results are computed locally and never sent
back to the model.

**Alternatives considered.**
- *Send a sample of rows.* Better context for the model, but leaks records.
- *Send nothing but column names.* Safer, but the model would guess category spellings and write broken filters.

**Trade-off.** Group labels that appear in aggregates (for example the top 10 products) and up to 10 labels per
category do reach the model. The Guide states this precisely rather than claiming "nothing is shared".

**In the code.** `FactPack.to_json()` in `core/facts.py` and `schema_context()` in `ai/nl2sql.py`. A test
asserts that raw row values never appear in the insights prompt.

## 5. DuckDB as the engine

**Context.** The app needs fast aggregations over up to a million rows, readable SQL for transparency and a
way to run user-written queries safely.

**Decision.** Register the typed pandas DataFrame as a table in an in-memory DuckDB connection and run all
analysis as SQL.

**Alternatives considered.**
- *pandas only.* Fast and familiar, but there is no SQL to show users, and user queries would need a custom
  language.
- *SQLite.* Ubiquitous, but row-oriented and slower for analytics, with weaker date and statistics functions
  (no `quantile_cont`, `corr` or `date_trunc`).

**Trade-off.** One more dependency and a SQL dialect to learn. DuckDB registers DataFrames without copying,
supports window functions and statistical aggregates, and can be configured so that queries cannot touch the
file system.

**In the code.** `core/engine.py` (`QueryEngine`).

## 6. Streamlit for the interface

**Context.** A data tool built by one person needs to look professional and ship quickly, with Python end to end.

**Decision.** Streamlit with multipage navigation (`st.navigation` and `st.Page`), a custom CSS design system
injected from one module, and a registered Plotly template.

**Alternatives considered.**
- *React plus a Python API.* Full design control, but two codebases and far more time.
- *Dash.* Flexible callbacks, but more boilerplate for the same result.

**Trade-off.** Streamlit reruns the script on every interaction, so heavy work must be cached, and some styling
relies on CSS selectors that may change between versions. Caching is keyed on the file's SHA-256 fingerprint
(`st.cache_data`), and custom components are plain escaped HTML, so the app stays fast and portable.

**In the code.** `app.py`, `ui/theme.py`, `ui/components.py` and `ui/state.py`. Pages live in `views/` rather
than `pages/`, because Streamlit treats a `pages/` folder as legacy auto-navigation, which bypassed `app.py`
(and therefore the theme) when a page URL was opened directly.

## 7. Health score design

**Context.** Users want one number that summarises data quality, but a black-box score is not useful: they need
to know why a file scored 79.

**Decision.** Start at 100 and subtract one capped penalty per check:
`score = 100 - sum(min(cap, points_per_unit x measure))`. Checks are missing cells, duplicate rows, mixed-type
columns, constant columns and columns with more than 5% IQR outliers. Weights and caps live in one dictionary,
`HEALTH_WEIGHTS`, which the Guide page renders directly. Scores map to grades (A at 90+, B 80+, C 70+, D 60+).

**Alternatives considered.**
- *A learned or statistical quality model.* Harder to explain and to tune without labelled data.
- *A checklist with no score.* Clear, but hard to compare across files.

**Trade-off.** The weights are judgement calls. Caps stop one dominant issue (for example 40% missing values)
from hiding everything else, and the full formula is published so anyone can disagree with a weight and change
it in one place.

**In the code.** `core/health.py`. Every issue carries a severity and a "why it matters" sentence.

## 8. A Power BI kit instead of a .pbix

**Context.** Many analysts finish their work in Power BI. A one-click Power BI file would be the ideal export.

**Decision.** Generate a *Starter Kit* zip: the cleaned CSV, a Power Query (M) script with the detected column
types, DAX measures generated from the detected metric, date and category columns (Total, Average, Count, % of
Total, YoY %, MoM % and Running Total), a whole-year Date table and a five-step quickstart.

**Alternatives considered.**
- *Generate a .pbix.* The format is an undocumented binary; producing one outside Power BI Desktop is fragile
  and could break with any release.
- *A PBIP project with a TMDL semantic model.* Text-based and promising, but it could not be validated against
  Power BI Desktop in this build, so it is on the roadmap rather than shipped untested.

**Trade-off.** Users paste the scripts in themselves, which takes a few minutes. In return, everything is
plain text they can read and review, and averaged metrics get sensible measures (shares and running totals use
the record count instead of summing an average).

**In the code.** `exports/powerbi.py`, with tests on the zip contents, M types and DAX measures.

## 9. Defence in depth for user SQL

**Context.** Ask your data runs SQL written by a model (or typed by the user) against the session's data. A
single validation layer is one bug away from reading a file on the server.

**Decision.** Three independent layers:
1. **Validation:** a single statement, `SELECT` or `WITH` only (confirmed by DuckDB's own parser), no comments,
   blocked keywords (`ATTACH`, `COPY`, `PRAGMA`, `INSTALL`, `LOAD`, writes) and blocked file and system
   functions, no string literal as a table source, and an enforced `LIMIT`.
2. **Sandbox:** the DuckDB connection is created with `enable_external_access = false` and the configuration is
   then locked, so even a query that slips past validation cannot read files, URLs or extensions.
3. **Resource limits:** a 10-second timeout (via `interrupt`) and a 1,000-row cap.

**Alternatives considered.** *Validation only* (simpler, but brittle) or *no free-form SQL* (safe, but loses
the most useful feature for analysts).

**Trade-off.** A few legitimate queries are rejected (for example, those with comments). Literal strings and
quoted identifiers are masked before keyword checks, so values such as "load" in a filter are still allowed.

**In the code.** `ai/nl2sql.py` (`validate_sql`) and `core/engine.py`. `tests/test_nl2sql.py` covers 16 rejection
cases, and `tests/test_recommender.py` proves the sandbox blocks file reads and cannot be switched off.

## 10. Explaining change only where the parts add up

**Context.** "Revenue rose 19.6% last month" invites the next question: which stores, regions or products moved
it? Analysts answer that with a contribution (or variance) breakdown.

**Decision.** The "What drove the latest change" chart compares the last two *complete* periods, per group, in a
single query, and only for totals and counts. For those, the group changes add up to the total change, which
the tests check. Averages are skipped because a group's change in average does not add up to the overall
change; showing it would look precise while misleading.

**Alternatives considered.** *A full mix-and-rate decomposition for averages* (correct, but hard to read for a
non-analyst) or *letting the AI explain the change* (exactly the kind of arithmetic the AI is not allowed to do).

**Trade-off.** Files whose main metric is an average (such as satisfaction scores) get no breakdown. Groups with
a missing label are excluded, and the chart says how many rows that affects.

**In the code.** `core/recommender.py` (`_drivers`) and `tests/test_recommender.py`.

## 11. Other languages without weakening the fact-check

**Context.** Many users read more comfortably in their own language, but the fact-checker parses numbers such
as $785.3K and 34.6%. A Spanish or French text would normally write 34,6 %, which would not parse.

**Decision.** AI insights can be written in eight languages, and the prompt requires every number to keep the
fact pack's display format (period decimals, comma thousands, $ and %) in all of them. Column names and group
labels stay as they appear in the data, so labels with digits are still recognised. The list is limited to
languages the PDF font can render.

**Alternatives considered.** *Locale-aware parsing in the fact-checker* (more natural text, but a second number
grammar to verify and keep in sync) or *machine-translating the English output* (a second model call whose
numbers would also need checking).

**Trade-off.** Numbers look slightly foreign in some languages (34.6% instead of 34,6 %). Rule-based insights
and the interface stay in English.

**In the code.** `ai/insights_ai.py` (`LANGUAGES`, `system_prompt`) and `tests/test_ai.py`.

## 12. Measuring the safeguards with a published benchmark

**Context.** Veridash's pitch is that its numbers can be trusted, but the evidence was a set of unit tests that
I wrote while I already knew how the checker worked. That shows the code does what I intended, not how well it
catches the mistakes a model actually makes.

**Decision.** A deterministic benchmark (`bench/`) attacks the safeguards at scale. It turns every headline
fact in the example datasets into sentences, plants six kinds of error (near misses, 10% errors, wrong units,
swapped digits, another group's number and flipped signs) and counts how many the fact-checker catches, along
with false alarms on correct sentences written in several formats. It also sends 38 harmful and 25 harmless
queries through the SQL guard and the sandbox, and recomputes headline numbers with pandas. The results are
committed, shown on the Benchmark page and verified in CI.

**What it found.** The first run caught 77.9% of planted errors and none of the numbers given to the wrong
group or written with a flipped sign. Both gaps led to new checks (section 13 and the sign rule in section 3),
raising the catch rate to 96.0% with no false alarms.

**Alternatives considered.** *Measuring with real Gemini output* (more realistic, but costs money, needs a key
in CI and gives different scores on every run) or *hand-written test cases only* (they share the author's
blind spots, which is exactly what the first run exposed).

**Trade-off.** Planted errors are systematic, not a sample of real model mistakes, so the score is a lower
bound on what the checker can do rather than a measured hallucination rate. Measuring Gemini directly is on
the roadmap.

**In the code.** `bench/` and `tests/test_bench.py`; the CI step in `.github/workflows/ci.yml`.

## 13. Checking which group a number belongs to

**Context.** "Electronics comes to $209.1K" passed the fact-check when $209.1K was Apparel's revenue, because
the number exists. This is a likely model mistake when it reads a ranked list.

**Decision.** When a number only matches per-group facts (such as `top.2.value`) and its sentence names a group
from the same chart, the number must belong to that group. The group is the one named in brackets right after
the number, otherwise the groups named since the previous number, otherwise the nearest one in the sentence.
Wrong numbers are flagged with a reason, for example "Wrong group: $209.1K is the figure for Apparel, not
Electronics".

**Alternatives considered.** *Asking the AI to cite a fact ID for every number and checking the citation*
(stricter, but brittle with free text) or *full sentence parsing* (heavy and language-specific).

**Trade-off.** It is a heuristic: unusual phrasing such as "Compared with Apparel, $271.4K is the total for
Electronics" attributes the number to the wrong name and raises a false alarm. The benchmark keeps false alarms at zero on correct sentences, and when
a number also matches a non-group fact, the check stays out of the way.

**In the code.** `ai/factcheck.py` (`_groups`, `_named_groups`) and `tests/test_factcheck.py`.

## 14. A web report with no JavaScript

**Context.** Results are often shared with people who will not open the app. A PDF is static and an Excel file
needs Excel; neither lets a reader check where a number came from.

**Decision.** A single HTML file with inline CSS and inline SVG charts drawn by the same code as the PDF. SQL
sits in native collapsible blocks, and each verified number in the insights is a plain link to its row in a
facts table. There is no JavaScript and nothing is loaded from the internet, so the file opens anywhere,
including offline and in email attachments, and cannot run code.

**Alternatives considered.** *Interactive Plotly charts* (about 3.5 MB of JavaScript per file, and scripts are
often blocked in attachments) or *a hosted share link* (would mean storing users' results on a server).

**Trade-off.** Charts are static images without hover. All file content is escaped, and a test checks that a
file with HTML in its column names and values cannot inject markup.

**In the code.** `exports/html_report.py` and `tests/test_exports.py`.
