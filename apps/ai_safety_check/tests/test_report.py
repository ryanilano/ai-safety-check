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


NO_COVERAGE_STATE = {
    "tools": [{"name": "tinytool", "category": "AGENT", "verdict": "GREEN",
               "significance": "obscure agent", "capabilities": [], "stars": 3,
               "signals": {
                   "cve": {"detail": "0 CRITICAL / 0 HIGH / 0 MODERATE advisories"},
                   "capability": {"detail": "x"}, "staleness": {"detail": "x"},
                   "blast": {"detail": "no dependents recorded", "dependent_count": None},
                   "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "no known incidents", "source_url": None}}],
    "dangers": [],
    "cases": ["tinytool"],
}

COVERED_STATE = {
    "tools": [{"name": "bigtool", "category": "AGENT", "verdict": "YELLOW",
               "significance": "popular agent", "capabilities": [], "stars": 5000,
               "signals": {
                   "cve": {"detail": "x"}, "capability": {"detail": "x"},
                   "staleness": {"detail": "x"},
                   "blast": {"detail": "42 downstream dependents", "dependent_count": 42},
                   "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "no known incidents", "source_url": None}}],
    "dangers": [],
    "cases": ["bigtool"],
}


def test_leaderboard_flags_missing_dependents_coverage():
    md = report.render_markdown(NO_COVERAGE_STATE)
    assert "⚠️" in md
    assert "not measured" in md


def test_leaderboard_no_marker_when_dependents_data_present():
    md = report.render_markdown(COVERED_STATE)
    assert "⚠️¹" not in md


def test_case_study_marks_blast_as_unverified_when_no_coverage():
    md = report.render_markdown(NO_COVERAGE_STATE)
    assert "not a verified measurement" in md


CVE_STATE = {
    "tools": [{"name": "leaky", "category": "AGENT", "verdict": "RED",
               "significance": "agent", "capabilities": ["executes_code"], "stars": 10,
               "signals": {"cve": {"detail": "x"}, "capability": {"detail": "x"},
                           "staleness": {"detail": "x"},
                           "blast": {"detail": "x", "dependent_count": 5},
                           "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "patched CVE-2023-6015 after disclosure",
                             "source_url": "http://x"}},
              {"name": "sketchy", "category": "AGENT", "verdict": "RED",
               "significance": "agent", "capabilities": ["executes_code"], "stars": 1,
               "signals": {"cve": {"detail": "x"}, "capability": {"detail": "x"},
                           "staleness": {"detail": "x"},
                           "blast": {"detail": "x", "dependent_count": 2},
                           "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "flagged as CVE-23-1 by a blog post (unconfirmed)",
                             "source_url": "http://y"}}],
    "dangers": [{"pattern": "bogus ref CVE-99-1", "seen_in": ["sketchy"],
                 "remediation": "verify against CVE-2023-6015 before trusting it"}],
    "cases": ["leaky", "sketchy"],
}


def test_valid_cve_id_is_rendered_verbatim():
    md = report.render_markdown(CVE_STATE)
    assert "CVE-2023-6015" in md


def test_malformed_cve_id_is_flagged_unverified_not_rendered_verbatim():
    md = report.render_markdown(CVE_STATE)
    assert "CVE-23-1" not in md
    assert "CVE-99-1" not in md
    assert "[unverified advisory ID]" in md
