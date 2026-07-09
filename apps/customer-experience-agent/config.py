"""Configuration — all environment variables are read here and nowhere else.

Required vars raise immediately at import time so the process fails on boot
with a clear message rather than mid-workflow. See .env.template.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Return the value of an env var or raise with a clear message."""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. See .env.template."
        )
    return value


# ── CRAFT MCP Server ──────────────────────────────────────────────────────────
CRAFT_MCP_URL    = _require("MCP_URL")
CRAFT_PROJECT_ID = _require("PROJECT_ID")

# ── Keycloak auth (refresh token flow — run scripts/get_token.py once) ────────
KEYCLOAK_URL           = _require("KEYCLOAK_URL")
KEYCLOAK_REFRESH_TOKEN = _require("KEYCLOAK_REFRESH_TOKEN")

# ── TheLook E-Commerce Database ───────────────────────────────────────────────
# RESOURCE_URI format: "data:<datasource-uuid>:<project-uuid>:<connection-name>"
# generate_sql requires schema_fqn as exactly 3 dot-segments: datasource.database.schema
_datasource_id = _require("DATASOURCE_ID")
_connection    = _require("CONNECTION_NAME")

RESOURCE_URI = f"data:{_datasource_id}:{CRAFT_PROJECT_ID}:{_connection}"
SCHEMA = {
    "schema_name": _require("SCHEMA_NAME"),
    "schema_fqn":  _require("SCHEMA_FQN"),
}
SCHEMA_FQN = SCHEMA["schema_fqn"]
CONNECTION = _connection

# ── LLM ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = _require("GEMINI_API_KEY")

# Model names — change here if Google renames preview models
GEMINI_FLASH_MODEL = os.environ.get("GEMINI_FLASH_MODEL") or "gemini-3.1-flash-lite"
GEMINI_PRO_MODEL   = os.environ.get("GEMINI_PRO_MODEL")   or "gemini-3-pro-preview"

# Node 5 (compose_engagement) synthesis model
GEMINI_SYNTHESIS_MODEL = GEMINI_FLASH_MODEL

# ── Agent control ─────────────────────────────────────────────────────────────
AGENT_MAX_RETRIES = 2
QUERY_MAX_ROWS    = 200
