import asyncio
import os

# config.py validates required env vars at import time — set fakes before
# importing nodes (which imports config) if they aren't already present.
os.environ.setdefault("MCP_URL", "https://example.invalid/mcp")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("KEYCLOAK_URL", "https://example.invalid")
os.environ.setdefault("KEYCLOAK_REFRESH_TOKEN", "fake-refresh-token")
os.environ.setdefault("DEPS_CONNECTION", "deps_conn")
os.environ.setdefault("GITHUB_CONNECTION", "github_conn")
os.environ.setdefault("NEBIUS_API_KEY", "fake-nebius-key")

from apps.ai_safety_check import nodes


# Canned results use the REAL column names CRAFT generate_sql produces for each
# pipeline query (verified against live output), so tests exercise the
# column-NAME-based parsing rather than fixed positions.
def _canned(question, *, advisories=None, identity=None):
    q = question.lower()
    if "advisor" in q:
        return (advisories if advisories is not None else
                {"columns": ["Title", "CVSS3Score", "GitHubSeverity"],
                 "rows": [["path traversal", 10.0, "CRITICAL"],
                          ["arbitrary code execution", 10.0, "CRITICAL"]]}, "SELECT ... advisories")
    if "dependents" in q:
        return ({"columns": ["DISTINCT_DEPENDENT_PACKAGES"], "rows": [[1500]]}, "SELECT dependents")
    if "upstreampublishedat" in q:
        return ({"columns": ["MostRecentUpstreamPublishedAt", "TotalVersions"],
                 "rows": [["2023-07-17T00:00:00", 78]]}, "SELECT staleness")
    if "projects" in q:
        return ({"columns": ["ProjectName", "StarsCount", "ForksCount", "OpenIssuesCount"],
                 "rows": [["mlflow/mlflow", 15000, 3000, 700]]}, "SELECT health")
    # identity (all-systems version counts; most 0)
    return (identity if identity is not None else
            {"columns": ["System", "VERSION_COUNT"],
             "rows": [["PYPI", 78], ["NPM", 0], ["MAVEN", 0]]}, "SELECT identity")


class FakeCraft:
    def __init__(self, *, advisories=None, identity=None):
        self._advisories = advisories
        self._identity = identity

    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        return _canned(question, advisories=self._advisories, identity=self._identity)


def test_gate_node_reds_out_mlflow():
    state = {"tools": [{"name": "mlflow", "system": "PYPI", "category": "INFERENCE_SERVER",
                        "capabilities": ["exposes_server", "filesystem"], "significance": "ml platform",
                        "stars": 15000, "sql_log": []}], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraft()))
    tool = out["tools"][0]
    assert tool["verdict"] == "RED"          # 2 CVSS-10 criticals
    assert tool["signals"]["cve"]["verdict"] == "RED"
    assert tool["signals"]["health"]["stars"] == 15000     # name-based: StarsCount col
    assert tool["signals"]["health"]["open_issues"] == 700  # name-based: OpenIssuesCount col
    assert any(lbl.startswith("advisories") for lbl, _ in tool["sql_log"])


def test_gate_node_detects_single_ecosystem_squat():
    # anthropic-style: present in exactly one ecosystem with a lone version.
    squat_identity = {"columns": ["System", "VERSION_COUNT"],
                      "rows": [["NPM", 1], ["PYPI", 0], ["MAVEN", 0], ["CARGO", 0]]}
    clean_advisories = {"columns": ["Title", "CVSS3Score", "GitHubSeverity"], "rows": []}
    state = {"tools": [{"name": "anthropic", "system": "PYPI", "category": "GATEWAY",
                        "capabilities": [], "significance": "vendor name", "stars": None,
                        "sql_log": []}], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraft(advisories=clean_advisories,
                                                       identity=squat_identity)))
    tool = out["tools"][0]
    assert tool["signals"]["identity"]["verdict"] == "RED"
    assert tool["verdict"] == "RED"


def test_gate_node_not_squat_when_widely_published():
    # A legit package with many versions in one ecosystem must NOT be flagged.
    out = asyncio.run(nodes.gate_node(
        {"tools": [{"name": "mlflow", "system": "PYPI", "category": "INFERENCE_SERVER",
                    "capabilities": [], "significance": "x", "stars": 15000, "sql_log": []}],
         "sql_log": []},
        FakeCraft(advisories={"columns": ["Title", "CVSS3Score", "GitHubSeverity"], "rows": []})))
    assert out["tools"][0]["signals"]["identity"]["verdict"] == "GREEN"


class FakeCraftShortAdvisoryRow:
    """Advisories query returns a malformed row with only 1 element."""
    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        if "advisor" in question.lower():
            return ({"columns": ["Title"], "rows": [["some advisory"]]}, "SELECT ... advisories")
        return _canned(question)


def test_gate_node_handles_short_advisory_row_without_crashing():
    state = {"tools": [{"name": "some-tool", "system": "PYPI", "category": "OTHER",
                        "capabilities": [], "significance": "misc tool",
                        "stars": 100, "sql_log": []}], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraftShortAdvisoryRow()))
    tool = out["tools"][0]
    assert "verdict" in tool
    assert tool["signals"]["cve"]["verdict"] == "GREEN"


class FakeCraftRaisesForTool:
    """Raises for one named tool's advisories call, succeeds for others."""
    def __init__(self, failing_name):
        self.failing_name = failing_name

    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        q = question.lower()
        if self.failing_name.lower() in q and "advisor" in q:
            raise RuntimeError("craft is down")
        if "advisor" in q:
            return ({"columns": ["Title", "CVSS3Score", "GitHubSeverity"], "rows": []},
                    "SELECT ... advisories")
        return _canned(question)


def test_gate_node_isolates_per_tool_errors():
    state = {"tools": [
        {"name": "broken-tool", "system": "PYPI", "category": "OTHER",
         "capabilities": [], "significance": "misc", "stars": 10, "sql_log": []},
        {"name": "ok-tool", "system": "PYPI", "category": "OTHER",
         "capabilities": [], "significance": "misc", "stars": 10, "sql_log": []},
    ], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraftRaisesForTool("broken-tool")))
    names = {t["name"] for t in out["tools"]}
    assert names == {"broken-tool", "ok-tool"}
    broken = next(t for t in out["tools"] if t["name"] == "broken-tool")
    assert broken["verdict"] == "YELLOW"
    ok = next(t for t in out["tools"] if t["name"] == "ok-tool")
    assert "verdict" in ok
    assert out["errors"]
    assert any("broken-tool" in e for e in out["errors"])


def test_discover_node_parses_name_and_stars_by_column():
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        return ({"columns": ["ProjectName", "ProjectType", "StarsCount", "ForksCount"],
                 "rows": [["significant-gravitas/autogpt", "GITHUB", 164209, 43000]]}, "SELECT discover")
    craft = type("C", (), {"nl_query": staticmethod(nl_query)})()
    out = asyncio.run(nodes.discover_candidates_node({"sql_log": []}, craft))
    assert out["candidates"][0]["name"] == "autogpt"      # split org/, not positional
    assert out["candidates"][0]["stars"] == 164209


from apps.ai_safety_check.graph import build_graph


class FakeLLM:
    def complete(self, prompt, json_mode=False):
        if "recurring supply-chain danger" in prompt:
            return '[{"pattern":"executes code","seen_in":["autogpt"],"remediation":"sandbox it"}]'
        if "triaging" in prompt.lower() or "classification" in prompt.lower():
            return '[{"name":"mlflow","category":"INFERENCE_SERVER","capabilities":["exposes_server"],"significance":"ml platform"}]'
        return "summary"


class FakeTavily:
    def search(self, q): return [{"title": "t", "url": "http://x", "content": "exploited"}]


def test_dangers_node_drops_non_dict_items():
    # Live Nemotron run returned a JSON array of strings — valid JSON, wrong
    # shape — which crashed report rendering. Only well-formed dicts may pass.
    class StringListLLM:
        def complete(self, prompt, json_mode=False):
            return ('["typosquatting", {"pattern": "executes code", '
                    '"seen_in": ["autogpt"], "remediation": "sandbox it"}, 42]')

    out = asyncio.run(nodes.dangers_node(
        {"tools": [{"name": "autogpt", "verdict": "RED",
                    "signals": {"cve": {"detail": "2 critical"}}}]},
        llm=StringListLLM()))
    assert out["dangers"] == [{"pattern": "executes code",
                               "seen_in": ["autogpt"],
                               "remediation": "sandbox it"}]


def test_dangers_node_skips_llm_when_nothing_graded():
    # An empty summary must not reach the LLM — it hallucinates filler
    # dangers ("ToolA", "ToolB") when given nothing to summarize.
    class ExplodingLLM:
        def complete(self, prompt, json_mode=False):
            raise AssertionError("LLM must not be called with no graded tools")

    out = asyncio.run(nodes.dangers_node({"tools": []}, llm=ExplodingLLM()))
    assert out["dangers"] == []


def test_discover_node_records_error_on_zero_candidates():
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        return ({"ok": False, "error": {"code": "boom"}}, "")
    craft = type("C", (), {"nl_query": staticmethod(nl_query)})()
    out = asyncio.run(nodes.discover_candidates_node({"sql_log": []}, craft))
    assert out["candidates"] == []
    assert any("discover returned 0 candidates" in e for e in out["errors"])


def test_graph_runs_end_to_end():
    craft = FakeCraft()

    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        if "most-starred" in question:
            return ({"columns": ["ProjectName", "ProjectType", "StarsCount"],
                     "rows": [["org/mlflow", "GITHUB", 15000]]}, "SELECT discover")
        return _canned(question)
    craft.nl_query = nl_query
    graph = build_graph(craft, FakeLLM(), FakeTavily())
    out = asyncio.run(graph.ainvoke({"sql_log": []}))
    assert out["tools"][0]["verdict"] == "RED"
    assert out["dangers"][0]["pattern"]
