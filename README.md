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
