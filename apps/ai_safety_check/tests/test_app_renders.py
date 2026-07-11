from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("apps/ai_safety_check/app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    labels = {b.label for b in at.button}
    assert "Re-run live" in labels
