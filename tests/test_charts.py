"""Tests that every recommended chart renders to a Plotly figure."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from core.engine import QueryEngine
from core.loader import load_file
from core.profiler import profile_dataframe
from core.recommender import make_selection, recommend_charts
from core.samples import EXAMPLES
from ui.charts import auto_figure, correlation_matrix, figure_for
from ui.theme import DARK, LIGHT


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=["light", "dark"])
@pytest.mark.parametrize("key", list(EXAMPLES))
def test_figures_build_for_every_chart(key, tokens):
    ex = EXAMPLES[key]
    profile = profile_dataframe(load_file(ex.read_bytes(), ex.filename).df)
    with QueryEngine(profile.df) as engine:
        charts = recommend_charts(engine, profile, make_selection(profile))
    for chart in charts:
        fig = figure_for(chart, tokens)
        assert isinstance(fig, go.Figure)
        assert fig.layout.template is not None
        assert fig.data, chart.key
        if chart.kind == "heatmap":
            matrix = correlation_matrix(chart)
            assert (matrix.values == matrix.values.T).all()


def test_auto_figure_choices():
    by_cat = pd.DataFrame({"region": ["A", "B", "C"], "total": [3, 2, 1]})
    assert isinstance(auto_figure(by_cat).data[0], go.Bar)
    by_date = pd.DataFrame({"d": pd.date_range("2024-01-01", periods=5), "v": range(5)})
    assert isinstance(auto_figure(by_date).data[0], go.Scatter)
    assert auto_figure(pd.DataFrame({"only": [1, 2]})) is None
    assert auto_figure(pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})) is None
