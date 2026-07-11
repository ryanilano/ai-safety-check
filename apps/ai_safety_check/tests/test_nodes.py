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


class FakeCraft:
    """Returns canned rows per NL question substring."""
    def __init__(self): self.sql_log = []
    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        q = question.lower()
        if "advisor" in q:
            return ({"columns": ["Title", "CVSS3Score", "GitHubSeverity"],
                     "rows": [["path traversal", 10.0, "CRITICAL"],
                              ["arbitrary code execution", 10.0, "CRITICAL"]]}, "SELECT ... advisories")
        if "dependents" in q:
            return ({"columns": ["c"], "rows": [[1500]]}, "SELECT count dependents")
        if "upstreampublishedat" in q:
            return ({"columns": ["d", "v"], "rows": [["2023-07-17T00:00:00", 78]]}, "SELECT staleness")
        if "projects" in q:
            return ({"columns": ["StarsCount", "ForksCount", "OpenIssuesCount", "Licenses"],
                     "rows": [[15000, 3000, 700, "Apache-2.0"]]}, "SELECT health")
        return ({"columns": ["System", "v"], "rows": [["PYPI", 78]]}, "SELECT identity")


def test_gate_node_reds_out_mlflow():
    state = {"tools": [{"name": "mlflow", "system": "PYPI", "category": "INFERENCE_SERVER",
                        "capabilities": ["exposes_server", "filesystem"], "significance": "ml platform",
                        "stars": 15000, "sql_log": []}], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraft()))
    tool = out["tools"][0]
    assert tool["verdict"] == "RED"          # 2 CVSS-10 criticals
    assert tool["signals"]["cve"]["verdict"] == "RED"
    assert any(lbl.startswith("advisories") for lbl, _ in tool["sql_log"])


class FakeCraftShortAdvisoryRow:
    """Advisories query returns a malformed row with only 1 element."""
    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        q = question.lower()
        if "advisor" in q:
            return ({"columns": ["Title"], "rows": [["some advisory"]]}, "SELECT ... advisories")
        if "dependents" in q:
            return ({"columns": ["c"], "rows": [[1500]]}, "SELECT count dependents")
        if "upstreampublishedat" in q:
            return ({"columns": ["d", "v"], "rows": [["2023-07-17T00:00:00", 78]]}, "SELECT staleness")
        if "projects" in q:
            return ({"columns": ["StarsCount", "ForksCount", "OpenIssuesCount", "Licenses"],
                     "rows": [[15000, 3000, 700, "Apache-2.0"]]}, "SELECT health")
        return ({"columns": ["System", "v"], "rows": [["PYPI", 78]]}, "SELECT identity")


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
        if "dependents" in q:
            return ({"columns": ["c"], "rows": [[1]]}, "SELECT count dependents")
        if "upstreampublishedat" in q:
            return ({"columns": ["d", "v"], "rows": [["2023-07-17T00:00:00", 78]]}, "SELECT staleness")
        if "projects" in q:
            return ({"columns": ["StarsCount", "ForksCount", "OpenIssuesCount", "Licenses"],
                     "rows": [[15000, 3000, 700, "Apache-2.0"]]}, "SELECT health")
        return ({"columns": ["System", "v"], "rows": [["PYPI", 78]]}, "SELECT identity")


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


def test_graph_runs_end_to_end():
    craft = FakeCraft()
    # discover returns one project row:
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        if "most-starred" in question:
            return ({"columns": ["ProjectName", "ProjectType", "StarsCount"],
                     "rows": [["org/mlflow", "GITHUB", 15000]]}, "SELECT discover")
        return await FakeCraft().nl_query(question, connection, schema_name, schema_fqn, max_rows)
    craft.nl_query = nl_query
    graph = build_graph(craft, FakeLLM(), FakeTavily())
    out = asyncio.run(graph.ainvoke({"sql_log": []}))
    assert out["tools"][0]["verdict"] == "RED"
    assert out["dangers"][0]["pattern"]
