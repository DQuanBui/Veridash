"""Tests for the Excel, PDF and Power BI exports."""

from __future__ import annotations

import io

import openpyxl
import pytest

from core.pipeline import analyze, prepare
from core.samples import EXAMPLES
from exports.excel import build_excel


@pytest.fixture(scope="module", params=list(EXAMPLES))
def analysis(request):
    ex = EXAMPLES[request.param]
    return analyze(prepare(ex.read_bytes(), ex.filename))


def test_excel_opens_and_has_expected_sheets(analysis):
    data = build_excel(analysis)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    names = wb.sheetnames
    assert names[0] == "Summary"
    assert names[1] == "Profile"
    assert names[-1] == "Data"
    assert len(names) == 3 + len(analysis.charts)
    assert all(len(n) <= 31 for n in names)


def test_excel_data_sheet_is_a_full_table(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    ws = wb["Data"]
    assert ws.max_row == analysis.profile.n_rows + 1
    assert [c.value for c in ws[1]] == list(analysis.profile.df.columns)
    assert "VeridashData" in ws.tables
    assert ws.freeze_panes == "A2"


def test_excel_has_native_charts(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    chart_sheets = [wb[n] for n in wb.sheetnames[2:-1]]
    with_charts = [ws for ws in chart_sheets if ws._charts]
    non_heatmap = [c for c in analysis.charts if c.kind != "heatmap"]
    assert len(with_charts) == len(non_heatmap)


def test_excel_summary_mentions_health_and_verification(analysis):
    wb = openpyxl.load_workbook(io.BytesIO(build_excel(analysis)))
    text = " ".join(str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value)
    assert f"{analysis.health.score}/100" in text
    assert "Verified numbers:" in text
    assert "Rule-based" in text
