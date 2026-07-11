from apps.ai_safety_check import queries


def test_advisories_mentions_name_and_severity():
    q = queries.advisories_for("mlflow")
    assert "mlflow" in q
    assert "GitHubSeverity" in q or "severity" in q.lower()


def test_discover_mentions_stars_and_limit():
    q = queries.discover_top_ai_projects(15)
    assert "star" in q.lower()
    assert "15" in q
