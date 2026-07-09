"""The Streamlit app must render without raising when executed as an app script.

`streamlit run apps/seller_delivery_agent/app.py` runs the file as a top-level script, so
relative imports fail — this test uses Streamlit's AppTest harness (the same execution path a
browser session drives) to catch that class of bug, which an HTTP-200 check misses.
"""
from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("apps/seller_delivery_agent/app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # key controls present
    labels = {b.label for b in at.button}
    assert "🔎 Investigate" in labels
    assert "Check connection" in labels
    assert len(at.text_area) >= 1  # free-text question box
