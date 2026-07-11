import os

_DEFAULTS = {
    "MCP_URL": "https://example/mcp", "PROJECT_ID": "test-project",
    "KEYCLOAK_URL": "https://example/keycloak", "KEYCLOAK_REFRESH_TOKEN": "test-token",
    "DEPS_CONNECTION": "deps-dev-v1-test", "GITHUB_CONNECTION": "github-repos-test",
    "NEBIUS_API_KEY": "test-key",
}
for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)
