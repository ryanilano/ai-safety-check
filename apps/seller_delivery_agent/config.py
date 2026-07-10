"""Static configuration for the Seller Delivery Intelligence Agent."""
from pathlib import Path

# --- MCP server ---
MCP_URL = "https://runtime.dev.emergence.ai/mcp"
PROJECT_ID = "edb5c0bf-5407-4d88-b577-9f43ab53fe59"
HEADERS = {"X-Project-ID": PROJECT_ID}

# --- Data connection ---
CONNECTION_SLUG = "eval-brazilian-e-commerce"
DATABASE = "BRAZILIAN_E_COMMERCE"
SCHEMA = "BRAZILIAN_E_COMMERCE"
SCHEMA_NAME = "BRAZILIAN_E_COMMERCE"
# 3-part schema catalog FQN (connection-slug.database.schema) — used ONLY for
# the generate_sql `schema` argument. Verified live.
SCHEMA_FQN = "eval-brazilian-e-commerce.BRAZILIAN_E_COMMERCE.BRAZILIAN_E_COMMERCE"

# --- OAuth (static pre-registered client) ---
OAUTH_CLIENT_ID = "em-runtime-mcp"
OAUTH_METADATA_URL = (
    "https://runtime.dev.emergence.ai/keycloak/realms/hub/.well-known/openid-configuration"
)
OAUTH_CALLBACK_PORT = 9876
OAUTH_SCOPES = "openid profile email organization"
TOKEN_CACHE_PATH = Path(__file__).parent / ".token_cache.json"

# --- Demo default ---
# Verified high-volume seller: 1,854 orders; on-time 4.00* vs late 2.54*.
DEFAULT_SELLER_ID = "6560211a19b47992c3666cc44a7e94c0"

# Known high-volume sellers for the UI dropdown (verified order counts).
DEMO_SELLERS = [
    "6560211a19b47992c3666cc44a7e94c0",  # 1854 orders
    "4a3ca9315b744ce9f8e9374361493884",  # 1806 orders
    "cc419e0650a3c5ba77189a1882b7556a",  # 1706 orders
    "1f50f920176fa81dab994f9023523100",  # 1404 orders
]


def qualified(table: str) -> str:
    """Return a fully-qualified, double-quoted 3-part table name for SQL."""
    return f'"{DATABASE}"."{SCHEMA}"."{table}"'
