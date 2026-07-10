"""Authenticated MCP session wrapper + response parsers.

The core data primitive is ask(): generate_sql -> execute_query -> get_result_page.
No SQL is authored here; generate_sql produces it and we only read it back.
"""
import contextlib
import json
from dataclasses import dataclass, field

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from . import config
from .craft_auth import build_oauth_provider


@dataclass
class QueryResult:
    question: str | None = None
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)

    @property
    def dicts(self) -> list[dict]:
        return [dict(zip(self.columns, r)) for r in self.rows]


class MCPResponseError(Exception):
    """The MCP server returned an unexpected/error shape (e.g. a transient upstream
    outage, or an {"ok": false, "error": ...} payload). Raised with a clear message so
    callers — and the LLM reading the tool result — can tell 'retry the server' apart
    from 'my request was wrong'."""


def _expect(resp: dict, *path, tool: str):
    """Walk `path` through nested dicts; raise MCPResponseError with the raw response if a
    key is missing (instead of a bare KeyError). Also surfaces explicit error payloads."""
    if isinstance(resp, dict) and resp.get("ok") is False:
        raise MCPResponseError(f"{tool}: server returned an error: {resp.get('error', resp)}")
    node = resp
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise MCPResponseError(
                f"{tool}: malformed response (missing '{key}'). "
                f"This is usually a transient server issue — retry. Raw: {resp!r:.400}"
            )
        node = node[key]
    return node


# --- pure parsers (unit-tested against real shapes) ---
def parse_generate_sql(resp: dict) -> str:
    return _expect(resp, "generate_sql", "sql", tool="generate_sql")


def parse_execute_query(resp: dict) -> str:
    body = resp.get("result", resp)  # tolerate an optional result wrapper
    return _expect(body, "execute_query", "artifact_fqn", tool="execute_query")


def parse_result_page(resp: dict) -> tuple[list[str], list[list[str]]]:
    body = resp.get("result", resp)  # tolerate an optional result wrapper, mirroring execute_query
    preview = _expect(body, "preview", tool="get_result_page")
    columns = _expect(preview, "columns", tool="get_result_page")
    rows = _expect(preview, "rows", tool="get_result_page")
    return columns, rows


def parse_plotly(resp: dict) -> dict:
    inner = _expect(resp, "generate_plotly_chart", "plotly_json", "plotly_json", tool="generate_plotly_chart")
    return {"data": inner.get("data", []), "layout": inner.get("layout", {})}


class CraftClient:
    def __init__(self):
        self._stack: contextlib.AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "CraftClient":
        auth = await build_oauth_provider()
        self._stack = contextlib.AsyncExitStack()
        try:
            read, write, _ = await self._stack.enter_async_context(
                streamablehttp_client(config.MCP_URL, auth=auth, headers=config.HEADERS)
            )
            self._session = await self._stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
        except BaseException:
            await self._stack.aclose()
            self._stack = None
            self._session = None
            raise
        return self

    async def __aexit__(self, *exc):
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def _call(self, tool: str, args: dict) -> dict:
        result = await self._session.call_tool(tool, args)
        text = result.content[0].text
        return json.loads(text)

    async def ask(self, question: str, *, max_rows: int = 500) -> QueryResult:
        gen = await self._call(
            "generate_sql",
            {
                "connection": config.CONNECTION_SLUG,
                "question": question,
                "schema": {"schema_name": config.SCHEMA_NAME, "schema_fqn": config.SCHEMA_FQN},
            },
        )
        sql = parse_generate_sql(gen)
        exe = await self._call(
            "execute_query",
            {"connection": config.CONNECTION_SLUG, "sql": sql, "max_rows": max_rows},
        )
        artifact = parse_execute_query(exe)
        page = await self._call(
            "get_result_page", {"artifact_fqn": artifact, "offset": 0, "limit": max_rows}
        )
        columns, rows = parse_result_page(page)
        return QueryResult(question=question, sql=sql, columns=columns, rows=rows)

    async def chart(self, chart_type: str, data: list[dict], options: dict) -> dict:
        resp = await self._call(
            "generate_plotly_chart",
            {"chart_type": chart_type, "data": data, "options": options},
        )
        return parse_plotly(resp)
