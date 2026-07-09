"""One-time script to obtain a Keycloak refresh token via PKCE + Google SSO.

Run once:
    uv run python scripts/get_token.py

A browser tab opens → sign in with Google → the script prints:

    KEYCLOAK_REFRESH_TOKEN=eyJ...

Paste that value into your .env file. The refresh token is long-lived
(days/weeks); craft_client.py will silently renew access tokens using it.
"""
import asyncio
import base64
import hashlib
import http.server
import os
import secrets
import urllib.parse

import httpx

_keycloak_url  = os.environ.get("KEYCLOAK_URL") or input("KEYCLOAK_URL (base URL, no /realms suffix): ").strip()
KEYCLOAK_BASE  = f"{_keycloak_url.rstrip('/')}/realms/hub"
CLIENT_ID      = "em-runtime-mcp"
REDIRECT_URI   = "http://localhost:9876/callback"
SCOPE          = "openid profile email organization offline_access"


def _build_pkce() -> tuple[str, str]:
    verifier  = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _wait_for_code(port: int) -> str:
    """Spin up a one-shot localhost server and capture the auth code."""
    code: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code.append(qs.get("code", [""])[0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authenticated! You can close this tab.")

        def log_message(self, *_: object) -> None:
            pass

    with http.server.HTTPServer(("localhost", port), Handler) as srv:
        srv.handle_request()

    return code[0]


async def main() -> None:
    verifier, challenge = _build_pkce()

    auth_url = (
        f"{KEYCLOAK_BASE}/protocol/openid-connect/auth?"
        + urllib.parse.urlencode({
            "response_type":         "code",
            "client_id":             CLIENT_ID,
            "redirect_uri":          REDIRECT_URI,
            "scope":                 SCOPE,
            "code_challenge":        challenge,
            "code_challenge_method": "S256",
        })
    )

    print("\nOpening browser for Google SSO login…")
    print(f"If it does not open, visit:\n  {auth_url}\n")

    import webbrowser
    webbrowser.open(auth_url)

    code = _wait_for_code(9876)
    if not code:
        print("ERROR: no auth code received")
        return

    token_url = f"{KEYCLOAK_BASE}/protocol/openid-connect/token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type":    "authorization_code",
                "client_id":     CLIENT_ID,
                "code":          code,
                "redirect_uri":  REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
    resp.raise_for_status()
    tokens = resp.json()

    refresh_token = tokens.get("refresh_token", "")
    access_token  = tokens.get("access_token",  "")

    print("\n✓ Authentication successful!\n")
    print("Add this line to your .env file:")
    print(f"\nKEYCLOAK_REFRESH_TOKEN={refresh_token}\n")

    if not refresh_token:
        print(
            "WARNING: no refresh_token returned.\n"
            "The server did not grant the offline_access scope.\n"
            "Re-run this script after confirming your Keycloak client has offline_access enabled.\n"
            "Do NOT use a short-lived access token as a substitute for a refresh token."
        )


if __name__ == "__main__":
    asyncio.run(main())
