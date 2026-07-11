import importlib
import pytest


def _reload_config(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import apps.ai_safety_check.config as config
    return importlib.reload(config)


BASE_ENV = {
    "MCP_URL": "https://x/mcp", "PROJECT_ID": "pid", "KEYCLOAK_URL": "https://kc",
    "KEYCLOAK_REFRESH_TOKEN": "rt", "DEPS_CONNECTION": "deps", "GITHUB_CONNECTION": "gh",
    "NEBIUS_API_KEY": "nk",
}


def test_missing_required_var_raises(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    env = {k: v for k, v in BASE_ENV.items() if k != "NEBIUS_API_KEY"}
    with pytest.raises(RuntimeError, match="NEBIUS_API_KEY"):
        _reload_config(monkeypatch, **env)


def test_loads_and_derives_schema_fqn(monkeypatch):
    config = _reload_config(monkeypatch, **BASE_ENV)
    assert config.DEPS_SCHEMA_FQN == "deps.DEPS_DEV_V1.DEPS_DEV_V1"
    assert config.TAVILY_API_KEY == ""          # optional, defaults empty
    assert isinstance(config.CATEGORIES, dict)
    assert "AGENT" in config.CATEGORIES
