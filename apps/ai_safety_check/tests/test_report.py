from apps.ai_safety_check import report

STATE = {
    "tools": [{"name": "mlflow", "category": "INFERENCE_SERVER", "verdict": "RED",
               "significance": "ml platform", "capabilities": ["exposes_server"],
               "stars": 15000,
               "signals": {"cve": {"detail": "2 CRITICAL"}, "capability": {"detail": "x"},
                           "staleness": {"detail": "x"}, "blast": {"detail": "x"},
                           "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "actively exploited", "source_url": "http://x"}}],
    "dangers": [{"pattern": "web UI exposes filesystem", "seen_in": ["mlflow"],
                 "remediation": "auth the UI"}],
    "cases": ["mlflow"],
}


def test_markdown_has_all_three_tiers():
    md = report.render_markdown(STATE)
    assert "🔴" in md and "mlflow" in md          # leaderboard badge
    assert "Case Stud" in md                       # case-study tier
    assert "web UI exposes filesystem" in md       # dangers tier


def test_figure_has_data():
    fig = report.leaderboard_figure(STATE)
    assert fig["data"]
