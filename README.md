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
.venv/bin/python -m apps.seller_delivery_agent.agent [--seller-id <id>]
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
