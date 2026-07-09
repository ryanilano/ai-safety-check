"""CRAFT MCP client — async wrapper over the Streamable HTTP transport.

Authentication:
  Tokens are fetched automatically via Keycloak refresh_token grant (no browser needed).
  The refresh token is cached on the instance and transparently renewed whenever a
  call returns 401 Unauthorized (one retry per call).

MCP Streamable HTTP protocol:
  POST /mcp
  Headers : Authorization: Bearer <token>, X-Project-ID: <id>
  Body    : JSON-RPC 2.0  { method: "tools/call", params: { name, arguments } }
  Response: SSE stream    data: { jsonrpc, id, result: { content: [{type, text}] } }

Transient network errors (timeout, connection reset) are retried with
exponential back-off via tenacity. Permanent errors (4xx other than 401,
tool-level errors) are raised immediately.
"""
import asyncio
import json
import logging
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    AGENT_MAX_RETRIES,
    CONNECTION,
    CRAFT_MCP_URL,
    CRAFT_PROJECT_ID,
    KEYCLOAK_REFRESH_TOKEN,
    KEYCLOAK_URL,
    QUERY_MAX_ROWS,
    SCHEMA,
)

log = logging.getLogger(__name__)

_KEYCLOAK_TOKEN_URL = (
    f"{KEYCLOAK_URL.rstrip('/')}/realms/hub/protocol/openid-connect/token"
)


def _log_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    log.warning(f"Retry attempt {retry_state.attempt_number} for MCP tool call: {exc}")


class CraftClient:
    def __init__(self) -> None:
        self._mcp_url    = CRAFT_MCP_URL
        self._project_id = CRAFT_PROJECT_ID
        self._bearer_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _fetch_keycloak_token(self) -> str:
        """Fetch a fresh access token via Keycloak refresh_token grant.

        The refresh token is obtained once via scripts/get_token.py (PKCE + Google SSO)
        and stored in KEYCLOAK_REFRESH_TOKEN. It is long-lived (days/weeks).
        """
        log.debug("Refreshing Keycloak access token")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _KEYCLOAK_TOKEN_URL,
                data={
                    "grant_type":    "refresh_token",
                    "client_id":     "em-runtime-mcp",
                    "refresh_token": KEYCLOAK_REFRESH_TOKEN,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Keycloak token refresh failed ({exc.response.status_code}): "
                f"{exc.response.text[:200]}\n"
                "Run 'uv run python scripts/get_token.py' to obtain a new refresh token."
            ) from exc
        self._bearer_token = resp.json()["access_token"]
        log.debug("Keycloak access token refreshed successfully")
        return self._bearer_token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._bearer_token}",
            "X-Project-ID":  self._project_id,
            "Content-Type":  "application/json",
            "Accept":        "application/json, text/event-stream",
        }

    # ── Core call ─────────────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        before_sleep=_log_retry,
        reraise=True,
    )
    async def call(self, tool: str, arguments: dict) -> Any:
        """Call any CRAFT MCP tool, auto-fetching/refreshing the token as needed."""
        if not self._bearer_token:
            await self._fetch_keycloak_token()

        log.debug(f"→ MCP tool call: {tool}")

        result = await self._send(tool, arguments)

        # Transparent token refresh on 401 — retry once
        if result == "_UNAUTHORIZED_":
            log.info("Bearer token expired — refreshing and retrying")
            await self._fetch_keycloak_token()
            result = await self._send(tool, arguments)
            if result == "_UNAUTHORIZED_":
                raise RuntimeError("CRAFT returned 401 after token refresh")

        log.debug(f"← MCP tool result: {tool} ok={isinstance(result, dict) and result.get('ok')}")
        return result

    async def _send(self, tool: str, arguments: dict) -> Any:
        """Send one MCP tool call and return the parsed result, or '_UNAUTHORIZED_'.

        MCP Streamable HTTP servers may respond with either:
          - Content-Type: application/json  → single JSON-RPC response body
          - Content-Type: text/event-stream → SSE stream of JSON-RPC events
        Both are handled here.
        """
        payload = {
            "jsonrpc": "2.0",
            "id":      id(arguments),
            "method":  "tools/call",
            "params":  {"name": tool, "arguments": arguments},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", self._mcp_url, headers=self._auth_headers(), json=payload
            ) as resp:
                if resp.status_code == 401:
                    return "_UNAUTHORIZED_"
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "")
                log.debug(f"  response status={resp.status_code} content-type={content_type!r}")

                if "text/event-stream" in content_type:
                    async for raw in resp.aiter_lines():
                        log.debug(f"  SSE line: {raw[:300]}")
                        if not raw.startswith("data: "):
                            continue
                        event = json.loads(raw[6:])
                        return self._extract_result(tool, event)
                else:
                    body = await resp.aread()
                    log.debug(f"  JSON body: {body[:500].decode(errors='replace')}")
                    event = json.loads(body)
                    return self._extract_result(tool, event)

        return None

    @staticmethod
    def _extract_result(tool: str, event: dict) -> Any:
        """Parse a JSON-RPC result or raise on error."""
        if "error" in event:
            raise RuntimeError(f"MCP tool '{tool}' returned error: {event['error']}")
        if "result" in event:
            content = event["result"].get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0]["text"]
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = text
                if not isinstance(parsed, dict):
                    log.warning(f"MCP tool '{tool}' returned non-dict response ({type(parsed).__name__}): {text[:200]}")
                    return {"ok": False, "error": {"code": "non_dict_response", "message": text}}
                return parsed
        return None

    # ── Named helpers (1-to-1 with CRAFT tool names) ──────────────────────────

    async def fetch_schema(self, fqn: str) -> dict:
        return await self.call("get_schema", {
            "connection":       CONNECTION,
            "fqn":              fqn,
            "include_children": True,
        })

    async def generate_sql(self, question: str) -> dict:
        """Translate a natural-language question to SQL via CRAFT Text2SQL.

        Retries on talk2data_unreachable with exponential backoff.
        """
        for attempt in range(1, AGENT_MAX_RETRIES + 2):
            result = await self.call("generate_sql", {
                "question":  question,
                "connection": CONNECTION,
                "schema":    SCHEMA,
            })
            if result and not result.get("ok"):
                error_code = (result.get("error") or {}).get("code", "")
                if error_code == "talk2data_unreachable" and attempt <= AGENT_MAX_RETRIES:
                    wait = 2 ** attempt
                    log.warning(
                        f"generate_sql: talk2data_unreachable (attempt {attempt}), "
                        f"retrying in {wait}s…"
                    )
                    await asyncio.sleep(wait)
                    continue
            return result
        return result

    async def execute_query(self, sql: str, max_rows: int = QUERY_MAX_ROWS) -> dict:
        """Execute SQL and return rows as a list of dicts.

        Internally calls execute_query MCP (gets artifact_fqn) then
        get_result_page MCP (fetches actual rows). Callers see only rows.
        """
        exec_resp = await self.call("execute_query", {
            "sql":        sql,
            "connection": CONNECTION,
            "max_rows":   max_rows,
        })

        if not exec_resp or not exec_resp.get("ok"):
            return exec_resp or {"ok": False}

        artifact_fqn = exec_resp.get("execute_query", {}).get("artifact_fqn")
        row_count    = exec_resp.get("execute_query", {}).get("row_count", 0)

        log.debug(f"execute_query artifact_fqn={artifact_fqn!r}  row_count={row_count}")

        if not artifact_fqn or row_count == 0:
            return {"ok": True, "rows": [], "columns": []}

        page_resp = await self.call("get_result_page", {
            "artifact_fqn": artifact_fqn,
            "offset":       0,
            "limit":        max_rows,
        })

        log.debug(
            f"get_result_page response keys: "
            f"{list(page_resp.keys()) if isinstance(page_resp, dict) else type(page_resp)}"
        )

        if isinstance(page_resp, dict):
            preview  = page_resp.get("preview", {})
            columns  = preview.get("columns", [])
            raw_rows = preview.get("rows", [])
            if raw_rows:
                row_dicts = [dict(zip(columns, row)) for row in raw_rows]
                log.debug(f"Converted {len(row_dicts)} rows using columns {columns}")
                return {"ok": True, "rows": row_dicts, "columns": columns}

        return {"ok": True, "rows": [], "columns": []}

    async def generate_plotly_chart(
        self,
        data: list[dict],
        chart_type: str,
        options: dict | None = None,
    ) -> dict:
        return await self.call("generate_plotly_chart", {
            "data":       data,
            "chart_type": chart_type,
            "options":    options,
        })
