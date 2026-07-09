# Merge Craft-Dogfooding customer-experience-agent + Public Release Prep — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate `seller_agent/` to `apps/seller_delivery_agent/`, copy Craft-Dogfooding's `apps/customer-experience-agent/` into this repo as a sibling, and clean up docs/repo hygiene (READMEs, LICENSE, dangling internal references) so the repo is ready to be made public — with zero behavioral changes to either agent.

**Architecture:** Both demo agents live side-by-side under `apps/`. `seller_delivery_agent` keeps its existing internal module structure (relative imports inside the package are untouched); only its *externally-facing* absolute imports (`app.py` and its test suite) and its README need updating to reflect the new `apps.` prefix and path. `customer-experience-agent` is copied byte-for-byte (no history) with one text edit afterward to remove a dangling cross-repo reference in an ADR.

**Tech Stack:** Python 3.13 (seller_delivery_agent, via `pip`/`requirements.txt`), Python 3.12 (customer-experience-agent, via `uv`/`pyproject.toml` — untouched), pytest, Streamlit.

## Global Constraints

- No behavioral changes to either agent's runtime logic — only paths/imports/docs change.
- `seller_delivery_agent/config.py`'s hardcoded `PROJECT_ID` and dev-environment URLs are kept as-is (explicitly out of scope).
- No git history is preserved from `Craft-Dogfooding` — files are copied as fresh content.
- No CI/CD setup.
- `apps/customer-experience-agent/*` code files are copied verbatim except the ADR-002 edit (Task 3) — do not touch its config, imports, or logic.
- Every gitignored artifact (`runs/`, `.token_cache.json`, `__pycache__/`, `uv.lock`) must remain untracked after the move — verify with `git status` before each commit, not after.

**Task order:** these tasks are sequential, not independent — do not parallelize.
Task 1 creates the root `.gitignore` that Task 2 relies on to keep `.DS_Store` out of the
copy. Task 3 edits a file that Task 2 creates. Task 4 rewrites paths that only exist after
Task 1. Task 5 links to both agent directories, so it must run after Tasks 1 and 2. Task 6
verifies the end state of all five.

---

### Task 1: Relocate seller_agent to apps/seller_delivery_agent and fix its absolute imports

**Context:** `seller_agent/` is currently **untracked** by git (confirmed: `git ls-files seller_agent` returns 0 files). This means `git mv` will fail (`git mv` requires the source to already be tracked) — use a plain filesystem move, then `git add` the destination. The package's *internal* files (`agent.py`, `llm.py`, `tools.py`, `craft_client.py`, `craft_auth.py`, `config.py`, `prompts.py`, `charts.py`) already use relative imports (e.g. `from .craft_client import CraftClient`) and need **no changes**. Only `app.py` and all 8 files under `tests/` use absolute `seller_agent.`-prefixed imports, and those need an `apps.` prefix.

**Files:**
- Move: `seller_agent/` → `apps/seller_delivery_agent/` (entire directory, via `mv`)
- Modify: `apps/seller_delivery_agent/app.py`
- Modify: `apps/seller_delivery_agent/tests/test_config.py`
- Modify: `apps/seller_delivery_agent/tests/test_parsing.py`
- Modify: `apps/seller_delivery_agent/tests/test_prompts.py`
- Modify: `apps/seller_delivery_agent/tests/test_tools.py`
- Modify: `apps/seller_delivery_agent/tests/test_llm.py`
- Modify: `apps/seller_delivery_agent/tests/test_outputs.py`
- Modify: `apps/seller_delivery_agent/tests/test_charts.py`
- Modify: `apps/seller_delivery_agent/tests/test_app_renders.py`

**Interfaces:**
- Produces: `apps/seller_delivery_agent/` importable as `apps.seller_delivery_agent` (a Python namespace package rooted at repo root — no `apps/__init__.py` needed since `apps/seller_delivery_agent/__init__.py` already exists and pytest/streamlit are run from repo root).

- [ ] **Step 1: Move the directory, remove macOS cruft, add a repo-root .gitignore, and stage it in git**

`.DS_Store` files exist at the repo root, inside `seller_agent/`, and inside `seller_agent/runs/` — and nothing in the repo currently ignores them, so a plain `git add` would commit them. Add a root `.gitignore` covering `.DS_Store` (and other common macOS/editor cruft) before staging anything.

```bash
mkdir -p apps
mv seller_agent apps/seller_delivery_agent
find apps/seller_delivery_agent -name ".DS_Store" -delete
rm -f .DS_Store
cat > .gitignore <<'EOF'
.DS_Store
__pycache__/
*.pyc
.venv/
EOF
git add .gitignore apps/seller_delivery_agent
git status --porcelain=v1 | grep -v '^??' | head -30
```

Expected: every line is prefixed `A  ` and paths are either `.gitignore` or under `apps/seller_delivery_agent/...`. Confirm `runs/`, `.token_cache.json`, and `.DS_Store` are **not** in this list (the first two are gitignored by `apps/seller_delivery_agent/.gitignore`, which moved along with everything else; `.DS_Store` files were deleted above and are now also covered by the new root `.gitignore`).

- [ ] **Step 2: Fix `app.py`'s import prefix and sys.path depth**

`apps/seller_delivery_agent/app.py` currently reads (lines 1–23):

```python
"""Streamlit UI for the Marketplace Root-Cause Investigator.

Ask any question about the marketplace data. Claude orchestrates the investigation itself
— discovering the schema, forming and testing hypotheses, and following the evidence — and
you watch it reason live. Run with:  streamlit run seller_agent/app.py
"""
import asyncio
import os
import sys

# `streamlit run seller_agent/app.py` executes this file as a top-level script (module
# name "__main__"), so relative imports have no package. Put the repo root on sys.path and
# import the package absolutely — this works both under `streamlit run` and as a module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from seller_agent import config
from seller_agent.agent import DEFAULT_QUESTION, run
from seller_agent.craft_auth import build_oauth_provider
```

Replace lines 1–23 with:

```python
"""Streamlit UI for the Marketplace Root-Cause Investigator.

Ask any question about the marketplace data. Claude orchestrates the investigation itself
— discovering the schema, forming and testing hypotheses, and following the evidence — and
you watch it reason live. Run with:  streamlit run apps/seller_delivery_agent/app.py
"""
import asyncio
import os
import sys

# `streamlit run apps/seller_delivery_agent/app.py` executes this file as a top-level script
# (module name "__main__"), so relative imports have no package. Put the repo root on
# sys.path and import the package absolutely — this works both under `streamlit run` and as
# a module. app.py is two directories below repo root (apps/seller_delivery_agent/app.py),
# so dirname must be applied twice.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from apps.seller_delivery_agent import config
from apps.seller_delivery_agent.agent import DEFAULT_QUESTION, run
from apps.seller_delivery_agent.craft_auth import build_oauth_provider
```

The rest of `app.py` (line 24 onward) is unchanged — it only references `config`, `DEFAULT_QUESTION`, `run`, and `build_oauth_provider` by their imported names, not by module path.

- [ ] **Step 3: Fix the 8 test files' absolute imports**

`apps/seller_delivery_agent/tests/test_config.py` — replace line 1:

```python
from seller_agent import config
```

with:

```python
from apps.seller_delivery_agent import config
```

`apps/seller_delivery_agent/tests/test_parsing.py` — replace lines 3–9:

```python
from seller_agent.craft_client import (
    MCPResponseError,
    parse_execute_query,
    parse_generate_sql,
    parse_plotly,
    parse_result_page,
)
```

with:

```python
from apps.seller_delivery_agent.craft_client import (
    MCPResponseError,
    parse_execute_query,
    parse_generate_sql,
    parse_plotly,
    parse_result_page,
)
```

`apps/seller_delivery_agent/tests/test_prompts.py` — replace line 1:

```python
from seller_agent import prompts
```

with:

```python
from apps.seller_delivery_agent import prompts
```

`apps/seller_delivery_agent/tests/test_tools.py` — replace lines 4–5:

```python
from seller_agent import config
from seller_agent.tools import TOOL_DEFINITIONS, ToolExecutor
```

with:

```python
from apps.seller_delivery_agent import config
from apps.seller_delivery_agent.tools import TOOL_DEFINITIONS, ToolExecutor
```

Also replace line 126 (`import seller_agent.tools as tools_mod`):

```python
    import seller_agent.tools as tools_mod
```

with:

```python
    import apps.seller_delivery_agent.tools as tools_mod
```

And replace line 146 (same pattern, inside `test_get_result_page_gives_clear_error_after_exhausting_retries`):

```python
    import seller_agent.tools as tools_mod
```

with:

```python
    import apps.seller_delivery_agent.tools as tools_mod
```

`apps/seller_delivery_agent/tests/test_llm.py` — replace line 6:

```python
from seller_agent import llm
```

with:

```python
from apps.seller_delivery_agent import llm
```

`apps/seller_delivery_agent/tests/test_outputs.py` — replace line 5:

```python
import seller_agent.agent as agent
```

with:

```python
import apps.seller_delivery_agent.agent as agent
```

`apps/seller_delivery_agent/tests/test_charts.py` — replace line 3:

```python
from seller_agent.charts import render_chart
```

with:

```python
from apps.seller_delivery_agent.charts import render_chart
```

`apps/seller_delivery_agent/tests/test_app_renders.py` — replace the full file content:

```python
"""The Streamlit app must render without raising when executed as an app script.

`streamlit run apps/seller_delivery_agent/app.py` runs the file as a top-level script, so
relative imports fail — this test uses Streamlit's AppTest harness (the same execution path a
browser session drives) to catch that class of bug, which an HTTP-200 check misses.
"""
from streamlit.testing.v1 import AppTest


def test_app_renders_without_exception():
    at = AppTest.from_file("apps/seller_delivery_agent/app.py", default_timeout=30)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    # key controls present
    labels = {b.label for b in at.button}
    assert "🔎 Investigate" in labels
    assert "Check connection" in labels
    assert len(at.text_area) >= 1  # free-text question box
```

- [ ] **Step 4: Verify no remaining bare `seller_agent` references inside the moved directory**

```bash
grep -rn "seller_agent" apps/seller_delivery_agent --include="*.py" | grep -v "__pycache__"
```

Expected: no output (the directory is now internally consistent — its own name is `seller_delivery_agent`, not `seller_agent`, everywhere it's referenced).

- [ ] **Step 5: Set up a venv and run the test suite**

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/seller_delivery_agent/requirements.txt
.venv/bin/python -m pytest apps/seller_delivery_agent/tests -q
```

Expected: all tests pass (this is the existing test suite, unmodified in behavior — only import paths changed). If `test_app_renders.py` fails with an import error, re-check Step 2's `sys.path` fix (a common mistake is only one `dirname()` instead of two).

- [ ] **Step 6: Manually sanity-check the Streamlit entrypoint**

```bash
.venv/bin/python -c "
import sys, os
sys.path.insert(0, os.getcwd())
sys.argv = ['streamlit', 'apps/seller_delivery_agent/app.py']
import ast
with open('apps/seller_delivery_agent/app.py') as f:
    ast.parse(f.read())
print('app.py parses OK')
"
.venv/bin/python -m py_compile apps/seller_delivery_agent/app.py && echo "app.py compiles OK"
```

Expected: both print their "OK" messages. (A full `streamlit run` requires live OAuth/MCP credentials and can't be exercised in this environment — the `test_app_renders.py` AppTest run in Step 5 is the real behavioral check, since Streamlit's `AppTest` harness executes the script the same way `streamlit run` does.)

- [ ] **Step 7: Commit**

```bash
git add .gitignore apps/seller_delivery_agent
git status --porcelain=v1
git commit -m "$(cat <<'EOF'
Relocate seller_agent to apps/seller_delivery_agent

Moves the Seller Delivery Intelligence Agent under apps/ so it sits
alongside the customer-experience-agent being added next. Only the
package's externally-facing absolute imports (app.py, tests/) needed
an apps. prefix — internal modules already use relative imports. Also
adds a repo-root .gitignore for .DS_Store/__pycache__/.venv, since none
existed before and the move would otherwise have committed .DS_Store.
EOF
)"
```

---

### Task 2: Copy customer-experience-agent from Craft-Dogfooding

**Context:** Copy `Craft-Dogfooding/apps/customer-experience-agent/` into this repo as fresh content — no `.git`, no history. The source repo lives at `/Users/abhishekpradhan/Workspace/repos/Craft-Dogfooding/apps/customer-experience-agent/` (verified to contain 18 files across `README.md`, `AGENT.md`, `config.py`, `craft_client.py`, `graph.py`, `main.py`, `nodes.py`, `state.py`, `pyproject.toml`, `Makefile`, `.env.template`, `.gitignore`, `scripts/get_token.py`, and `docs/decisions/` (4 files) + `docs/learnings/learnings.md`). No import-path changes are needed — this agent doesn't use repo-root-relative absolute imports (it's a flat package run via `uv run python main.py` from within its own directory), so its path within `apps/` being unchanged means it works exactly as it did in Craft-Dogfooding.

**Files:**
- Create: `apps/customer-experience-agent/` (entire directory tree, copied from source)

**Interfaces:**
- Produces: `apps/customer-experience-agent/` — a self-contained `uv`-managed Python project, unrelated to `apps/seller_delivery_agent`'s import namespace (no cross-dependencies between the two agents).

- [ ] **Step 1: Copy the directory tree, excluding .git**

```bash
mkdir -p apps/customer-experience-agent
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
  /Users/abhishekpradhan/Workspace/repos/Craft-Dogfooding/apps/customer-experience-agent/ \
  apps/customer-experience-agent/
find apps/customer-experience-agent -type f | sort
```

Expected output (18 files):
```
apps/customer-experience-agent/.env.template
apps/customer-experience-agent/.gitignore
apps/customer-experience-agent/AGENT.md
apps/customer-experience-agent/Makefile
apps/customer-experience-agent/README.md
apps/customer-experience-agent/config.py
apps/customer-experience-agent/craft_client.py
apps/customer-experience-agent/docs/decisions/001-database-selection.md
apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md
apps/customer-experience-agent/docs/decisions/003-generate-sql-over-raw-sql.md
apps/customer-experience-agent/docs/decisions/README.md
apps/customer-experience-agent/docs/learnings/learnings.md
apps/customer-experience-agent/graph.py
apps/customer-experience-agent/main.py
apps/customer-experience-agent/nodes.py
apps/customer-experience-agent/pyproject.toml
apps/customer-experience-agent/scripts/get_token.py
apps/customer-experience-agent/state.py
```

- [ ] **Step 2: Confirm no secrets or internal-only links were copied**

```bash
grep -rn "AIza\|sk-ant\|sk-[A-Za-z0-9]\{20,\}\|atlassian\|wiki" apps/customer-experience-agent/ 2>/dev/null
```

Expected: no output. (Already verified during design exploration — this step is a re-confirmation after the copy, not new discovery.)

- [ ] **Step 3: Stage and commit**

```bash
git add apps/customer-experience-agent
git status --porcelain=v1 | grep '^A' | wc -l
```

Expected: `18` (matches the file count from Step 1 — confirms nothing extra like `__pycache__` or `.venv` got staged).

```bash
git commit -m "$(cat <<'EOF'
Add customer-experience-agent from Craft-Dogfooding

Copies apps/customer-experience-agent/ as fresh content (no history)
from the Craft-Dogfooding repo, to sit alongside seller_delivery_agent
as a second CRAFT MCP demo agent. No code changes — the ADR-002
dangling reference fix is a separate commit.
EOF
)"
```

---

### Task 3: Fix the dangling f1-strategy-agent reference in ADR-002

**Context:** `apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md` mentions an "f1-strategy-agent" project that exists in neither this repo nor Craft-Dogfooding — it's a dangling cross-repo reference that would confuse a public reader. Rephrase the reasoning to stand on its own.

**Files:**
- Modify: `apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md`

- [ ] **Step 1: Edit the Decision and Consequences sections**

Current content (full file):

```markdown
# ADR-002: Use Gemini Flash for Engagement Synthesis

**Date:** 2026-06-25
**Status:** Accepted

## Context

Node 5 (compose_engagement) requires an LLM to synthesize structured data (purchase history, preferences, recommendations) into a personalized engagement brief. Options considered:
- Claude Sonnet 4.6 (Anthropic) — excellent at structured synthesis, already used in Claude Code harness
- Gemini 2.5 Flash (Google) — fast, cost-efficient, existing API key in project
- Gemini 2.5 Pro (Google) — higher quality but slower and more expensive

## Decision

Use **Gemini 2.5 Flash** (`gemini-2.5-flash`) for synthesis. This matches the pattern already established in the f1-strategy-agent in this same project, which uses the same Gemini API key and SDK.

## Consequences

**Positive:**
- Consistent with f1-strategy-agent — same SDK (`google-genai`), same key, same error handling patterns
- Flash is fast enough for a live demo (< 5s synthesis latency)
- Cost-efficient at scale vs Pro

**Negative / Trade-offs:**
- Flash may produce less nuanced personalization than Pro for complex customer profiles
- Locked to Google for LLM calls while CRAFT tools use Emergence AI's platform

**Neutral:**
- Model name is overridable via `GEMINI_SYNTHESIS_MODEL` env var — upgrading to Pro requires only a config change
```

Replace the `## Decision` and `## Consequences` sections with:

```markdown
## Decision

Use **Gemini 2.5 Flash** (`gemini-2.5-flash`) for synthesis.

## Consequences

**Positive:**
- Fast enough for a live demo (< 5s synthesis latency)
- Cost-efficient at scale vs Pro
- Uses the `google-genai` SDK, consistent with the CRAFT MCP integration's existing tooling

**Negative / Trade-offs:**
- Flash may produce less nuanced personalization than Pro for complex customer profiles
- Locked to Google for LLM calls while CRAFT tools use Emergence AI's platform

**Neutral:**
- Model name is overridable via `GEMINI_SYNTHESIS_MODEL` env var — upgrading to Pro requires only a config change
```

The `## Context` section (listing the three options considered) is unchanged.

- [ ] **Step 2: Verify the dangling reference is gone**

```bash
grep -n "f1-strategy-agent" apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md
git commit -m "$(cat <<'EOF'
Remove dangling f1-strategy-agent reference from ADR-002

f1-strategy-agent doesn't exist in this repo or its source
(Craft-Dogfooding) — the reference would confuse a public reader.
Restates the Gemini Flash rationale on its own merits.
EOF
)"
```

---

### Task 4: Clean up apps/seller_delivery_agent/README.md for public release

**Context:** The README has three issues for a public audience: two links to internal Confluence wiki pages, phrasing that says "internal `emergence.ai`", and stale `seller_agent`-prefixed paths/module names throughout (setup, run, outputs, project layout, troubleshooting sections) that need to become `apps/seller_delivery_agent`-prefixed.

**Files:**
- Modify: `apps/seller_delivery_agent/README.md`

- [ ] **Step 1: Remove the internal Confluence links (lines 13–15)**

Current:

```markdown
Built for the Emergence hackathon, riffing on the reference
[Customer Experience Intelligence Agent](https://emergenceai.atlassian.net/wiki/spaces/deveng/pages/1736933401/Customer+Experience+Intelligence+Agent)
and the [Nebius DEV Environment MCP Setup Guide](https://emergenceai.atlassian.net/wiki/spaces/Product/pages/1717895195/Nebius+DEV+Environment+MCP+Setup+Guide).
```

Replace with:

```markdown
Built for the Emergence hackathon, riffing on the reference
[Customer Experience Intelligence Agent](../customer-experience-agent/) in this same repo.
```

- [ ] **Step 2: Soften the internal-environment phrasing (line 44)**

Current:

```markdown
- **A DEV Keycloak / SSO account** for `runtime.dev.emergence.ai` — internal `emergence.ai`
  developers use *Sign in with Google*. First run opens a browser for OAuth (once).
```

Replace with:

```markdown
- **A Keycloak / SSO account** for `runtime.dev.emergence.ai` (Emergence's dev CRAFT
  environment). First run opens a browser for OAuth (once).
```

- [ ] **Step 3: Update Setup section path (line 56)**

Current:

```markdown
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r seller_agent/requirements.txt
```

Replace with:

```markdown
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r apps/seller_delivery_agent/requirements.txt
```

- [ ] **Step 4: Update Run section commands (lines 79, 93)**

Current (line 79):

```markdown
.venv/bin/streamlit run seller_agent/app.py
```

Replace with:

```markdown
.venv/bin/streamlit run apps/seller_delivery_agent/app.py
```

Current (line 93):

```markdown
.venv/bin/python -m seller_agent.agent [--seller-id <id>]
```

Replace with:

```markdown
.venv/bin/python -m apps.seller_delivery_agent.agent [--seller-id <id>]
```

- [ ] **Step 5: Update Outputs section path (line 105)**

Current:

```markdown
Each run writes to `seller_agent/runs/seller_{id_short}_{timestamp}/`:
```

Replace with:

```markdown
Each run writes to `apps/seller_delivery_agent/runs/seller_{id_short}_{timestamp}/`:
```

- [ ] **Step 6: Update auth section path (line 123)**

Current:

```markdown
`https://runtime.dev.emergence.ai/mcp` over streamable HTTP, authenticating via Keycloak OAuth
(`OAuthClientProvider`, static client `em-runtime-mcp`, callback port 9876). The token is cached to
`seller_agent/.token_cache.json` (gitignored) and reused on later runs; expiry re-opens the browser
automatically. Every request carries the required `X-Project-ID` header.
```

Replace with:

```markdown
`https://runtime.dev.emergence.ai/mcp` over streamable HTTP, authenticating via Keycloak OAuth
(`OAuthClientProvider`, static client `em-runtime-mcp`, callback port 9876). The token is cached to
`apps/seller_delivery_agent/.token_cache.json` (gitignored) and reused on later runs; expiry
re-opens the browser automatically. Every request carries the required `X-Project-ID` header.
```

- [ ] **Step 7: Update Troubleshooting section path (line 135)**

Current:

```markdown
- **`401 Unauthorized` / corrupted token**: `rm -f seller_agent/.token_cache.json` and re-run — the
  OAuth flow restarts.
```

Replace with:

```markdown
- **`401 Unauthorized` / corrupted token**: `rm -f apps/seller_delivery_agent/.token_cache.json` and
  re-run — the OAuth flow restarts.
```

- [ ] **Step 8: Update Project layout section (lines 148–161)**

Current:

```markdown
## Project layout

```
seller_agent/
  app.py            # Streamlit UI (thin wrapper over agent.run)
  agent.py          # orchestration (drives the LLM loop) + CLI + progress callback
  llm.py            # client factory (Vertex/ADC or API key) + the agentic tool-use loop
  tools.py          # Anthropic tool defs + ToolExecutor (bridges tool calls -> MCP session)
  prompts.py        # system prompt (goal + schema hint + 5-section output spec)
  craft_client.py   # MCP session + response parsers (backs the tools)
  craft_auth.py     # OAuth (FileTokenStorage + OAuthClientProvider)
  charts.py         # render a Plotly figure spec -> PNG
  config.py         # connection slug, project id, OAuth settings, default seller
  tests/            # pytest suite (run: .venv/bin/python -m pytest seller_agent/tests/ -q)
  runs/             # per-run output (gitignored)
```
```

Replace with:

```markdown
## Project layout

```
apps/seller_delivery_agent/
  app.py            # Streamlit UI (thin wrapper over agent.run)
  agent.py          # orchestration (drives the LLM loop) + CLI + progress callback
  llm.py            # client factory (Vertex/ADC or API key) + the agentic tool-use loop
  tools.py          # Anthropic tool defs + ToolExecutor (bridges tool calls -> MCP session)
  prompts.py        # system prompt (goal + schema hint + 5-section output spec)
  craft_client.py   # MCP session + response parsers (backs the tools)
  craft_auth.py     # OAuth (FileTokenStorage + OAuthClientProvider)
  charts.py         # render a Plotly figure spec -> PNG
  config.py         # connection slug, project id, OAuth settings, default seller
  tests/            # pytest suite (run: .venv/bin/python -m pytest apps/seller_delivery_agent/tests/ -q)
  runs/             # per-run output (gitignored)
```
```

- [ ] **Step 9: Verify no stale references remain**

```bash
grep -n "seller_agent[^_]" apps/seller_delivery_agent/README.md | grep -v "seller_delivery_agent"
grep -n "atlassian\|wiki" apps/seller_delivery_agent/README.md
```

Expected: both commands produce no output.

- [ ] **Step 10: Commit**

```bash
git add apps/seller_delivery_agent/README.md
git commit -m "$(cat <<'EOF'
Update seller_delivery_agent README for its new path and public release

Removes internal Confluence links and internal-environment phrasing,
and updates all seller_agent path/module references to
apps/seller_delivery_agent to match the Task 1 relocation.
EOF
)"
```

---

### Task 5: Rewrite the top-level README and add LICENSE

**Context:** The top-level `README.md` is currently a one-line stub (`# nebius-emergence-hackathon`). Replace it with a short intro plus a table linking to both agents, modeled on Craft-Dogfooding's top-level README style (short blurb per app + stack + link). Also add a root MIT `LICENSE`.

**Files:**
- Modify: `README.md`
- Create: `LICENSE`

- [ ] **Step 1: Replace README.md content**

Current (full file):

```markdown
# nebius-emergence-hackathon
```

Replace with:

```markdown
# nebius-emergence-hackathon

Two agentic demos built on the [CRAFT](https://emergence.ai) semantic data platform (em-runtime
MCP server), showing natural-language-driven analytics without hand-written SQL — one from the
seller side of a marketplace, one from the customer side.

---

## Agents

### [Seller Delivery Intelligence Agent](apps/seller_delivery_agent/)

Point it at an Olist marketplace seller and it produces a personalized improvement brief, built
entirely through an LLM-orchestrated tool-use loop — Claude decides which questions to ask and
when, with every query flowing through the CRAFT MCP server (no hand-written SQL anywhere).

**Stack:** Python · Claude (Anthropic) · CRAFT MCP (Text2SQL) · Streamlit
**Run:** `streamlit run apps/seller_delivery_agent/app.py`

See [apps/seller_delivery_agent/README.md](apps/seller_delivery_agent/README.md) for full setup and usage.

### [Customer Experience Intelligence Agent](apps/customer-experience-agent/)

Turns a customer ID into a personalized engagement brief — product recommendations, targeted
discount offers, and a CRM action trigger — all without writing SQL. The agent autonomously
discovers the TheLook E-Commerce schema via the CRAFT MCP platform, runs natural-language
queries across purchase history, behavioral events, and product catalog, then feeds all evidence
to Gemini to produce a ready-to-act markdown report.

**Stack:** Python · LangGraph · CRAFT MCP (Text2SQL) · Gemini
**Run:** `python main.py <customer_id>`

See [apps/customer-experience-agent/README.md](apps/customer-experience-agent/README.md) for full setup and usage.

---

## Contributing

Each agent lives under `apps/<agent-name>/` as a self-contained project with its own
`README.md` and environment configuration. Add new agents the same way.
```

- [ ] **Step 2: Add the LICENSE file**

Create `LICENSE` with the standard MIT license text:

```
MIT License

Copyright (c) 2026 Emergence AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Verify both links in the README resolve to real paths**

```bash
test -d apps/seller_delivery_agent && echo "seller_delivery_agent dir exists"
test -f apps/seller_delivery_agent/README.md && echo "seller_delivery_agent README exists"
test -d apps/customer-experience-agent && echo "customer-experience-agent dir exists"
test -f apps/customer-experience-agent/README.md && echo "customer-experience-agent README exists"
```

Expected: all four lines print.

- [ ] **Step 4: Commit**

```bash
git add README.md LICENSE
git commit -m "$(cat <<'EOF'
Rewrite top-level README and add MIT LICENSE for public release

Introduces the repo and links to both agents (seller_delivery_agent,
customer-experience-agent), replacing the one-line placeholder README.
EOF
)"
```

---

### Task 6: Final repo-wide verification pass

**Context:** A last sweep across the whole repo to catch anything the per-task verification steps missed — leftover secrets, leftover old package name, and confirmation that gitignored artifacts never got committed.

**Files:** None modified — this task only runs checks. If any check finds a problem, fix it in the relevant file and re-run the check before proceeding.

- [ ] **Step 1: Grep the whole repo for internal links, secrets, and dangling references**

```bash
grep -rn "atlassian\.net\|AIza[A-Za-z0-9_-]\{10,\}\|sk-ant-[A-Za-z0-9_-]\{10,\}\|f1-strategy-agent" \
  --include="*.md" --include="*.py" --include="*.txt" --include="*.toml" \
  apps/ README.md 2>/dev/null
```

Expected: no output.

- [ ] **Step 2: Grep for any remaining bare `seller_agent` (old package name) references**

```bash
grep -rln "seller_agent" apps/ README.md 2>/dev/null | grep -v "seller_delivery_agent"
```

Expected: no output. (Every hit for the substring `seller_agent` should actually be part of `seller_delivery_agent` — the grep filters those out, so any remaining line is a genuine stale reference.)

- [ ] **Step 3: Confirm gitignored artifacts were never staged**

```bash
git log --all --name-only --diff-filter=A -- '**/runs/*' '**/.token_cache.json' '**/__pycache__/*' '**/uv.lock' '**/.venv/*'
```

Expected: no output (nothing matching these patterns was ever added to any commit in this branch's history).

- [ ] **Step 4: Full test suite run, one more time, from a clean venv**

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r apps/seller_delivery_agent/requirements.txt
.venv/bin/python -m pytest apps/seller_delivery_agent/tests -q
```

Expected: all tests pass.

- [ ] **Step 5: Confirm final directory structure matches the design**

```bash
find apps -maxdepth 1 -type d
ls README.md LICENSE
```

Expected:
```
apps
apps/seller_delivery_agent
apps/customer-experience-agent
README.md
LICENSE
```

- [ ] **Step 6: Clean up the local venv (not part of the repo)**

```bash
rm -rf .venv
git status --porcelain=v1
```

Expected: `git status` shows no pending changes (everything from Tasks 1–5 was already committed; this task made no file changes, only ran checks).

---

## Summary of commits produced by this plan

1. `Relocate seller_agent to apps/seller_delivery_agent`
2. `Add customer-experience-agent from Craft-Dogfooding`
3. `Remove dangling f1-strategy-agent reference from ADR-002`
4. `Update seller_delivery_agent README for its new path and public release`
5. `Rewrite top-level README and add MIT LICENSE for public release`

(Task 6 produces no commit — verification only.)
