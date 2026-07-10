"""OAuth plumbing for the standalone MCP client.

em-runtime uses a statically pre-registered public client, so we pre-seed the
token storage with client_info to skip dynamic client registration. Tokens are
cached to disk so only the first run opens a browser.
"""
import asyncio
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)

from . import config


class FileTokenStorage(TokenStorage):
    def __init__(self, path: Path):
        self.path = path
        self._data = json.loads(path.read_text()) if path.exists() else {}

    async def get_tokens(self):
        t = self._data.get("tokens")
        return OAuthToken.model_validate(t) if t else None

    async def set_tokens(self, tokens: OAuthToken):
        self._data["tokens"] = tokens.model_dump(mode="json")
        self._save()

    async def get_client_info(self):
        c = self._data.get("client_info")
        return OAuthClientInformationFull.model_validate(c) if c else None

    async def set_client_info(self, client_info: OAuthClientInformationFull):
        self._data["client_info"] = client_info.model_dump(mode="json")
        self._save()

    def _save(self):
        self.path.write_text(json.dumps(self._data, indent=2))


async def _redirect_handler(url: str) -> None:
    print(f"Opening browser for authorization...\nIf it does not open, visit:\n{url}\n")
    webbrowser.open(url)


def _make_callback_handler(port: int):
    async def callback_handler():
        captured = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                q = parse_qs(urlparse(self.path).query)
                captured["code"] = q.get("code", [None])[0]
                captured["state"] = q.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h3>Authorization complete. You can close this tab.</h3>")

            def log_message(self, *args):
                pass

        server = HTTPServer(("localhost", port), Handler)
        await asyncio.get_event_loop().run_in_executor(None, server.handle_request)
        server.server_close()
        return captured.get("code"), captured.get("state")

    return callback_handler


def _redirect_uri() -> str:
    return f"http://localhost:{config.OAUTH_CALLBACK_PORT}/callback"


async def _ensure_static_client(storage: FileTokenStorage) -> None:
    if await storage.get_client_info() is None:
        await storage.set_client_info(
            OAuthClientInformationFull(
                client_id=config.OAUTH_CLIENT_ID,
                redirect_uris=[_redirect_uri()],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                token_endpoint_auth_method="none",
                scope=config.OAUTH_SCOPES,
            )
        )


async def build_oauth_provider() -> OAuthClientProvider:
    storage = FileTokenStorage(config.TOKEN_CACHE_PATH)
    await _ensure_static_client(storage)
    return OAuthClientProvider(
        server_url=config.MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="Seller Delivery Intelligence Agent",
            redirect_uris=[_redirect_uri()],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=config.OAUTH_SCOPES,
        ),
        storage=storage,
        redirect_handler=_redirect_handler,
        callback_handler=_make_callback_handler(config.OAUTH_CALLBACK_PORT),
    )
