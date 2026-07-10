# nebius-emergence-hackathon

Two agentic demos built on the [CRAFT](https://emergence.ai) semantic data platform (CRAFT MCP
server), showing natural-language-driven analytics without hand-written SQL — one from the
seller side of a marketplace, one from the customer side.

---

## Agents

### [Seller Delivery Intelligence Agent](apps/seller_delivery_agent/)

Ask a free-text question about an Olist marketplace's data and it investigates like a root-cause
analyst, built entirely through an LLM-orchestrated tool-use loop — Claude decides which schema
to explore, which questions to ask, and when, with every query flowing through the CRAFT MCP
server (no hand-written SQL anywhere).

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

## Starter Script

### [`mcp_starter.py`](mcp_starter.py)

A single-file, dependency-light hand-off template for hackathon participants who want to talk to
the CRAFT MCP server directly from their own Python, without adopting either agent's framework.
It walks through the whole round-trip: OAuth 2.1 + PKCE (Keycloak SSO, browser opens once),
`list_tools` to discover the server's capabilities, `generate_sql` to turn a natural-language
question into SQL, and `execute_query` to run it and get rows back.

**Stack:** Python (single file, `uv`-run — no venv or `pip install` needed) · CRAFT MCP

**Run:**
```bash
uv run mcp_starter.py                # ask the default question, print the SQL + rows
uv run mcp_starter.py --list-tools   # just dump the MCP tool catalogue and exit
uv run mcp_starter.py --reset-auth   # force a fresh SSO login
```

Edit the `CONFIG` block at the top of the file (`MCP_URL`, `PROJECT_ID`, `CONNECTION`,
`SCHEMA_NAME`, `QUESTION`) for your environment — everything below it is OAuth boilerplate you
can leave as-is. The file's default `MCP_URL` points at a different CRAFT cluster than the two
agents above (`runtime.dev.emergence.ai`) — both are real CRAFT MCP deployments; ask your host
which one your hackathon account is provisioned for and point `MCP_URL`/`PROJECT_ID` there.

---

## Quick Start

Each agent is a self-contained project with its own dependencies and environment config — see
each agent's own README for full detail. Short version:

### Seller Delivery Intelligence Agent

```bash
# from the repo root
python3 -m venv .venv
.venv/bin/pip install -r apps/seller_delivery_agent/requirements.txt

# set Claude auth (pick one)
export ANTHROPIC_VERTEX_PROJECT_ID=<gcp-project>   # + gcloud auth application-default login
export CLOUD_ML_REGION=global
# — or —
export ANTHROPIC_API_KEY=sk-ant-...

# Web UI (recommended for a demo)
.venv/bin/streamlit run apps/seller_delivery_agent/app.py

# — or CLI —
.venv/bin/python -m apps.seller_delivery_agent.agent ["<question>"]
```

First run opens a browser for Keycloak/SSO login against `runtime.dev.emergence.ai` (one-time
OAuth). The CRAFT connection is preconfigured — you only need Claude access and to complete OAuth.

### Customer Experience Intelligence Agent

Uses `uv` instead of `pip`, and needs its own `.env`:

```bash
cd apps/customer-experience-agent
uv sync
cp .env.template .env
# edit .env: set MCP_URL, PROJECT_ID, KEYCLOAK_URL, DATASOURCE_ID, CONNECTION_NAME,
# SCHEMA_NAME, SCHEMA_FQN, GEMINI_API_KEY

# one-time: get a Keycloak refresh token (opens browser for Google SSO)
uv run python scripts/get_token.py
# paste the printed KEYCLOAK_REFRESH_TOKEN=... into .env

# run it
python main.py 12345          # or any customer ID
# — or —
make run CUSTOMER_ID=12345
```

**Key differences:** the seller agent needs Claude access (Vertex or Anthropic API key) and talks
to Brazilian e-commerce data via a preconfigured CRAFT connection; the customer agent needs a
Gemini API key and its own fully-filled `.env` (CRAFT connection details plus the Gemini key)
before it can talk to TheLook e-commerce data. Both authenticate to the same CRAFT MCP platform
via Keycloak.

---

## Contributing

Each agent lives under `apps/<agent-name>/` as a self-contained project with its own
`README.md` and environment configuration. Add new agents the same way.
