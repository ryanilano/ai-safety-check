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
