# LLM / AI Safety Check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit app that discovers the top AI/LLM tools in the CRAFT Scenario-5 snapshot, classifies them with an LLM, gates each into a 🔴/🟡/🟢 safety verdict from data-backed signals, validates verdicts against post-2023 reality via Tavily, and renders a nutrition-label leaderboard + case studies + Common Dangers + a live NL ask-box.

**Architecture:** A LangGraph fixed pipeline cloning `apps/customer-experience-agent/` (hand-rolled `CraftClient` over MCP JSON-RPC + Keycloak refresh-token auth, config validated at import, `functools.partial`-bound nodes, `runs/<ts>/` artifact trail). The reasoning LLM is Nebius Token Factory (OpenAI-compatible) swapped in where the customer agent used Gemini. A Streamlit UI clones `apps/seller_delivery_agent/app.py` patterns and renders from a cached run by default.

**Tech Stack:** Python 3.12, `uv`, LangGraph 1.2.6, `httpx` 0.28.1, `openai` (OpenAI-compatible client for Nebius), `tenacity` 9.1.4, `plotly` 6.8.0 + `kaleido`, `streamlit`, `pytest` + `pytest-asyncio`, `python-dotenv`.

## Global Constraints

- **Python:** `requires-python = "==3.12.*"` (match customer-agent).
- **Package manager:** `uv` (this app), run from repo root.
- **Import convention:** package code uses **relative** imports (`from . import config`); tests and `app.py` use **absolute** `apps.ai_safety_check.*` imports. App dir is a Python package importable as `apps.ai_safety_check` — directory name uses an underscore, not a hyphen, so it is importable.
- **Tests run from repo root:** `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/ -q` (or `uv run pytest ...`). No network in unit tests — hand-rolled fakes + `monkeypatch` only (no mocking library).
- **CRAFT connections (exact slugs):** `deps-dev-v1-cb6bf32f` (advisories/packages/dependents) and `github-repos-cb6bf32f` (repo metadata). Project id: `cb6bf32f-f77a-4092-93d4-ca5762a4ebfe`. Cluster: `https://nebius.emergence.ai/mcp`.
- **`generate_sql` schema arg:** every call passes `{"schema_name": ..., "schema_fqn": ...}`; `schema_fqn` is exactly 3 dot-segments `{connection_slug}.{database}.{schema}` — for deps.dev that is `deps-dev-v1-cb6bf32f.DEPS_DEV_V1.DEPS_DEV_V1`.
- **Severity column:** use `GitHubSeverity` in `ADVISORIES`, never `Severity` (all `UNKNOWN`).
- **Rate limits:** query execution 10/min, metadata 30/min per key — pipeline batches; demo renders from cache.
- **Secrets:** `NEBIUS_API_KEY`, `TAVILY_API_KEY`, `KEYCLOAK_REFRESH_TOKEN` come from env/`.env`, never committed. `.env` is gitignored.
- **Verdict vocabulary:** 🔴 RED / 🟡 YELLOW / 🟢 GREEN, worst-signal-wins.
- **Spec:** `docs/superpowers/specs/2026-07-11-ai-supply-chain-grader-design.md` is the source of truth for behavior.

---

## File Structure

```
apps/ai_safety_check/
├── __init__.py            # empty; makes it a package
├── pyproject.toml         # uv project, deps
├── .env.template          # documents required env vars
├── .gitignore             # .env, runs/
├── config.py              # env-validated-at-import; connections, LLM, thresholds, categories, pinned cases
├── craft_client.py        # MCP JSON-RPC client + Keycloak refresh-token auth (adapted from customer-agent)
├── nebius_llm.py          # OpenAI-compatible Nebius Token Factory client wrapper
├── tavily_client.py       # hindsight web lookups; graceful no-op without key
├── queries.py             # parameterized natural-language CRAFT questions
├── gating.py              # PURE: signals -> per-signal verdict -> worst-wins composite
├── classify.py            # PURE parsing of LLM classification output (dedup, category, capability, significance)
├── state.py               # SafetyCheckState TypedDict
├── nodes.py               # async pipeline nodes (state, deps) -> dict
├── graph.py               # build_graph(craft, llm, tavily) -> compiled StateGraph
├── report.py              # PURE: build markdown + plotly leaderboard figure from final state
├── main.py                # CLI entry: run pipeline, write runs/<ts>/ artifacts
├── app.py                 # Streamlit UI (cached render + re-run + ask-box)
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_craft_client.py
    ├── test_nebius_llm.py
    ├── test_tavily_client.py
    ├── test_queries.py
    ├── test_gating.py
    ├── test_classify.py
    ├── test_nodes.py
    ├── test_report.py
    ├── test_main.py
    └── test_app_renders.py
```

**Data-type contracts** (used across tasks; defined once here, referenced by name):

```python
# A signal verdict is one of these exact strings:
Verdict = str  # "RED" | "YELLOW" | "GREEN"

# Per-tool signal results produced by gating.py:
# {
#   "cve":        {"verdict": Verdict, "detail": str, "worst_cvss": float | None, "counts": {"CRITICAL": int, "HIGH": int, "MODERATE": int}},
#   "capability": {"verdict": Verdict, "detail": str, "flags": list[str]},           # flags subset of {"executes_code","exposes_server","filesystem"}
#   "staleness":  {"verdict": Verdict, "detail": str, "days_since_last_release": int | None},
#   "blast":      {"verdict": Verdict, "detail": str, "dependent_count": int | None},
#   "health":     {"verdict": Verdict, "detail": str, "stars": int | None, "open_issues": int | None, "has_repo": bool},
#   "identity":   {"verdict": Verdict, "detail": str, "suspected_squat": bool},
# }
#
# A "tool" dict flowing through the pipeline:
# {
#   "name": str, "system": str,               # e.g. "mlflow", "PYPI"
#   "category": str,                            # "AGENT"|"GATEWAY"|"INFERENCE_SERVER"|"ORCHESTRATION"|"VECTOR_DB"|"TUTORIAL"|"FALSE_POSITIVE"
#   "significance": str,                        # one-line blurb
#   "capabilities": list[str],
#   "stars": int | None,
#   "signals": dict,                            # the per-signal dict above
#   "verdict": Verdict,                         # overall, worst-wins
#   "hindsight": {"tag": str, "source_url": str | None} | None,
#   "sql_log": list[tuple[str, str]],           # (label, sql) audit trail
# }
```

---

## Task 1: Scaffold package + config with import-time validation

**Files:**
- Create: `apps/ai_safety_check/__init__.py` (empty)
- Create: `apps/ai_safety_check/tests/__init__.py` (empty)
- Create: `apps/ai_safety_check/pyproject.toml`
- Create: `apps/ai_safety_check/.env.template`
- Create: `apps/ai_safety_check/.gitignore`
- Create: `apps/ai_safety_check/config.py`
- Test: `apps/ai_safety_check/tests/test_config.py`

**Interfaces:**
- Produces: `config` module exposing constants `MCP_URL`, `PROJECT_ID`, `KEYCLOAK_URL`, `KEYCLOAK_REFRESH_TOKEN`, `DEPS_CONNECTION`, `GITHUB_CONNECTION`, `DEPS_SCHEMA_NAME`, `DEPS_SCHEMA_FQN`, `GITHUB_SCHEMA_NAME`, `GITHUB_SCHEMA_FQN`, `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, `TAVILY_API_KEY` (may be `""`), `QUERY_MAX_ROWS: int`, `CATEGORIES: dict[str, list[str]]`, `PINNED_CASES: list[str]`, `MAX_TOOLS: int`, and helper `_require(key: str) -> str`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "ai-safety-check"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
    "langgraph==1.2.6",
    "httpx==0.28.1",
    "openai>=1.40",
    "tenacity==9.1.4",
    "plotly==6.8.0",
    "kaleido==0.2.1",
    "streamlit>=1.36",
    "python-dotenv==1.2.2",
    "rich==15.0.0",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `.env.template` and `.gitignore`**

`.env.template`:
```
# CRAFT MCP (nebius cluster)
MCP_URL=https://nebius.emergence.ai/mcp
PROJECT_ID=cb6bf32f-f77a-4092-93d4-ca5762a4ebfe
KEYCLOAK_URL=https://runtime.prod.emergence.ai/keycloak
KEYCLOAK_REFRESH_TOKEN=

# Connections
DEPS_CONNECTION=deps-dev-v1-cb6bf32f
GITHUB_CONNECTION=github-repos-cb6bf32f

# Nebius Token Factory (OpenAI-compatible reasoning LLM)
NEBIUS_API_KEY=
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b

# Optional hindsight web search
TAVILY_API_KEY=
```

`.gitignore`:
```
.env
.venv/
runs/
__pycache__/
```

- [ ] **Step 2b: Create the app virtualenv (Python 3.12) and install deps**

The repo-root `.venv` is Python 3.11 and lacks langgraph/openai — do NOT use it. Create a dedicated 3.12 venv for this app with `uv`, from the repo root:

```bash
uv venv --python 3.12 apps/ai_safety_check/.venv
uv pip install --python apps/ai_safety_check/.venv \
  langgraph==1.2.6 httpx==0.28.1 "openai>=1.40" tenacity==9.1.4 \
  plotly==6.8.0 kaleido==0.2.1 "streamlit>=1.36" python-dotenv==1.2.2 \
  rich==15.0.0 pytest pytest-asyncio
```

All test commands in this plan use `apps/ai_safety_check/.venv/bin/python -m pytest ...` run **from the repo root** (so `apps.ai_safety_check.*` absolute imports resolve — the repo root lands on `sys.path` under `python -m`). This app's `.venv` is gitignored.

- [ ] **Step 3: Write the failing test**

```python
# apps/ai_safety_check/tests/test_config.py
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` / `RuntimeError` not raised (config.py not written yet).

- [ ] **Step 5: Write `config.py`**

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add apps/ai_safety_check/__init__.py apps/ai_safety_check/tests/__init__.py \
  apps/ai_safety_check/pyproject.toml apps/ai_safety_check/.env.template \
  apps/ai_safety_check/.gitignore apps/ai_safety_check/config.py \
  apps/ai_safety_check/tests/test_config.py
git commit -m "feat(safety-check): scaffold package + validated config"
```

---

## Task 2: `gating.py` — the pure safety-verdict core

This is the crown jewel of testability: pure functions, no network, exhaustive unit tests. Build it early so every downstream node has a trustworthy scorer.

**Files:**
- Create: `apps/ai_safety_check/gating.py`
- Test: `apps/ai_safety_check/tests/test_gating.py`

**Interfaces:**
- Produces:
  - `grade_cve(counts: dict, worst_cvss: float | None) -> dict` — counts keyed CRITICAL/HIGH/MODERATE.
  - `grade_capability(flags: list[str], has_cve: bool) -> dict`
  - `grade_staleness(days_since_last_release: int | None) -> dict`
  - `grade_blast(dependent_count: int | None) -> dict`
  - `grade_health(stars: int | None, open_issues: int | None, has_repo: bool) -> dict`
  - `grade_identity(suspected_squat: bool) -> dict`
  - `composite(signals: dict) -> str` — returns "RED"|"YELLOW"|"GREEN", worst-wins.
  - Each `grade_*` returns `{"verdict": str, "detail": str, ...signal-specific keys...}` matching the contract in File Structure.

- [ ] **Step 1: Write the failing tests**

```python
# apps/ai_safety_check/tests/test_gating.py
from apps.ai_safety_check import gating


def test_cve_critical_is_red():
    r = gating.grade_cve({"CRITICAL": 2, "HIGH": 0, "MODERATE": 0}, worst_cvss=10.0)
    assert r["verdict"] == "RED"
    assert "CRITICAL" in r["detail"]


def test_cve_none_is_green():
    r = gating.grade_cve({"CRITICAL": 0, "HIGH": 0, "MODERATE": 0}, worst_cvss=None)
    assert r["verdict"] == "GREEN"


def test_capability_executes_code_plus_cve_is_red():
    r = gating.grade_capability(["executes_code"], has_cve=True)
    assert r["verdict"] == "RED"


def test_capability_executes_code_alone_is_yellow():
    r = gating.grade_capability(["executes_code"], has_cve=False)
    assert r["verdict"] == "YELLOW"


def test_staleness_two_years_is_red():
    assert gating.grade_staleness(800)["verdict"] == "RED"


def test_staleness_fresh_is_green():
    assert gating.grade_staleness(30)["verdict"] == "GREEN"


def test_health_no_repo_is_yellow_flag():
    r = gating.grade_health(stars=None, open_issues=None, has_repo=False)
    assert r["verdict"] == "YELLOW"


def test_identity_squat_is_red():
    assert gating.grade_identity(True)["verdict"] == "RED"


def test_composite_worst_wins():
    signals = {
        "cve": {"verdict": "GREEN"}, "capability": {"verdict": "RED"},
        "staleness": {"verdict": "GREEN"}, "blast": {"verdict": "YELLOW"},
        "health": {"verdict": "GREEN"}, "identity": {"verdict": "GREEN"},
    }
    assert gating.composite(signals) == "RED"


def test_composite_all_green():
    signals = {k: {"verdict": "GREEN"} for k in
               ["cve", "capability", "staleness", "blast", "health", "identity"]}
    assert gating.composite(signals) == "GREEN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_gating.py -v`
Expected: FAIL (`ModuleNotFoundError: apps.ai_safety_check.gating`).

- [ ] **Step 3: Write `gating.py`**

```python
# apps/ai_safety_check/gating.py
"""Pure safety-signal grading. No network, no I/O. Fully unit-tested."""

_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}


def _worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: _RANK[v])


def grade_cve(counts: dict, worst_cvss: float | None) -> dict:
    crit = counts.get("CRITICAL", 0)
    high = counts.get("HIGH", 0)
    mod = counts.get("MODERATE", 0)
    if crit > 0:
        verdict = "RED"
    elif high > 0:
        verdict = "YELLOW"
    else:
        verdict = "GREEN"
    detail = f"{crit} CRITICAL / {high} HIGH / {mod} MODERATE advisories"
    if worst_cvss is not None:
        detail += f"; worst CVSS {worst_cvss}"
    return {"verdict": verdict, "detail": detail, "worst_cvss": worst_cvss, "counts": counts}


def grade_capability(flags: list[str], has_cve: bool) -> dict:
    dangerous = "executes_code" in flags
    if dangerous and has_cve:
        verdict = "RED"
    elif dangerous or "exposes_server" in flags:
        verdict = "YELLOW"
    else:
        verdict = "GREEN"
    detail = "capabilities: " + (", ".join(flags) if flags else "none detected")
    return {"verdict": verdict, "detail": detail, "flags": flags}


def grade_staleness(days_since_last_release: int | None) -> dict:
    d = days_since_last_release
    if d is None:
        verdict, detail = "YELLOW", "no release date available"
    elif d > 730:
        verdict, detail = "RED", f"last release {d} days ago (>2y)"
    elif d > 365:
        verdict, detail = "YELLOW", f"last release {d} days ago (>1y)"
    else:
        verdict, detail = "GREEN", f"last release {d} days ago"
    return {"verdict": verdict, "detail": detail, "days_since_last_release": d}


def grade_blast(dependent_count: int | None) -> dict:
    c = dependent_count
    if c is None:
        verdict, detail = "GREEN", "no dependents recorded"
    elif c >= 1000:
        verdict, detail = "RED", f"{c} downstream dependents (systemic)"
    elif c >= 100:
        verdict, detail = "YELLOW", f"{c} downstream dependents"
    else:
        verdict, detail = "GREEN", f"{c} downstream dependents"
    return {"verdict": verdict, "detail": detail, "dependent_count": c}


def grade_health(stars: int | None, open_issues: int | None, has_repo: bool) -> dict:
    if not has_repo:
        return {"verdict": "YELLOW", "detail": "no linked source repo (unauditable)",
                "stars": stars, "open_issues": open_issues, "has_repo": False}
    if open_issues is not None and stars is not None and stars > 0 and open_issues > stars:
        verdict, detail = "YELLOW", f"{open_issues} open issues vs {stars} stars"
    else:
        verdict, detail = "GREEN", f"{stars} stars / {open_issues} open issues"
    return {"verdict": verdict, "detail": detail, "stars": stars,
            "open_issues": open_issues, "has_repo": has_repo}


def grade_identity(suspected_squat: bool) -> dict:
    if suspected_squat:
        return {"verdict": "RED", "detail": "suspected squat / name-confusion package",
                "suspected_squat": True}
    return {"verdict": "GREEN", "detail": "identity looks legitimate", "suspected_squat": False}


def composite(signals: dict) -> str:
    return _worst(*(s["verdict"] for s in signals.values()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_gating.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add apps/ai_safety_check/gating.py apps/ai_safety_check/tests/test_gating.py
git commit -m "feat(safety-check): pure traffic-light gating core"
```

---

## Task 3: `craft_client.py` — MCP client (adapt from customer-agent)

**Files:**
- Create: `apps/ai_safety_check/craft_client.py` (adapted copy of `apps/customer-experience-agent/craft_client.py`)
- Test: `apps/ai_safety_check/tests/test_craft_client.py`

**Interfaces:**
- Produces: `class CraftClient` with `__init__(self)`; async methods:
  - `generate_sql(self, question: str, connection: str, schema_name: str, schema_fqn: str) -> dict`
  - `execute_query(self, sql: str, connection: str, max_rows: int = config.QUERY_MAX_ROWS) -> dict` (returns `{"columns": [...], "rows": [[...]]}`)
  - `_auth_headers(self) -> dict`
  - staticmethod `_extract_result(tool: str, event: dict) -> Any`

- [ ] **Step 1: Copy and adapt the source file**

Copy `apps/customer-experience-agent/craft_client.py` to `apps/ai_safety_check/craft_client.py` verbatim, then make exactly these changes:
1. Update the relative import of config (already `from . import config` — keep).
2. Change `generate_sql(self, question)` and `execute_query(self, sql, max_rows=...)` signatures to take an explicit `connection` (and `schema_name`/`schema_fqn` for `generate_sql`) instead of reading a single hardcoded connection from config — because this app talks to **two** connections. Where the original passed `config.CONNECTION_SLUG` / `config.SCHEMA_FQN`, pass the new parameters through into the JSON-RPC `arguments`.
3. Keep the Keycloak refresh-token auth (`_fetch_keycloak_token`), the SSE/JSON branching in `_send`, the tenacity retries, and the `get_result_page` pagination chaining exactly as-is.
4. Add a convenience `async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=config.QUERY_MAX_ROWS) -> tuple[dict, str]` that calls `generate_sql` then `execute_query` and returns `(result_dict, generated_sql)` so nodes get both the rows and the SQL for the audit trail.

- [ ] **Step 2: Write the failing test** (parsing + header logic, no network)

```python
# apps/ai_safety_check/tests/test_craft_client.py
from apps.ai_safety_check.craft_client import CraftClient


def test_auth_headers_include_project_and_bearer(monkeypatch):
    c = CraftClient()
    c._bearer_token = "tok123"
    h = c._auth_headers()
    assert h["Authorization"] == "Bearer tok123"
    assert h["X-Project-ID"]  # project id injected


def test_extract_result_unwraps_content_text():
    event = {"result": {"content": [{"text": '{"ok": true, "rows": []}'}]}}
    out = CraftClient._extract_result("execute_query", event)
    assert out["ok"] is True
```

(Adjust attribute/method names in the test to match whatever the copied file actually uses — the scout confirmed `_auth_headers`, `_bearer_token`, and static `_extract_result` exist.)

- [ ] **Step 3: Run test to verify it fails**, then adapt until green.

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_craft_client.py -v`
Expected first run: FAIL; after the copy+adapt: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/ai_safety_check/craft_client.py apps/ai_safety_check/tests/test_craft_client.py
git commit -m "feat(safety-check): CRAFT MCP client (two-connection, refresh-token auth)"
```

---

## Task 4: `nebius_llm.py` — OpenAI-compatible reasoning client

**Files:**
- Create: `apps/ai_safety_check/nebius_llm.py`
- Test: `apps/ai_safety_check/tests/test_nebius_llm.py`

**Interfaces:**
- Produces: `class NebiusLLM` with `__init__(self, client=None)` (client injectable for tests); `def complete(self, prompt: str, *, json_mode: bool = False) -> str` returning the model's text. Uses `openai.OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY)` and `chat.completions.create(model=config.NEBIUS_MODEL, messages=[{"role":"user","content":prompt}])`.

- [ ] **Step 1: Write the failing test** (inject a fake client)

```python
# apps/ai_safety_check/tests/test_nebius_llm.py
from apps.ai_safety_check.nebius_llm import NebiusLLM


class _FakeChoice:
    def __init__(self, text): self.message = type("M", (), {"content": text})


class _FakeResp:
    def __init__(self, text): self.choices = [_FakeChoice(text)]


class _FakeClient:
    def __init__(self, text): self._text = text; self.calls = []
    class _Chat:
        def __init__(self, outer): self._outer = outer
        class _Completions:
            def __init__(self, outer): self._outer = outer
            def create(self, **kwargs):
                self._outer.calls.append(kwargs)
                return _FakeResp(self._outer._text)
        @property
        def completions(self): return NebiusLLM  # placeholder, replaced below


def test_complete_returns_text(monkeypatch):
    # Minimal fake with the openai client shape:
    class FakeCompletions:
        def __init__(self, text, sink): self.text, self.sink = text, sink
        def create(self, **kw): self.sink.append(kw); return _FakeResp(self.text)
    class FakeChat:
        def __init__(self, text, sink): self.completions = FakeCompletions(text, sink)
    class FakeClient:
        def __init__(self, text, sink): self.chat = FakeChat(text, sink)
    sink = []
    llm = NebiusLLM(client=FakeClient("hello", sink))
    assert llm.complete("hi") == "hello"
    assert sink[0]["model"]  # model passed through
```

- [ ] **Step 2: Run to verify fail**, then implement.

- [ ] **Step 3: Write `nebius_llm.py`**

```python
# apps/ai_safety_check/nebius_llm.py
"""Reasoning LLM via Nebius Token Factory (OpenAI-compatible)."""
from . import config


class NebiusLLM:
    def __init__(self, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY)
        self._client = client

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        kwargs = {"model": config.NEBIUS_MODEL,
                  "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/nebius_llm.py apps/ai_safety_check/tests/test_nebius_llm.py
git commit -m "feat(safety-check): Nebius Token Factory LLM client"
```

---

## Task 5: `tavily_client.py` — hindsight lookup with graceful no-op

**Files:**
- Create: `apps/ai_safety_check/tavily_client.py`
- Test: `apps/ai_safety_check/tests/test_tavily_client.py`

**Interfaces:**
- Produces: `class TavilyClient` with `__init__(self, api_key: str | None = None, http_post=None)`; `def search(self, query: str) -> list[dict]` returning `[{"title": str, "url": str, "content": str}, ...]`. If no api key → returns `[]` (graceful no-op). `http_post` injectable for tests (defaults to `httpx.post`).

- [ ] **Step 1: Write the failing tests**

```python
# apps/ai_safety_check/tests/test_tavily_client.py
from apps.ai_safety_check.tavily_client import TavilyClient


def test_no_key_returns_empty():
    assert TavilyClient(api_key="").search("anything") == []


def test_parses_results():
    def fake_post(url, json=None, timeout=None):
        class R:
            def raise_for_status(self): pass
            def json(self): return {"results": [
                {"title": "T", "url": "http://x", "content": "snippet"}]}
        return R()
    c = TavilyClient(api_key="k", http_post=fake_post)
    out = c.search("mlflow cve 2024")
    assert out[0]["url"] == "http://x"
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/tavily_client.py
"""Hindsight web lookups. Enrichment only — degrades to no-op without a key."""
import httpx

_ENDPOINT = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, api_key: str | None = None, http_post=None):
        from . import config
        self._key = api_key if api_key is not None else config.TAVILY_API_KEY
        self._post = http_post or httpx.post

    def search(self, query: str) -> list[dict]:
        if not self._key:
            return []
        try:
            r = self._post(_ENDPOINT,
                           json={"api_key": self._key, "query": query, "max_results": 5},
                           timeout=15.0)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        return [{"title": x.get("title", ""), "url": x.get("url", ""),
                 "content": x.get("content", "")} for x in data.get("results", [])]
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/tavily_client.py apps/ai_safety_check/tests/test_tavily_client.py
git commit -m "feat(safety-check): Tavily hindsight client with graceful no-op"
```

---

## Task 6: `queries.py` — parameterized NL questions for CRAFT

**Files:**
- Create: `apps/ai_safety_check/queries.py`
- Test: `apps/ai_safety_check/tests/test_queries.py`

**Interfaces:**
- Produces pure functions returning natural-language question strings (fed to `craft.generate_sql`):
  - `discover_top_ai_projects(limit: int = 30) -> str`
  - `package_exists(names: list[str], system: str) -> str`
  - `advisories_for(name: str) -> str`
  - `staleness_for(name: str, system: str) -> str`
  - `dependents_for(name: str, system: str) -> str`
  - `health_for(name: str) -> str`
  - `identity_check(name: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
# apps/ai_safety_check/tests/test_queries.py
from apps.ai_safety_check import queries


def test_advisories_mentions_name_and_severity():
    q = queries.advisories_for("mlflow")
    assert "mlflow" in q
    assert "GitHubSeverity" in q or "severity" in q.lower()


def test_discover_mentions_stars_and_limit():
    q = queries.discover_top_ai_projects(15)
    assert "star" in q.lower()
    assert "15" in q
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/queries.py
"""Natural-language questions handed to CRAFT generate_sql. Kept in one place
so the audit trail and prompt-tuning live together."""


def discover_top_ai_projects(limit: int = 30) -> str:
    return (
        f"What are the top {limit} most-starred projects whose name relates to LLMs, AI agents, "
        "machine learning, or generative AI (names containing gpt, llm, llama, agent, langchain, "
        "transformer, diffusion, stable, bert, or the words ai/ml)? Show ProjectName, ProjectType, "
        "StarsCount, ForksCount, and OpenIssuesCount, ordered by StarsCount descending."
    )


def package_exists(names: list[str], system: str) -> str:
    joined = ", ".join(f"'{n}'" for n in names)
    return (f"For {system} packages whose name is one of {joined}, show the package name, the number "
            "of distinct versions, and the most recent UpstreamPublishedAt date.")


def advisories_for(name: str) -> str:
    return (f"Find all security advisories affecting the package '{name}'. The link is the Advisories "
            "column in PACKAGEVERSIONS joined to ADVISORIES on SourceID. Show advisory Title, "
            "CVSS3Score, and GitHubSeverity, ordered by CVSS3Score descending.")


def staleness_for(name: str, system: str) -> str:
    return (f"For the {system} package '{name}', show the most recent UpstreamPublishedAt date and the "
            "total number of versions.")


def dependents_for(name: str, system: str) -> str:
    return (f"How many distinct packages transitively depend on the {system} package '{name}' according "
            "to the DEPENDENTS table?")


def health_for(name: str) -> str:
    return (f"For projects whose name contains '{name}', show StarsCount, ForksCount, OpenIssuesCount, "
            "and Licenses from the PROJECTS table, ordered by StarsCount descending, limit 5.")


def identity_check(name: str) -> str:
    return (f"Across all systems (PYPI, NPM, MAVEN, CARGO, GO, NUGET), show every System and version count "
            f"for packages named exactly '{name}' in PACKAGEVERSIONS.")
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/queries.py apps/ai_safety_check/tests/test_queries.py
git commit -m "feat(safety-check): parameterized NL query bank"
```

---

## Task 7: `classify.py` — pure parsing of LLM classification

The LLM (Task 4) returns JSON; this module parses/validates it into the tool dict fields, deduping and dropping tutorials/false-positives. Pure given the raw LLM string.

**Files:**
- Create: `apps/ai_safety_check/classify.py`
- Test: `apps/ai_safety_check/tests/test_classify.py`

**Interfaces:**
- Produces:
  - `build_classify_prompt(candidates: list[dict]) -> str` — candidates are `{"name","stars"}`.
  - `parse_classification(raw: str) -> list[dict]` — returns `[{"name","category","capabilities","significance"}]`; tolerant of code-fenced JSON.
  - `filter_real_tools(classified: list[dict], max_tools: int) -> list[dict]` — drops `TUTORIAL`/`FALSE_POSITIVE`, dedups by normalized name (strip, lower, `-`/`_` unified), keeps top `max_tools`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/ai_safety_check/tests/test_classify.py
from apps.ai_safety_check import classify


def test_parse_tolerates_code_fence():
    raw = '```json\n[{"name":"autogpt","category":"AGENT","capabilities":["executes_code"],"significance":"kicked off agents"}]\n```'
    out = classify.parse_classification(raw)
    assert out[0]["name"] == "autogpt"
    assert "executes_code" in out[0]["capabilities"]


def test_filter_drops_tutorials_and_dedups():
    classified = [
        {"name": "autogpt", "category": "AGENT", "capabilities": [], "significance": "x"},
        {"name": "auto-gpt", "category": "AGENT", "capabilities": [], "significance": "x"},
        {"name": "ml-for-beginners", "category": "TUTORIAL", "capabilities": [], "significance": "course"},
        {"name": "masscan", "category": "FALSE_POSITIVE", "capabilities": [], "significance": "scanner"},
    ]
    out = classify.filter_real_tools(classified, max_tools=20)
    names = {t["name"] for t in out}
    assert "ml-for-beginners" not in names and "masscan" not in names
    assert len(out) == 1  # autogpt / auto-gpt deduped
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/classify.py
"""Parse + filter the LLM's tool classification. Pure given the raw string."""
import json
import re

_DROP = {"TUTORIAL", "FALSE_POSITIVE"}


def build_classify_prompt(candidates: list[dict]) -> str:
    lines = "\n".join(f"- {c['name']} ({c.get('stars', '?')} stars)" for c in candidates)
    return (
        "You are triaging AI/LLM software projects for a self-hosting safety audit.\n"
        "For EACH project below, return a JSON array of objects with keys:\n"
        '  "name" (verbatim), "category" (one of AGENT, GATEWAY, INFERENCE_SERVER, '
        'ORCHESTRATION, VECTOR_DB, TUTORIAL, FALSE_POSITIVE),\n'
        '  "capabilities" (subset of ["executes_code","exposes_server","filesystem"]),\n'
        '  "significance" (ONE sentence: what it was and why it mattered).\n'
        "Mark courses/example repos as TUTORIAL and non-AI matches as FALSE_POSITIVE.\n"
        "Return ONLY the JSON array.\n\nProjects:\n" + lines
    )


def parse_classification(raw: str) -> list[dict]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    data = json.loads(text)
    out = []
    for d in data:
        out.append({
            "name": d.get("name", "").strip(),
            "category": d.get("category", "FALSE_POSITIVE"),
            "capabilities": list(d.get("capabilities", [])),
            "significance": d.get("significance", ""),
        })
    return out


def _norm(name: str) -> str:
    return re.sub(r"[-_]", "", name.strip().lower())


def filter_real_tools(classified: list[dict], max_tools: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for t in classified:
        if t["category"] in _DROP:
            continue
        key = _norm(t["name"])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= max_tools:
            break
    return out
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/classify.py apps/ai_safety_check/tests/test_classify.py
git commit -m "feat(safety-check): pure LLM-classification parsing + filtering"
```

---

## Task 8: `state.py` + `nodes.py` — pipeline state and nodes

**Files:**
- Create: `apps/ai_safety_check/state.py`
- Create: `apps/ai_safety_check/nodes.py`
- Test: `apps/ai_safety_check/tests/test_nodes.py`

**Interfaces:**
- Produces:
  - `state.SafetyCheckState` (TypedDict): keys `candidates: list[dict]`, `tools: list[dict]`, `coverage: dict`, `dangers: list[dict]`, `cases: list[str]`, `errors: list[str]`, `sql_log: list`.
  - `nodes.discover_candidates_node(state, craft) -> dict`
  - `nodes.classify_node(state, llm) -> dict`
  - `nodes.gate_node(state, craft) -> dict`
  - `nodes.hindsight_node(state, tavily, llm) -> dict`
  - `nodes.dangers_node(state, llm) -> dict`
  - each returns a partial-state dict. Nodes are `async def`. They append `(label, sql)` to `sql_log` for every CRAFT call.
- Consumes: `gating`, `classify`, `queries`, `craft.nl_query`, `NebiusLLM.complete`, `TavilyClient.search`.

- [ ] **Step 1: Write `state.py`** (no test needed alone; exercised via nodes)

```python
# apps/ai_safety_check/state.py
from typing import TypedDict


class SafetyCheckState(TypedDict, total=False):
    candidates: list[dict]
    tools: list[dict]
    coverage: dict
    dangers: list[dict]
    cases: list[str]
    errors: list[str]
    sql_log: list
```

- [ ] **Step 2: Write the failing test** for `gate_node` using a fake craft client

```python
# apps/ai_safety_check/tests/test_nodes.py
import asyncio
from apps.ai_safety_check import nodes


class FakeCraft:
    """Returns canned rows per NL question substring."""
    def __init__(self): self.sql_log = []
    async def nl_query(self, question, connection, schema_name, schema_fqn, max_rows=200):
        q = question.lower()
        if "advisor" in q:
            return ({"columns": ["Title", "CVSS3Score", "GitHubSeverity"],
                     "rows": [["path traversal", 10.0, "CRITICAL"]]}, "SELECT ... advisories")
        if "dependents" in q:
            return ({"columns": ["c"], "rows": [[1500]]}, "SELECT count dependents")
        if "upstreampublishedat" in q:
            return ({"columns": ["d", "v"], "rows": [["2023-07-17T00:00:00", 78]]}, "SELECT staleness")
        if "projects" in q:
            return ({"columns": ["StarsCount", "ForksCount", "OpenIssuesCount", "Licenses"],
                     "rows": [[15000, 3000, 700, "Apache-2.0"]]}, "SELECT health")
        return ({"columns": ["System", "v"], "rows": [["PYPI", 78]]}, "SELECT identity")


def test_gate_node_reds_out_mlflow():
    state = {"tools": [{"name": "mlflow", "system": "PYPI", "category": "INFERENCE_SERVER",
                        "capabilities": ["exposes_server", "filesystem"], "significance": "ml platform",
                        "stars": 15000, "sql_log": []}], "sql_log": []}
    out = asyncio.run(nodes.gate_node(state, FakeCraft()))
    tool = out["tools"][0]
    assert tool["verdict"] == "RED"          # 2 CVSS-10 criticals
    assert tool["signals"]["cve"]["verdict"] == "RED"
    assert any(lbl.startswith("advisories") for lbl, _ in tool["sql_log"])
```

- [ ] **Step 3: Run to verify fail. Step 4: Write `nodes.py`**

```python
# apps/ai_safety_check/nodes.py
"""LangGraph pipeline nodes. Each returns a partial-state dict."""
from . import config, gating, classify, queries


def _rows(result: dict) -> list[list]:
    return result.get("rows", []) if isinstance(result, dict) else []


async def discover_candidates_node(state, craft) -> dict:
    q = queries.discover_top_ai_projects(30)
    result, sql = await craft.nl_query(q, config.GITHUB_CONNECTION,
                                        config.GITHUB_SCHEMA_NAME, config.GITHUB_SCHEMA_FQN)
    cands = []
    for row in _rows(result):
        name = str(row[0]).split("/")[-1]
        stars = int(row[2]) if len(row) > 2 and str(row[2]).isdigit() else None
        cands.append({"name": name, "stars": stars})
    return {"candidates": cands, "coverage": {"discovered": len(cands)},
            "sql_log": state.get("sql_log", []) + [("discover", sql)]}


async def classify_node(state, llm) -> dict:
    cands = state.get("candidates", [])
    prompt = classify.build_classify_prompt(cands)
    raw = llm.complete(prompt, json_mode=True)
    parsed = classify.parse_classification(raw)
    kept = classify.filter_real_tools(parsed, config.MAX_TOOLS)
    stars_by = {c["name"]: c.get("stars") for c in cands}
    tools = [{"name": t["name"], "system": "PYPI", "category": t["category"],
              "capabilities": t["capabilities"], "significance": t["significance"],
              "stars": stars_by.get(t["name"]), "sql_log": []} for t in kept]
    return {"tools": tools}


async def gate_node(state, craft) -> dict:
    graded = []
    for tool in state.get("tools", []):
        log = list(tool.get("sql_log", []))
        # CVE
        r, sql = await craft.nl_query(queries.advisories_for(tool["name"]),
                                      config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
        log.append(("advisories:" + tool["name"], sql))
        counts = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0}
        worst = None
        for row in _rows(r):
            sev = str(row[2]).upper() if len(row) > 2 else "UNKNOWN"
            if sev in counts:
                counts[sev] += 1
            try:
                cv = float(row[1])
                worst = cv if worst is None else max(worst, cv)
            except (TypeError, ValueError):
                pass
        cve = gating.grade_cve(counts, worst)
        has_cve = cve["verdict"] in ("RED", "YELLOW")
        # capability (from classification)
        cap = gating.grade_capability(tool.get("capabilities", []), has_cve)
        # staleness
        r, sql = await craft.nl_query(queries.staleness_for(tool["name"], tool["system"]),
                                      config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
        log.append(("staleness:" + tool["name"], sql))
        days = _days_since(_first_cell(r))
        stale = gating.grade_staleness(days)
        # blast
        r, sql = await craft.nl_query(queries.dependents_for(tool["name"], tool["system"]),
                                      config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
        log.append(("dependents:" + tool["name"], sql))
        blast = gating.grade_blast(_first_int(r))
        # health
        r, sql = await craft.nl_query(queries.health_for(tool["name"]),
                                      config.GITHUB_CONNECTION, config.GITHUB_SCHEMA_NAME, config.GITHUB_SCHEMA_FQN)
        log.append(("health:" + tool["name"], sql))
        stars, issues, has_repo = _health_cells(r, tool.get("stars"))
        health = gating.grade_health(stars, issues, has_repo)
        # identity
        r, sql = await craft.nl_query(queries.identity_check(tool["name"]),
                                      config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
        log.append(("identity:" + tool["name"], sql))
        squat = _looks_like_squat(r)
        identity = gating.grade_identity(squat)

        signals = {"cve": cve, "capability": cap, "staleness": stale,
                   "blast": blast, "health": health, "identity": identity}
        graded.append({**tool, "signals": signals,
                       "verdict": gating.composite(signals), "sql_log": log})
    return {"tools": graded}


def _first_cell(r):
    rows = _rows(r)
    return rows[0][0] if rows and rows[0] else None


def _first_int(r):
    v = _first_cell(r)
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _days_since(date_str):
    if not date_str:
        return None
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    # Snapshot horizon is fixed at 2023-07-31 for "days since" purposes.
    horizon = datetime(2023, 7, 31, tzinfo=timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (horizon - d).days


def _health_cells(r, fallback_stars):
    rows = _rows(r)
    if not rows:
        return fallback_stars, None, False
    row = rows[0]
    stars = int(row[0]) if len(row) > 0 and str(row[0]).isdigit() else fallback_stars
    issues = int(row[2]) if len(row) > 2 and str(row[2]).isdigit() else None
    return stars, issues, True


def _looks_like_squat(r):
    # Heuristic: a package that exists in exactly one ecosystem with a single version
    # under a well-known vendor name is squat-suspicious. Refined during tuning.
    rows = _rows(r)
    if len(rows) == 1 and len(rows[0]) > 1:
        try:
            return int(rows[0][1]) <= 1
        except (TypeError, ValueError):
            return False
    return False


async def hindsight_node(state, tavily, llm) -> dict:
    tools = state.get("tools", [])
    for tool in tools:
        results = tavily.search(f"{tool['name']} vulnerability CVE 2024 2025 incident")
        if not results:
            tool["hindsight"] = {"tag": "hindsight unavailable", "source_url": None}
            continue
        src = results[0]
        prompt = (f"In <=8 words, summarize what happened to '{tool['name']}' after mid-2023 based "
                  f"ONLY on this source. Source: {src['title']} — {src['content'][:500]}")
        tag = llm.complete(prompt).strip()
        tool["hindsight"] = {"tag": tag, "source_url": src["url"]}
    return {"tools": tools}


async def dangers_node(state, llm) -> dict:
    tools = state.get("tools", [])
    summary = "\n".join(
        f"- {t['name']} [{t['verdict']}] caps={t.get('capabilities')} "
        f"cve={t['signals']['cve']['detail']}" for t in tools if t.get("signals"))
    prompt = ("From these graded AI tools, identify the 3-5 recurring supply-chain danger PATTERNS. "
              "Return a JSON array of objects with keys 'pattern', 'seen_in' (list of tool names), "
              "'remediation' (one sentence). Return ONLY JSON.\n\n" + summary)
    import json
    try:
        raw = llm.complete(prompt, json_mode=True)
        dangers = json.loads(classify.parse_classification.__self__ if False else _strip_fence(raw))
    except Exception:
        dangers = []
    return {"dangers": dangers}


def _strip_fence(raw: str) -> str:
    import re
    t = re.sub(r"^```(?:json)?", "", raw.strip()).strip()
    t = re.sub(r"```$", "", t).strip()
    s, e = t.find("["), t.rfind("]")
    return t[s:e + 1] if s != -1 else t
```

> Note during implementation: the `dangers_node` JSON parse should reuse `_strip_fence`; remove the dead `classify.parse_classification.__self__` expression — it is shown here only to flag that a fence-stripping helper is needed. Use `json.loads(_strip_fence(raw))`.

- [ ] **Step 5: Run the node test to verify pass.**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_nodes.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/ai_safety_check/state.py apps/ai_safety_check/nodes.py apps/ai_safety_check/tests/test_nodes.py
git commit -m "feat(safety-check): pipeline state + nodes (discover/classify/gate/hindsight/dangers)"
```

---

## Task 9: `graph.py` — wire the LangGraph pipeline

**Files:**
- Create: `apps/ai_safety_check/graph.py`
- Test: extend `apps/ai_safety_check/tests/test_nodes.py` with a graph smoke test.

**Interfaces:**
- Produces: `build_graph(craft, llm, tavily)` returning a compiled graph whose `.ainvoke(initial_state)` runs discover → classify → gate → hindsight → dangers → END. Binds deps via `functools.partial`.

- [ ] **Step 1: Write the failing smoke test** (fakes for all three deps)

```python
# append to apps/ai_safety_check/tests/test_nodes.py
import asyncio
from apps.ai_safety_check.graph import build_graph


class FakeLLM:
    def complete(self, prompt, json_mode=False):
        if "recurring supply-chain danger" in prompt:
            return '[{"pattern":"executes code","seen_in":["autogpt"],"remediation":"sandbox it"}]'
        if "triaging" in prompt.lower() or "classification" in prompt.lower():
            return '[{"name":"mlflow","category":"INFERENCE_SERVER","capabilities":["exposes_server"],"significance":"ml platform"}]'
        return "summary"


class FakeTavily:
    def search(self, q): return [{"title": "t", "url": "http://x", "content": "exploited"}]


def test_graph_runs_end_to_end():
    craft = FakeCraft()
    # discover returns one project row:
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        if "most-starred" in question:
            return ({"columns": ["ProjectName", "ProjectType", "StarsCount"],
                     "rows": [["org/mlflow", "GITHUB", 15000]]}, "SELECT discover")
        return await FakeCraft().nl_query(question, connection, schema_name, schema_fqn, max_rows)
    craft.nl_query = nl_query
    graph = build_graph(craft, FakeLLM(), FakeTavily())
    out = asyncio.run(graph.ainvoke({"sql_log": []}))
    assert out["tools"][0]["verdict"] == "RED"
    assert out["dangers"][0]["pattern"]
```

- [ ] **Step 2: Run to verify fail. Step 3: Write `graph.py`**

```python
# apps/ai_safety_check/graph.py
import functools
from langgraph.graph import StateGraph, END
from .state import SafetyCheckState
from . import nodes


def build_graph(craft, llm, tavily):
    g = StateGraph(SafetyCheckState)
    g.add_node("discover", functools.partial(nodes.discover_candidates_node, craft=craft))
    g.add_node("classify", functools.partial(nodes.classify_node, llm=llm))
    g.add_node("gate", functools.partial(nodes.gate_node, craft=craft))
    g.add_node("hindsight", functools.partial(nodes.hindsight_node, tavily=tavily, llm=llm))
    g.add_node("dangers", functools.partial(nodes.dangers_node, llm=llm))
    g.set_entry_point("discover")
    g.add_edge("discover", "classify")
    g.add_edge("classify", "gate")
    g.add_edge("gate", "hindsight")
    g.add_edge("hindsight", "dangers")
    g.add_edge("dangers", END)
    return g.compile()
```

> Note: node functions are defined as `async def node(state, dep)`; `functools.partial(fn, craft=craft)` supplies the dependency by keyword so LangGraph calls them with `state` only. Confirm the partial keyword names match each node's second parameter (`craft`, `llm`, `tavily`).

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/graph.py apps/ai_safety_check/tests/test_nodes.py
git commit -m "feat(safety-check): LangGraph pipeline wiring + end-to-end smoke test"
```

---

## Task 10: `report.py` — pure markdown + leaderboard figure

**Files:**
- Create: `apps/ai_safety_check/report.py`
- Test: `apps/ai_safety_check/tests/test_report.py`

**Interfaces:**
- Produces:
  - `render_markdown(state: dict) -> str` — 3 tiers: leaderboard table, case studies (for `state["cases"]` names), Common Dangers.
  - `leaderboard_figure(state: dict) -> dict` — a plotly figure dict (`{"data":[...],"layout":{...}}`) for `render_chart`/`st.plotly_chart`.
  - `BADGE = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}`

- [ ] **Step 1: Write the failing test**

```python
# apps/ai_safety_check/tests/test_report.py
from apps.ai_safety_check import report

STATE = {
    "tools": [{"name": "mlflow", "category": "INFERENCE_SERVER", "verdict": "RED",
               "significance": "ml platform", "capabilities": ["exposes_server"],
               "stars": 15000,
               "signals": {"cve": {"detail": "2 CRITICAL"}, "capability": {"detail": "x"},
                           "staleness": {"detail": "x"}, "blast": {"detail": "x"},
                           "health": {"detail": "x"}, "identity": {"detail": "x"}},
               "hindsight": {"tag": "actively exploited", "source_url": "http://x"}}],
    "dangers": [{"pattern": "web UI exposes filesystem", "seen_in": ["mlflow"],
                 "remediation": "auth the UI"}],
    "cases": ["mlflow"],
}


def test_markdown_has_all_three_tiers():
    md = report.render_markdown(STATE)
    assert "🔴" in md and "mlflow" in md          # leaderboard badge
    assert "Case Stud" in md                       # case-study tier
    assert "web UI exposes filesystem" in md       # dangers tier


def test_figure_has_data():
    fig = report.leaderboard_figure(STATE)
    assert fig["data"]
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/report.py
"""Pure rendering of the final state into markdown + a plotly figure dict."""

BADGE = {"RED": "🔴", "YELLOW": "🟡", "GREEN": "🟢"}


def render_markdown(state: dict) -> str:
    tools = state.get("tools", [])
    lines = ["# 🔴🟡🟢 LLM / AI Safety Check", "",
             "*Red light, green light for self-hosted AI — would you run this on your laptop?*", "",
             "## Leaderboard", "",
             "| Verdict | Tool | Category | Significance | What happened next |",
             "|---|---|---|---|---|"]
    for t in tools:
        hs = (t.get("hindsight") or {}).get("tag", "")
        lines.append(f"| {BADGE.get(t['verdict'], '')} {t['verdict']} | {t['name']} | "
                     f"{t['category']} | {t.get('significance', '')} | {hs} |")
    # Case studies
    lines += ["", "## Case Studies", ""]
    by_name = {t["name"]: t for t in tools}
    for name in state.get("cases", []):
        t = by_name.get(name)
        if not t:
            continue
        lines.append(f"### {BADGE.get(t['verdict'], '')} {name}")
        lines.append(f"*{t.get('significance', '')}*")
        for key, sig in t.get("signals", {}).items():
            lines.append(f"- **{key}:** {sig.get('detail', '')}")
        hs = t.get("hindsight") or {}
        if hs.get("source_url"):
            lines.append(f"- **What actually happened:** {hs.get('tag')} "
                         f"([source]({hs['source_url']}))")
        lines.append("")
    # Common dangers
    lines += ["## Common Dangers", ""]
    for d in state.get("dangers", []):
        seen = ", ".join(d.get("seen_in", []))
        lines.append(f"- **{d.get('pattern')}** — seen in {seen}. "
                     f"*Unscrew:* {d.get('remediation')}")
    return "\n".join(lines)


def leaderboard_figure(state: dict) -> dict:
    tools = state.get("tools", [])
    colors = {"RED": "#e5484d", "YELLOW": "#f5a623", "GREEN": "#30a46c"}
    names = [t["name"] for t in tools]
    stars = [t.get("stars") or 0 for t in tools]
    bar_colors = [colors.get(t["verdict"], "#888") for t in tools]
    return {
        "data": [{"type": "bar", "x": stars, "y": names, "orientation": "h",
                  "marker": {"color": bar_colors}}],
        "layout": {"title": "AI tools by popularity, colored by safety verdict",
                   "xaxis": {"title": "GitHub stars"}, "height": 500},
    }
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/report.py apps/ai_safety_check/tests/test_report.py
git commit -m "feat(safety-check): pure markdown + leaderboard figure rendering"
```

---

## Task 11: `main.py` — CLI entry + run artifacts (first end-to-end run)

**Files:**
- Create: `apps/ai_safety_check/main.py`
- Test: `apps/ai_safety_check/tests/test_main.py`

**Interfaces:**
- Produces:
  - `async def run(*, craft=None, llm=None, tavily=None) -> dict` — builds deps (real if not injected), invokes graph, returns final state.
  - `def save_artifacts(state: dict, out_dir: str) -> None` — writes `report.md`, `sql_queries.txt`, `state.json`, `leaderboard.png`.
  - `def _create_run_dir() -> str` — `runs/safety_<ts>/` (timestamp injected/parametrized so tests are deterministic).
  - CLI: `python -m apps.ai_safety_check.main` runs and saves.

- [ ] **Step 1: Write the failing test** (inject fakes, assert artifacts)

```python
# apps/ai_safety_check/tests/test_main.py
import asyncio, json, os
from apps.ai_safety_check import main
from apps.ai_safety_check.tests.test_nodes import FakeCraft, FakeLLM, FakeTavily


def test_run_and_save_writes_artifacts(tmp_path):
    craft = FakeCraft()
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        if "most-starred" in question:
            return ({"columns": ["ProjectName", "ProjectType", "StarsCount"],
                     "rows": [["org/mlflow", "GITHUB", 15000]]}, "SELECT discover")
        return await FakeCraft().nl_query(question, connection, schema_name, schema_fqn, max_rows)
    craft.nl_query = nl_query
    state = asyncio.run(main.run(craft=craft, llm=FakeLLM(), tavily=FakeTavily()))
    out = str(tmp_path / "run")
    main.save_artifacts(state, out)
    assert os.path.exists(os.path.join(out, "report.md"))
    assert os.path.exists(os.path.join(out, "sql_queries.txt"))
    saved = json.load(open(os.path.join(out, "state.json")))
    assert saved["tools"][0]["verdict"] == "RED"
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/main.py
import asyncio
import json
import os
from datetime import datetime, timezone

from . import report
from .graph import build_graph


async def run(*, craft=None, llm=None, tavily=None) -> dict:
    if craft is None:
        from .craft_client import CraftClient
        craft = CraftClient()
    if llm is None:
        from .nebius_llm import NebiusLLM
        llm = NebiusLLM()
    if tavily is None:
        from .tavily_client import TavilyClient
        tavily = TavilyClient()
    graph = build_graph(craft, llm, tavily)
    return await graph.ainvoke({"sql_log": []})


def _create_run_dir() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join("runs", f"safety_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def save_artifacts(state: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(report.render_markdown(state))
    with open(os.path.join(out_dir, "state.json"), "w") as f:
        json.dump(state, f, indent=2, default=str)
    with open(os.path.join(out_dir, "sql_queries.txt"), "w") as f:
        for tool in state.get("tools", []):
            for label, sql in tool.get("sql_log", []):
                f.write(f"-- {label}\n{sql}\n\n")
    try:
        import plotly.io as pio
        fig = report.leaderboard_figure(state)
        pio.write_image(fig, os.path.join(out_dir, "leaderboard.png"),
                        width=1000, height=600)
    except Exception:
        pass  # kaleido optional; PNG is a nicety


def main() -> None:
    state = asyncio.run(run())
    out = _create_run_dir()
    save_artifacts(state, out)
    print(f"Wrote report to {out}/report.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass. Commit.**

```bash
git add apps/ai_safety_check/main.py apps/ai_safety_check/tests/test_main.py
git commit -m "feat(safety-check): CLI entry + run-artifact trail (end-to-end with fakes)"
```

---

## Task 12: `app.py` — Streamlit UI (cached render + ask-box)

**Files:**
- Create: `apps/ai_safety_check/app.py`
- Test: `apps/ai_safety_check/tests/test_app_renders.py`

**Interfaces:**
- Consumes: `main.run`, `report.render_markdown`, `report.leaderboard_figure`, latest `runs/safety_*/state.json`.
- Behavior: on load, render from the newest cached `runs/safety_*/state.json` if present; a "Re-run live" button calls `asyncio.run(main.run())`; an "Ask the supply chain" text box calls `craft.nl_query` live and shows the answer + generated SQL. Uses the `sys.path.insert` repo-root hack.

- [ ] **Step 1: Write the AppTest smoke test**

```python
# apps/ai_safety_check/tests/test_app_renders.py
from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("apps/ai_safety_check/app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    labels = {b.label for b in at.button}
    assert "Re-run live" in labels
```

- [ ] **Step 2: Run to verify fail. Step 3: Implement.**

```python
# apps/ai_safety_check/app.py
import os
import sys
import glob
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from apps.ai_safety_check import report, main
from apps.ai_safety_check import config, queries

st.set_page_config(page_title="AI Safety Check", page_icon="🚦", layout="wide")
st.title("🔴🟡🟢 LLM / AI Safety Check")
st.caption("Red light, green light for self-hosted AI — would you run this on your laptop?")


def _latest_state():
    runs = sorted(glob.glob("runs/safety_*/state.json"))
    if not runs:
        return None
    with open(runs[-1]) as f:
        return json.load(f)


state = st.session_state.get("state") or _latest_state()

col_run, col_ask = st.columns([1, 2])
with col_run:
    if st.button("Re-run live"):
        with st.status("Running safety check…", expanded=True):
            state = asyncio.run(main.run())
            st.session_state["state"] = state
with col_ask:
    q = st.text_input("Ask the supply chain (plain English):",
                      placeholder="Which AI agents execute code but have unpatched critical CVEs?")
    if q:
        from apps.ai_safety_check.craft_client import CraftClient
        craft = CraftClient()
        result, sql = asyncio.run(craft.nl_query(
            q, config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN))
        st.dataframe({c: [r[i] for r in result.get("rows", [])]
                      for i, c in enumerate(result.get("columns", []))})
        with st.expander("Generated SQL"):
            st.code(sql, language="sql")

if state:
    left, right = st.columns([3, 2])
    with left:
        st.markdown(report.render_markdown(state))
    with right:
        st.plotly_chart(report.leaderboard_figure(state), use_container_width=True)
else:
    st.info("No cached run yet. Click **Re-run live** to generate one.")
```

- [ ] **Step 4: Run to verify pass** (AppTest renders with no cached run → shows info, button present).

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/test_app_renders.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/ai_safety_check/app.py apps/ai_safety_check/tests/test_app_renders.py
git commit -m "feat(safety-check): Streamlit UI (cached render, re-run, ask-box)"
```

---

## Task 13: Live integration run + case-study pinning + README

**Files:**
- Modify: `apps/ai_safety_check/config.py` (finalize `PINNED_CASES` after a real run)
- Create: `apps/ai_safety_check/README.md`
- Create: (generated) `runs/safety_<ts>/` cached demo artifact — committed so the hosted/cached demo works without keys.

**Interfaces:** none new.

- [ ] **Step 1: Run the full unit suite**

Run: `apps/ai_safety_check/.venv/bin/python -m pytest apps/ai_safety_check/tests/ -q`
Expected: all green.

- [ ] **Step 2: Do a real end-to-end run** (needs `.env` filled with Nebius + Keycloak refresh token; Tavily optional)

Run: `uv run python -m apps.ai_safety_check.main`
Expected: prints `Wrote report to runs/safety_<ts>/report.md`; inspect `report.md` for a sensible leaderboard, mlflow appearing RED, and dangers.

- [ ] **Step 3: Pin case studies** — from the real leaderboard, choose the 3 strongest stories; set `config.PINNED_CASES` and ensure `main.run` seeds `state["cases"]` from `config.PINNED_CASES` (add `"cases": list(config.PINNED_CASES)` to the initial state in `main.run`). Re-run so `state.json` reflects them.

- [ ] **Step 4: Commit the cached demo run + README + finalized config**

```bash
git add apps/ai_safety_check/README.md apps/ai_safety_check/config.py runs/safety_*/
git commit -m "feat(safety-check): pin case studies + commit cached demo run + README"
```

- [ ] **Step 5: Verify the app renders the cached run**

Run: `uv run streamlit run apps/ai_safety_check/app.py`
Expected: leaderboard + case studies + dangers render from cache without re-running; ask-box works live.

---

## Self-Review (completed against the spec)

- **§1 concept / traffic-light verdicts** → Tasks 2, 8, 10. ✅
- **§3 data constraints** (GitHubSeverity, two connections, schema_fqn) → Global Constraints + Tasks 1, 6, 8. ✅
- **§4 architecture** (LangGraph clone, Nebius LLM swap, refresh-token auth) → Tasks 3, 4, 9. ✅
- **§5 pipeline nodes** (discover/classify/gate/hindsight/dangers) → Task 8; wiring Task 9. ✅
- **§6 six signals + worst-wins** → Task 2 (gating) + Task 8 (gate_node assembles all six). ✅
- **§7 hindsight** (universal tag + source URL, graceful no-op) → Tasks 5, 8. ✅ (Featured 3-case *selection* is human-pinned in Task 13 per spec's "agent-proposed, human-curated".)
- **§8 Common Dangers** → Task 8 `dangers_node` + Task 10 rendering. ✅
- **§9 Streamlit output** (leaderboard, case studies, dangers, ask-box, cached render) → Tasks 10, 12. ✅
- **§10 module layout** → matches File Structure exactly. ✅
- **§11 config/artifacts/testing** → Tasks 1, 11; tests every task. ✅
- **§12 deployment** (headless refresh-token auth) → Task 3 preserves it; no code beyond that needed for local/Proxmox. ✅

**Known deferrals (intentional, noted for the executor):**
- `_looks_like_squat` and staleness/blast thresholds are first-pass heuristics; Task 13's real run is where they get tuned against the actual distribution (spec §6 "thresholds tuned during implementation").
- The `identity` NPM-squat example (`anthropic` on npm) may need a dedicated cross-ecosystem query if the single-version heuristic proves too coarse — revisit in Task 13.
- `dangers_node` must use `json.loads(_strip_fence(raw))` (the inline note flags a placeholder expression to delete).
