# apps/ai_safety_check/config.py
"""Single source of truth. Read env here, nowhere else. Validated at import."""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key} (see .env.template)")
    return val


MCP_URL = _require("MCP_URL")
PROJECT_ID = _require("PROJECT_ID")
KEYCLOAK_URL = _require("KEYCLOAK_URL")
KEYCLOAK_REFRESH_TOKEN = _require("KEYCLOAK_REFRESH_TOKEN")

DEPS_CONNECTION = _require("DEPS_CONNECTION")
GITHUB_CONNECTION = _require("GITHUB_CONNECTION")

# schema_fqn = {connection}.{database}.{schema}; both dbs nest a same-named schema.
DEPS_SCHEMA_NAME = "DEPS_DEV_V1"
DEPS_SCHEMA_FQN = f"{DEPS_CONNECTION}.DEPS_DEV_V1.DEPS_DEV_V1"
GITHUB_SCHEMA_NAME = "GITHUB_REPOS"
GITHUB_SCHEMA_FQN = f"{GITHUB_CONNECTION}.GITHUB_REPOS.GITHUB_REPOS"

NEBIUS_API_KEY = _require("NEBIUS_API_KEY")
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

QUERY_MAX_ROWS = 200
MAX_TOOLS = 20

# Candidate seeds per category (starting point; the discover node also pulls data-driven).
CATEGORIES: dict[str, list[str]] = {
    "AGENT": ["autogpt", "auto-gpt", "agentgpt", "babyagi", "gpt-engineer"],
    "GATEWAY": ["openai", "litellm", "helicone"],
    "INFERENCE_SERVER": ["mlflow", "torchserve", "onnxruntime", "ollama", "gradio"],
    "ORCHESTRATION": ["langchain", "llama_index", "haystack"],
    "VECTOR_DB": ["chromadb", "qdrant-client", "pinecone-client", "weaviate-client"],
}

# Case studies pinned for a deterministic demo (chosen after a discovery run).
PINNED_CASES: list[str] = ["mlflow", "autogpt", "anthropic"]
