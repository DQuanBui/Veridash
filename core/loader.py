"""Read uploaded CSV and Excel files into pandas, entirely in memory.

Nothing in this module touches the file system: inputs are raw ``bytes`` and
outputs are DataFrames. Errors are raised as :class:`LoadError` with messages
that can be shown to users as-is.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field

import pandas as pd

from core.settings import MAX_COLUMNS, MAX_FILE_MB, MAX_ROWS

ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")
DELIMITERS = ",;\t|"
CSV_EXTENSIONS = (".csv", ".txt", ".tsv")
EXCEL_EXTENSIONS = (".xlsx", ".xls")
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS + EXCEL_EXTENSIONS


class LoadError(ValueError):
    """A file could not be loaded. The message is safe to show to users."""


@dataclass
class LoadedFile:
    """A successfully loaded table plus metadata about how it was read."""

    df: pd.DataFrame
    name: str
    file_hash: str
    n_bytes: int
    sheet: str | None = None
    sheet_names: list[str] = field(default_factory=list)
    encoding: str | None = None
    delimiter: str | None = None
    notes: list[str] = field(default_factory=list)


def file_hash(data: bytes) -> str:
    """Return a short SHA-256 fingerprint used as the cache key for a file."""
    return hashlib.sha256(data).hexdigest()[:16]


def _extension(filename: str) -> str:
    match = re.search(r"\.[A-Za-z0-9]+$", filename or "")
    return match.group(0).lower() if match else ""


def check_size(data: bytes) -> None:
    """Reject empty files and files larger than the configured limit."""
    if not data or not data.strip():
        raise LoadError("The file is empty. Please upload a file with a header row and data.")
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise LoadError(
            f"The file is {size_mb:.1f} MB, which is over the {MAX_FILE_MB} MB limit. "
            "Try filtering it or saving fewer columns."
        )


def decode_text(data: bytes) -> tuple[str, str]:
    """Decode bytes trying utf-8, utf-8-sig, then latin-1. Returns (text, encoding)."""
    for enc in ENCODINGS:
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        if enc == "utf-8" and text.startswith("﻿"):
            return text[1:], "utf-8-sig"
        return text, enc
    raise LoadError("Could not read the file's text encoding.")  # pragma: no cover


def sniff_delimiter(text: str) -> str:
    """Detect the delimiter from the first lines of a CSV. Defaults to a comma."""
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: first.count(d) for d in DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def clean_columns(columns: list[object]) -> list[str]:
    """Strip names, name blank/unnamed columns and make every name unique."""
    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for i, col in enumerate(columns, start=1):
        name = re.sub(r"\s+", " ", str(col)).strip()
        if not name or name.lower() == "nan" or re.fullmatch(r"Unnamed: \d+(_level_\d+)?", name):
            name = f"column_{i}"
        base = name
        if base.lower() in seen:
            seen[base.lower()] += 1
            name = f"{base}_{seen[base.lower()]}"
            while name.lower() in seen:
                seen[base.lower()] += 1
                name = f"{base}_{seen[base.lower()]}"
        seen[name.lower()] = seen.get(name.lower(), 1)
        cleaned.append(name)
    return cleaned


def _looks_like_number(value: str) -> bool:
    return bool(re.fullmatch(r"[-+$€£(]*\d[\d,.\s]*%?\)?", value.strip()))


def _validate_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Apply shape checks shared by CSV and Excel inputs.

    Returns the cleaned frame and whether any column names were changed.
    """
    df = df.dropna(axis=0, how="all")
    if df.shape[0] == 0:
        raise LoadError("The file has column headers but no data rows.")
    df = df.dropna(axis=1, how="all")
    if df.shape[1] == 0:
        raise LoadError("No columns were found. Check that the file has a header row.")
    headers = [str(c) for c in df.columns]
    if len(headers) > 1 and all(_looks_like_number(h) for h in headers):
        raise LoadError(
            "The first row looks like data, not column names. "
            "Add a single header row that names each column."
        )
    if df.shape[1] > MAX_COLUMNS:
        raise LoadError(f"The file has {df.shape[1]} columns; the limit is {MAX_COLUMNS}.")
    if df.shape[0] > MAX_ROWS:
        raise LoadError(
            f"The file has {df.shape[0]:,} rows; the limit is {MAX_ROWS:,}. "
            "Try aggregating or filtering it first."
        )
    before = [str(c) for c in df.columns]
    df.columns = clean_columns(list(df.columns))
    return df.reset_index(drop=True), before != list(df.columns)


def read_csv_bytes(data: bytes) -> tuple[pd.DataFrame, str, str]:
    """Parse CSV bytes. Returns ``(df, encoding, delimiter)``."""
    text, encoding = decode_text(data)
    delimiter = sniff_delimiter(text)
    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            skipinitialspace=True,
            on_bad_lines="error",
            low_memory=False,
            nrows=MAX_ROWS + 1,
        )
    except pd.errors.EmptyDataError as exc:
        raise LoadError("The file is empty. Please upload a file with a header row and data.") from exc
    except pd.errors.ParserError as exc:
        raise LoadError(
            "Some rows have a different number of fields than the header. "
            "Check for unquoted delimiters inside values."
        ) from exc
    return df, encoding, delimiter


def list_excel_sheets(data: bytes, filename: str) -> list[str]:
    """Return the sheet names of an Excel workbook."""
    try:
        with pd.ExcelFile(io.BytesIO(data), engine=_excel_engine(filename)) as xl:
            return [str(s) for s in xl.sheet_names]
    except Exception as exc:
        raise LoadError("This Excel file could not be opened. It may be corrupted or password-protected.") from exc


def _excel_engine(filename: str) -> str:
    return "xlrd" if _extension(filename) == ".xls" else "openpyxl"


def read_excel_bytes(data: bytes, filename: str, sheet: str | None = None) -> tuple[pd.DataFrame, str, list[str]]:
    """Parse one sheet of an Excel workbook. Returns ``(df, sheet, sheet_names)``."""
    sheets = list_excel_sheets(data, filename)
    if not sheets:
        raise LoadError("The workbook has no sheets.")
    chosen = sheet if sheet in sheets else sheets[0]
    try:
        df = pd.read_excel(io.BytesIO(data), sheet_name=chosen, engine=_excel_engine(filename))
    except Exception as exc:
        raise LoadError(f"Sheet '{chosen}' could not be read.") from exc
    return df, chosen, sheets


def load_file(data: bytes, filename: str, sheet: str | None = None) -> LoadedFile:
    """Load a CSV or Excel file from raw bytes.

    Args:
        data: The file contents.
        filename: Original file name; its extension selects the parser.
        sheet: Optional sheet name for Excel workbooks (defaults to the first).

    Raises:
        LoadError: With a user-facing explanation if the file cannot be used.
    """
    ext = _extension(filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise LoadError("Unsupported file type. Upload a .csv, .xlsx or .xls file.")
    check_size(data)

    notes: list[str] = []
    if ext in EXCEL_EXTENSIONS:
        raw, chosen, sheets = read_excel_bytes(data, filename, sheet)
        encoding = delimiter = None
        if len(sheets) > 1:
            notes.append(f"Workbook has {len(sheets)} sheets; analyzing '{chosen}'.")
    else:
        raw, encoding, delimiter = read_csv_bytes(data)
        chosen, sheets = None, []
        if encoding != "utf-8":
            notes.append(f"Read with {encoding} encoding.")
        if delimiter != ",":
            notes.append(f"Detected delimiter: {'tab' if delimiter == chr(9) else repr(delimiter)}.")

    df, renamed = _validate_frame(raw)
    if renamed:
        notes.append("Some column names were cleaned (trimmed, renamed or de-duplicated).")

    return LoadedFile(
        df=df,
        name=filename,
        file_hash=file_hash(data + (sheet or "").encode()),
        n_bytes=len(data),
        sheet=chosen,
        sheet_names=sheets,
        encoding=encoding,
        delimiter=delimiter,
        notes=notes,
    )
