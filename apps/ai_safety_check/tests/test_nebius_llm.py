import os

# config.py validates required env vars at import time — set fakes before
# importing nebius_llm (which imports config) if they aren't already present.
os.environ.setdefault("MCP_URL", "https://example.invalid/mcp")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("KEYCLOAK_URL", "https://example.invalid")
os.environ.setdefault("KEYCLOAK_REFRESH_TOKEN", "fake-refresh-token")
os.environ.setdefault("DEPS_CONNECTION", "deps_conn")
os.environ.setdefault("GITHUB_CONNECTION", "github_conn")
os.environ.setdefault("NEBIUS_API_KEY", "fake-nebius-key")

from apps.ai_safety_check.nebius_llm import NebiusLLM


class FakeCompletions:
    def __init__(self, text, sink):
        self.text, self.sink = text, sink

    def create(self, **kw):
        self.sink.append(kw)
        return type("Resp", (), {
            "choices": [type("Choice", (), {
                "message": type("Message", (), {"content": self.text})()
            })()]
        })()


class FakeChat:
    def __init__(self, text, sink):
        self.completions = FakeCompletions(text, sink)


class FakeClient:
    def __init__(self, text, sink):
        self.chat = FakeChat(text, sink)


def test_complete_returns_text():
    sink = []
    llm = NebiusLLM(client=FakeClient("hello", sink))
    assert llm.complete("hi") == "hello"
    assert sink[0]["model"]  # model passed through
