"""Tests for core.loader: formats, encodings, delimiters and bad inputs."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from core import loader
from core.loader import LoadError, clean_columns, load_file, sniff_delimiter


def _xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def test_reads_basic_csv():
    lf = load_file(b"a,b\n1,2\n3,4\n", "x.csv")
    assert list(lf.df.columns) == ["a", "b"]
    assert len(lf.df) == 2
    assert lf.delimiter == ","
    assert lf.encoding == "utf-8"


@pytest.mark.parametrize("sep", [";", "\t", "|"])
def test_sniffs_delimiters(sep):
    data = f"name{sep}value\nx{sep}1\ny{sep}2\n".encode()
    lf = load_file(data, "x.csv")
    assert list(lf.df.columns) == ["name", "value"]
    assert lf.delimiter == sep


def test_utf8_bom_is_handled():
    lf = load_file("﻿city,n\nHà Nội,1\n".encode(), "bom.csv")
    assert lf.df.columns[0] == "city"
    assert lf.encoding == "utf-8-sig"


def test_latin1_fallback():
    data = "name,amount\nCafé,10\nNiño,12\n".encode("latin-1")
    lf = load_file(data, "latin.csv")
    assert lf.encoding == "latin-1"
    assert lf.df["name"].tolist() == ["Café", "Niño"]


def test_reads_xlsx_and_lists_sheets():
    data = _xlsx_bytes({"Sales": pd.DataFrame({"a": [1, 2]}), "Costs": pd.DataFrame({"b": [3]})})
    lf = load_file(data, "book.xlsx")
    assert lf.sheet == "Sales"
    assert lf.sheet_names == ["Sales", "Costs"]
    second = load_file(data, "book.xlsx", sheet="Costs")
    assert list(second.df.columns) == ["b"]
    assert second.file_hash != lf.file_hash


def test_column_cleaning_strips_and_dedupes():
    assert clean_columns([" a ", "a", "", "Unnamed: 3", "A"]) == ["a", "a_2", "column_3", "column_4", "A_3"]


def test_empty_file_rejected():
    with pytest.raises(LoadError, match="empty"):
        load_file(b"", "x.csv")
    with pytest.raises(LoadError, match="empty"):
        load_file(b"   \n", "x.csv")


def test_header_only_rejected():
    with pytest.raises(LoadError, match="no data rows"):
        load_file(b"a,b,c\n", "x.csv")


def test_missing_header_rejected():
    with pytest.raises(LoadError, match="looks like data"):
        load_file(b"1,2,3\n4,5,6\n", "x.csv")


def test_unsupported_extension_rejected():
    with pytest.raises(LoadError, match="Unsupported"):
        load_file(b"a,b\n1,2\n", "x.json")


def test_too_large_rejected(monkeypatch):
    monkeypatch.setattr(loader, "MAX_FILE_MB", 0.00001)
    with pytest.raises(LoadError, match="limit"):
        load_file(b"a,b\n1,2\n3,4\n", "x.csv")


def test_too_many_rows_rejected(monkeypatch):
    monkeypatch.setattr(loader, "MAX_ROWS", 2)
    with pytest.raises(LoadError, match="rows"):
        load_file(b"a\n1\n2\n3\n", "x.csv")


def test_corrupt_excel_rejected():
    with pytest.raises(LoadError, match="could not be opened"):
        load_file(b"not really excel", "x.xlsx")


def test_sniff_defaults_to_comma():
    assert sniff_delimiter("single_column\nvalue\n") == ","
