import os

from apps.seller_delivery_agent.charts import render_chart


def test_render_chart_writes_png(tmp_path):
    figure = {"data": [{"type": "bar", "x": ["on_time", "late"], "y": [4.0, 2.54]}],
              "layout": {"title": "Avg Review Score"}}
    out = str(tmp_path / "chart.png")
    result = render_chart(figure, out)
    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
