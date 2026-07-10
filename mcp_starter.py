# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "mcp==1.26.0",
# ]
# ///
"""Starter example: talk to the em-runtime MCP server from your own Python.

This is a hand-off template for hackathon participants. It shows the *whole*
round-trip against the em-runtime MCP endpoint:

    1. authenticate  (OAuth 2.1 + PKCE / Keycloak SSO — browser opens once)
    2. list_tools    (discover what the server can do)
    3. discover a data connection + schema
    4. generate_sql  (natural language -> SQL)
    5. execute_query (run the SQL, get rows back)

Run it with `uv` — no venv or `pip install` needed, the header above pulls the
one dependency automatically:

    uv run scripts/mcp_starter.py

On the *first* run a browser tab opens for SSO login; the token is cached under
~/.cache/em-talk2data/ so every later run is silent. Force a fresh login with:

    uv run scripts/mcp_starter.py --reset-auth

To just see the raw tool catalogue (names + JSON input schemas) and stop:

    uv run scripts/mcp_starter.py --list-tools

------------------------------------------------------------------------------
 EVERYTHING you normally need to change lives in the CONFIG block right below.
 The OAuth plumbing further down is boilerplate — you can leave it untouched.
------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

# ============================================================================
#  CONFIG — edit these for your environment / question
# ============================================================================

# Which cluster's MCP endpoint to hit, and which project you're scoped to.
# Ask your host for the right PROJECT_ID (it changes when a cluster is recreated;
# `scripts/mcp_setup.sh` prints it for local clusters).
MCP_URL: str = "https://nebius.emergence.ai/mcp"
PROJECT_ID: str = "<Your Project Id>"

# The natural-language question you want turned into SQL.
QUESTION: str = "How many rows are in the largest table?"

# A data connection ("slug") and the schema to run against. If you don't know
# these yet, run once with --list-tools, then call `list_data_connections` and
# `get_schema` (see discover_connection_and_schema() below) to find valid values.
CONNECTION: str = "eval-thelook-ecommerce"
SCHEMA_NAME: str = "THELOOK_ECOMMERCE"
# The FQN scopes generate_sql. A 2-segment "{connection}.{DB}" FQN lets the agent
# see every schema in that database — usually what you want.
SCHEMA_FQN: str = f"{CONNECTION}.{SCHEMA_NAME}"

# ============================================================================
#  MAIN FLOW — the interesting part. Read top to bottom.
# ============================================================================


async def discover_connection_and_schema(session: ClientSession) -> None:
    """Print the available data connections so you can pick a CONNECTION slug.

    Not required for generate_sql if you already know your connection + schema,
    but handy the first time you point this script at a new project. Comment the
    call to this out once you've filled in the CONFIG block above.
    """
    print("=== available data connections ===")
    result = await session.call_tool("list_data_connections", {})
    print(_render_content(result.content))
    print()


async def run_generate_sql(session: ClientSession, question: str) -> str | None:
    """Ask the Text2SQL agent to turn `question` into SQL. Returns the SQL text."""
    print(f"=== generate_sql ===\nquestion: {question}\n")
    arguments: dict[str, object] = {
        "question": question,
        "connection": CONNECTION,
        "schema": {"schema_name": SCHEMA_NAME, "schema_fqn": SCHEMA_FQN},
    }
    result = await session.call_tool("generate_sql", arguments)
    if result.isError:
        print("[generate_sql failed]", file=sys.stderr)
        print(_render_content(result.content), file=sys.stderr)
        return None

    # generate_sql returns structured JSON: {"ok": true, "generate_sql": {"sql": ...}}
    structured: dict[str, object] | None = result.structuredContent
    print("--- raw structured response ---")
    print(json.dumps(structured, indent=2, default=str))

    sql: str | None = _extract_sql(structured)
    if sql:
        print(f"\n--- generated SQL ---\n{sql}\n")
    return sql


async def run_execute_query(session: ClientSession, sql: str) -> None:
    """Run the generated SQL read-only and print whatever rows come back."""
    print("=== execute_query ===")
    arguments: dict[str, object] = {"connection": CONNECTION, "sql": sql}
    result = await session.call_tool("execute_query", arguments)
    if result.isError:
        print("[execute_query failed]", file=sys.stderr)
        print(_render_content(result.content), file=sys.stderr)
        return
    print("--- rows ---")
    print(json.dumps(result.structuredContent, indent=2, default=str))


async def main_flow(question: str, list_tools_only: bool) -> None:
    """Open one authenticated MCP session and drive the tools in sequence."""
    provider: OAuthClientProvider = _build_provider()
    # Every request MUST carry the project header — the server rejects calls without it.
    headers: dict[str, str] = {"X-Project-ID": PROJECT_ID}

    async with streamablehttp_client(MCP_URL, auth=provider, headers=headers) as (
        read_stream,
        write_stream,
        _get_session_id,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # --list-tools: dump the catalogue and stop. Great for exploring.
            if list_tools_only:
                tools = await session.list_tools()
                for tool_def in tools.tools:
                    print(f"\n=== {tool_def.name} ===")
                    print(tool_def.description or "(no description)")
                    print(json.dumps(tool_def.inputSchema, indent=2))
                return

            # Uncomment the next line the first time you target a new project to
            # discover valid CONNECTION slugs, then fill in the CONFIG block.
            # await discover_connection_and_schema(session)

            sql: str | None = await run_generate_sql(session, question)
            if sql:
                await run_execute_query(session, sql)


# ============================================================================
#  OAuth plumbing + helpers — boilerplate. You can leave everything below as-is.
# ============================================================================

OAUTH_CLIENT_ID: str = "em-runtime-mcp"
OAUTH_SCOPES: str = "openid profile email organization"
CALLBACK_PORT: int = 9876
CALLBACK_PATH: str = "/callback"
TOKEN_CACHE: Path = Path.home() / ".cache" / "em-talk2data" / "mcp-starter.json"


class FileTokenStorage(TokenStorage):
    """Persists OAuth tokens to a 0600 JSON file and pre-seeds the fixed client.

    em-runtime registers `em-runtime-mcp` as a fixed public client, so dynamic
    client registration is skipped — `get_client_info` always returns the
    pre-seeded client instead.
    """

    def __init__(self, cache_path: Path, client_metadata: OAuthClientMetadata) -> None:
        self._cache_path: Path = cache_path
        self._client_metadata: OAuthClientMetadata = client_metadata

    async def get_tokens(self) -> OAuthToken | None:
        if not self._cache_path.exists():
            return None
        return OAuthToken.model_validate_json(self._cache_path.read_text())

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(tokens.model_dump_json())
        self._cache_path.chmod(0o600)

    async def get_client_info(self) -> OAuthClientInformationFull:
        return OAuthClientInformationFull(
            client_id=OAUTH_CLIENT_ID,
            redirect_uris=self._client_metadata.redirect_uris,
            token_endpoint_auth_method="none",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=self._client_metadata.scope,
        )

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        # Fixed public client — nothing to persist.
        return None


async def _open_browser_for_login(authorization_url: str) -> None:
    print(f"\nOpening browser for SSO login:\n  {authorization_url}\n", file=sys.stderr)
    print("If no browser opens, copy the URL above into one manually.", file=sys.stderr)
    webbrowser.open(authorization_url)


async def _wait_for_callback() -> tuple[str, str | None]:
    """Run a one-shot local HTTP server to catch the Keycloak redirect."""
    captured: dict[str, str] = {}
    done: threading.Event = threading.Event()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            query: dict[str, list[str]] = parse_qs(urlparse(self.path).query)
            if "code" in query:
                captured["code"] = query["code"][0]
                captured["state"] = query.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body>Login complete. Return to your terminal.</body></html>")
            done.set()

        def log_message(self, *_args: object) -> None:
            return None

    server: HTTPServer = HTTPServer(("localhost", CALLBACK_PORT), _Handler)
    thread: threading.Thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        await asyncio.to_thread(done.wait)
    finally:
        server.shutdown()

    if "code" not in captured:
        raise RuntimeError("OAuth callback did not include an authorization code")
    state: str = captured["state"]
    return captured["code"], (state if state else None)


def _build_provider() -> OAuthClientProvider:
    client_metadata: OAuthClientMetadata = OAuthClientMetadata(
        client_name="em-talk2data MCP starter",
        redirect_uris=[f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
        scope=OAUTH_SCOPES,
    )
    return OAuthClientProvider(
        server_url=MCP_URL,
        client_metadata=client_metadata,
        storage=FileTokenStorage(TOKEN_CACHE, client_metadata),
        redirect_handler=_open_browser_for_login,
        callback_handler=_wait_for_callback,
    )


def _render_content(content: object) -> str:
    """Flatten a CallToolResult content list into readable text."""
    parts: list[str] = []
    for item in content:  # type: ignore[assignment]
        text: str | None = getattr(item, "text", None)
        parts.append(text if text is not None else repr(item))
    return "\n".join(parts)


def _extract_sql(structured: dict[str, object] | None) -> str | None:
    """Pull the SQL string out of a generate_sql structuredContent payload."""
    if not structured or not structured.get("ok"):
        return None
    payload: object = structured.get("generate_sql")
    if not isinstance(payload, dict):
        return None
    sql: object = payload.get("sql")
    return sql if isinstance(sql, str) and sql.strip() else None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--question",
        default=QUESTION,
        help="Natural-language question to turn into SQL.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all available MCP tools and their input schemas, then exit.",
    )
    parser.add_argument(
        "--reset-auth",
        action="store_true",
        help="Delete the cached token before running to force a fresh browser login.",
    )
    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = _parse_args()
    if args.reset_auth and TOKEN_CACHE.exists():
        TOKEN_CACHE.unlink()
        print(f"Cleared cached token at {TOKEN_CACHE}", file=sys.stderr)

    asyncio.run(main_flow(args.question, args.list_tools))


if __name__ == "__main__":
    main()
