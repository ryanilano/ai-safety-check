from apps.ai_safety_check import gating


def test_cve_critical_is_red():
    r = gating.grade_cve({"CRITICAL": 2, "HIGH": 0, "MODERATE": 0}, worst_cvss=10.0)
    assert r["verdict"] == "RED"
    assert "CRITICAL" in r["detail"]


def test_cve_none_is_green():
    r = gating.grade_cve({"CRITICAL": 0, "HIGH": 0, "MODERATE": 0}, worst_cvss=None)
    assert r["verdict"] == "GREEN"


def test_capability_executes_code_plus_cve_is_red():
    r = gating.grade_capability(["executes_code"], has_cve=True)
    assert r["verdict"] == "RED"


def test_capability_executes_code_alone_is_yellow():
    r = gating.grade_capability(["executes_code"], has_cve=False)
    assert r["verdict"] == "YELLOW"


def test_staleness_two_years_is_red():
    assert gating.grade_staleness(800)["verdict"] == "RED"


def test_staleness_fresh_is_green():
    assert gating.grade_staleness(30)["verdict"] == "GREEN"


def test_health_no_repo_is_yellow_flag():
    r = gating.grade_health(stars=None, open_issues=None, has_repo=False)
    assert r["verdict"] == "YELLOW"


def test_identity_squat_is_red():
    assert gating.grade_identity(True)["verdict"] == "RED"


def test_composite_worst_wins():
    signals = {
        "cve": {"verdict": "GREEN"}, "capability": {"verdict": "RED"},
        "staleness": {"verdict": "GREEN"}, "blast": {"verdict": "YELLOW"},
        "health": {"verdict": "GREEN"}, "identity": {"verdict": "GREEN"},
    }
    assert gating.composite(signals) == "RED"


def test_composite_all_green():
    signals = {k: {"verdict": "GREEN"} for k in
               ["cve", "capability", "staleness", "blast", "health", "identity"]}
    assert gating.composite(signals) == "GREEN"
