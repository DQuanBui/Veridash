"""Power BI Starter Kit: a zip that gets a user from file to report in minutes.

Contents:
    data.csv        the cleaned, typed dataset (UTF-8, ISO dates)
    load_data.pq    Power Query (M) script that loads data.csv with correct types
    measures.dax    Total, Average, Count, % of Total, YoY %, MoM % and Running Total
    date_table.dax  a calculated Date table covering whole years of the data
    QUICKSTART.md   five steps to a working report

Why a kit rather than a .pbix: .pbix is an undocumented binary format that
cannot be generated reliably outside Power BI Desktop, while M and DAX are
plain text that users can read, review and paste.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

import pandas as pd

from core.formatting import pretty
from core.pipeline import Analysis
from core.profiler import ColType, ColumnProfile

TABLE = "Data"


def _m_string(text: str) -> str:
    return '"' + str(text).replace('"', '""') + '"'


def _dax_col(name: str) -> str:
    return f"{TABLE}[{str(name).replace(']', ']]')}]"


def _measure_ref(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def _title(name: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in pretty(name).split())


def _m_type(col: ColumnProfile, series: pd.Series) -> str:
    if col.col_type == ColType.NUMBER:
        values = series.dropna()
        if len(values) and bool((values.astype("float64") % 1 == 0).all()):
            return "Int64.Type"
        return "type number"
    if col.col_type == ColType.DATE:
        return "type datetime" if col.stats.get("has_time") else "type date"
    if col.col_type == ColType.BOOLEAN:
        return "type logical"
    if col.col_type == ColType.ID and pd.api.types.is_numeric_dtype(series):
        return "Int64.Type"
    return "type text"


def data_csv(analysis: Analysis) -> bytes:
    """The cleaned dataset as UTF-8 CSV with ISO dates."""
    df = analysis.profile.df.copy()
    for col in analysis.profile.columns:
        if col.col_type == ColType.DATE:
            fmt = "%Y-%m-%d %H:%M:%S" if col.stats.get("has_time") else "%Y-%m-%d"
            df[col.name] = df[col.name].dt.strftime(fmt)
    return df.to_csv(index=False, lineterminator="\n").encode("utf-8")


def power_query_m(analysis: Analysis) -> str:
    """Power Query M script that loads data.csv with the detected types."""
    df = analysis.profile.df
    types = ",\n".join(
        f"            {{{_m_string(c.name)}, {_m_type(c, df[c.name])}}}" for c in analysis.profile.columns
    )
    return (
        "// Veridash Power BI Starter Kit: load data.csv with the column types Veridash detected.\n"
        "// In Power BI Desktop: Get data > Blank query > Advanced editor, paste this script,\n"
        "// change FilePath below, click Done and rename the query to Data.\n"
        "let\n"
        '    FilePath = "C:\\Users\\you\\Downloads\\veridash_kit\\data.csv",\n'
        "    Source = Csv.Document(\n"
        "        File.Contents(FilePath),\n"
        f"        [Delimiter = \",\", Columns = {len(df.columns)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]\n"
        "    ),\n"
        "    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n"
        "    ChangedTypes = Table.TransformColumnTypes(\n"
        "        PromotedHeaders,\n"
        "        {\n"
        f"{types}\n"
        "        },\n"
        '        "en-US"\n'
        "    )\n"
        "in\n"
        "    ChangedTypes\n"
    )


def dax_measures(analysis: Analysis) -> str:
    """DAX measures generated from the detected metric, date and category columns."""
    sel = analysis.selection
    lines = [
        "// Veridash Power BI Starter Kit: DAX measures.",
        "// Add each measure with Modeling > New measure (one measure per paste).",
        f"// Table: {TABLE}. Primary metric: {sel.metric or 'none (record counts)'}."
        + (f" Date column: {sel.date_col}." if sel.date_col else ""),
        "",
    ]
    count_name = "Record Count"
    lines += [f"{count_name} = COUNTROWS ( {TABLE} )", ""]
    if sel.metric:
        m = _title(sel.metric)
        total, avg = f"Total {m}", f"Average {m}"
        base = total if sel.agg == "SUM" else avg
        col = _dax_col(sel.metric)
        lines += [f"{total} = SUM ( {col} )", "", f"{avg} = AVERAGE ( {col} )", ""]
        if sel.agg != "SUM":
            # Shares and running totals of an averaged measure are not meaningful,
            # so those measures are built on the record count instead.
            lines += [f"// {m} is averaged, so the share and running measures below use {count_name}.", ""]
            total = count_name
        share_name = m if sel.agg == "SUM" else "Records"
        lines += [
            "// Share of the visible total; works with any slicer or visual grouping.",
            f"{share_name} % of Total =",
            f"DIVIDE ( {_measure_ref(total)}, CALCULATE ( {_measure_ref(total)}, ALLSELECTED ( {TABLE} ) ) )",
            "",
        ]
    else:
        base, total = count_name, count_name
        m = share_name = "Records"
        lines += [
            "// Share of the visible total; works with any slicer or visual grouping.",
            "Records % of Total =",
            f"DIVIDE ( {_measure_ref(count_name)}, CALCULATE ( {_measure_ref(count_name)}, ALLSELECTED ( {TABLE} ) ) )",
            "",
        ]
    if sel.categories:
        cat = sel.categories[0]
        lines += [
            f"// Share within {cat}: the selected {cat} versus all {cat} values.",
            f"{share_name} % of {_title(cat)} Total =",
            f"DIVIDE ( {_measure_ref(total)}, CALCULATE ( {_measure_ref(total)}, REMOVEFILTERS ( {_dax_col(cat)} ) ) )",
            "",
        ]
    if sel.date_col:
        ref = _measure_ref(base)
        lines += [
            "// Time intelligence: requires the Date table (date_table.dax), marked as a date table",
            f"// and related one-to-many from 'Date'[Date] to {_dax_col(sel.date_col)}.",
            f"{m} YoY % =",
            f"VAR CurrentValue = {ref}",
            f"VAR PriorValue = CALCULATE ( {ref}, SAMEPERIODLASTYEAR ( 'Date'[Date] ) )",
            "RETURN DIVIDE ( CurrentValue - PriorValue, PriorValue )",
            "",
            f"{m} MoM % =",
            f"VAR CurrentValue = {ref}",
            f"VAR PriorValue = CALCULATE ( {ref}, DATEADD ( 'Date'[Date], -1, MONTH ) )",
            "RETURN DIVIDE ( CurrentValue - PriorValue, PriorValue )",
            "",
            f"Running {total} =",
            "CALCULATE (",
            f"    {_measure_ref(total)},",
            "    FILTER ( ALL ( 'Date'[Date] ), 'Date'[Date] <= MAX ( 'Date'[Date] ) )",
            ")",
            "",
        ]
    else:
        lines += ["// No date column was detected, so YoY %, MoM % and Running Total are not included.", ""]
    return "\n".join(lines)


def date_table_dax(analysis: Analysis) -> str:
    """A calculated Date table spanning whole calendar years of the data."""
    sel = analysis.selection
    if not sel.date_col:
        return (
            "// No date column was detected in this file, so a Date table is not needed.\n"
            "// If you add dates later, create one with CALENDAR ( start, end ) and mark it as a date table.\n"
        )
    stats = analysis.profile.get(sel.date_col).stats
    start = datetime.fromtimestamp(stats["min"], tz=UTC).year
    end = datetime.fromtimestamp(stats["max"], tz=UTC).year
    return (
        "// Veridash Power BI Starter Kit: Date table.\n"
        "// Modeling > New table, paste, then Table tools > Mark as date table (column: Date).\n"
        f"// Covers whole years {start}-{end} so YoY and MoM comparisons work.\n"
        "Date =\n"
        "ADDCOLUMNS (\n"
        f"    CALENDAR ( DATE ( {start}, 1, 1 ), DATE ( {end}, 12, 31 ) ),\n"
        '    "Year", YEAR ( [Date] ),\n'
        '    "Quarter", "Q" & QUARTER ( [Date] ),\n'
        '    "Month Number", MONTH ( [Date] ),\n'
        '    "Month", FORMAT ( [Date], "mmm" ),\n'
        '    "Year Month", FORMAT ( [Date], "yyyy-mm" ),\n'
        '    "Week of Year", WEEKNUM ( [Date] ),\n'
        '    "Weekday", FORMAT ( [Date], "ddd" )\n'
        ")\n"
    )


def quickstart_md(analysis: Analysis) -> str:
    """Five steps from the kit to a working Power BI report."""
    sel = analysis.selection
    metric = _title(sel.metric) if sel.metric else "Records"
    first_measure = (f"{'Total' if sel.agg == 'SUM' else 'Average'} {metric}") if sel.metric else "Record Count"
    cat = sel.categories[0] if sel.categories else None
    rel = (
        f"In Model view, drag Date[Date] onto Data[{sel.date_col}] to create a one-to-many relationship."
        if sel.date_col
        else "This file has no date column, so you can skip the Date table and relationship."
    )
    visual = f"a clustered bar chart of [{first_measure}] by {cat}" if cat else f"a card showing [{first_measure}]"
    trend = f" and a line chart of [{first_measure}] by Date[Year Month]" if sel.date_col else ""
    return f"""# Veridash Power BI Starter Kit

Generated by Veridash for **{analysis.name}** ({analysis.profile.n_rows:,} rows, {analysis.profile.n_cols} columns).

## Five steps to a working report

1. **Load the data.** Save this folder somewhere permanent. In Power BI Desktop choose
   Get data > Blank query > Advanced editor, paste `load_data.pq`, set `FilePath` to the
   full path of `data.csv`, click Done, then rename the query to **Data** and click Close & Apply.
2. **Add the Date table.** Modeling > New table, paste `date_table.dax`, then
   Table tools > Mark as date table and pick the Date column. Sort Month by Month Number.
3. **Relate the tables.** {rel}
4. **Add the measures.** Select the Data table, then Modeling > New measure for each
   measure in `measures.dax` (paste one measure at a time).
5. **Build a first page.** Add {visual}{trend}. Compare the numbers with the Veridash
   KPIs: they should match, because both come from the same cleaned data.

## What is inside

| File | Purpose |
|---|---|
| data.csv | The cleaned dataset (UTF-8, ISO dates, booleans as True/False) |
| load_data.pq | Power Query script with the column types Veridash detected |
| measures.dax | Total, Average, Count, % of Total, YoY %, MoM % and Running Total |
| date_table.dax | A Date table covering whole years of your data |

Veridash detected **{sel.metric or "no numeric metric"}** as the primary metric
({sel.agg}){f" and **{sel.date_col}** as the date column" if sel.date_col else ""}.
"""


def build_powerbi_kit(analysis: Analysis) -> bytes:
    """Build the Starter Kit zip in memory and return its bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.csv", data_csv(analysis))
        zf.writestr("load_data.pq", power_query_m(analysis))
        zf.writestr("measures.dax", dax_measures(analysis))
        zf.writestr("date_table.dax", date_table_dax(analysis))
        zf.writestr("QUICKSTART.md", quickstart_md(analysis))
    return buffer.getvalue()
