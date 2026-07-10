"""Render Plotly figure specs (from generate_plotly_chart) to PNG."""
import plotly.graph_objects as go


def render_chart(figure: dict, out_path: str) -> str:
    fig = go.Figure(data=figure.get("data", []), layout=figure.get("layout", {}))
    fig.write_image(out_path, width=1200, height=600, scale=2)
    return out_path
