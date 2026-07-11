from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("apps/ai_safety_check/app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    labels = {b.label for b in at.button}
    assert "Re-run live" in labels


def test_rerun_live_persists_artifacts(monkeypatch):
    from apps.ai_safety_check import main

    fake_state = {"tools": [], "dangers": [], "cases": []}
    saved = {}

    async def fake_run(*, craft=None, llm=None, tavily=None):
        return fake_state

    def fake_create_run_dir():
        return "runs/safety_TESTFAKE"

    def fake_save_artifacts(state, out_dir):
        saved["state"] = state
        saved["out_dir"] = out_dir

    monkeypatch.setattr(main, "run", fake_run)
    monkeypatch.setattr(main, "_create_run_dir", fake_create_run_dir)
    monkeypatch.setattr(main, "save_artifacts", fake_save_artifacts)

    at = AppTest.from_file("apps/ai_safety_check/app.py", default_timeout=30)
    at.run()
    [b for b in at.button if b.label == "Re-run live"][0].click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert saved["state"] is fake_state
    assert saved["out_dir"] == "runs/safety_TESTFAKE"
