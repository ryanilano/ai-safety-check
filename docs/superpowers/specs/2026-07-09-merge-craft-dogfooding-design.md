# Design: Merge Craft-Dogfooding's customer-experience-agent into nebius-emergence-hackathon, prep repo for public release

**Date:** 2026-07-09
**Status:** Approved

## Context

`nebius-emergence-hackathon` currently contains one agent, `seller_agent/` (a Seller Delivery
Intelligence Agent built on Claude + the em-runtime/CRAFT MCP server + Streamlit). A second,
related agent — the Customer Experience Intelligence Agent (LangGraph + Gemini + CRAFT MCP) —
lives in a separate repo, `Craft-Dogfooding`, at `apps/customer-experience-agent/`.

The repo is being made public. Goal: bring the customer-experience-agent into this repo
alongside the seller agent as a clear sibling demo, and clean up both agents' docs/repo
hygiene for a public audience — without changing either agent's runtime behavior.

## Scope

**In scope:**
- Copy `apps/customer-experience-agent/` from `Craft-Dogfooding` into this repo, preserving its
  `apps/` nesting.
- Rename `seller_agent/` → `seller_delivery_agent/` at the repo root (not nested under `apps/`).
- Update both agents' READMEs for correctness (renamed paths, module names) and to remove
  internal-only references (Confluence links, dangling cross-repo mentions).
- Rewrite the top-level `README.md` to introduce the repo and link to both agents.
- Add a root `LICENSE` (MIT).

**Out of scope (explicitly deferred):**
- No code refactors, dependency upgrades, or behavioral changes to either agent.
- No change to `seller_delivery_agent/config.py`'s hardcoded `PROJECT_ID` / dev-environment URLs
  — these are being kept as-is.
- No CI/CD setup.
- No preservation of `Craft-Dogfooding`'s git history — files are copied as fresh content.

## Final structure

```
nebius-emergence-hackathon/
├── README.md                          (rewritten: intro + links to both agents)
├── LICENSE                            (new: MIT)
├── seller_delivery_agent/             (renamed from seller_agent/)
│   ├── README.md                      (updated: new name, internal links removed)
│   ├── agent.py, app.py, config.py, craft_client.py, craft_auth.py,
│   │   llm.py, prompts.py, tools.py, charts.py, __init__.py
│   ├── requirements.txt
│   ├── tests/
│   └── .gitignore
└── apps/
    └── customer-experience-agent/     (copied from Craft-Dogfooding, path unchanged)
        ├── README.md, AGENT.md
        ├── config.py, craft_client.py, graph.py, main.py, nodes.py, state.py
        ├── pyproject.toml, Makefile, .env.template, .gitignore
        ├── scripts/get_token.py
        └── docs/
            ├── decisions/  (3 ADRs + index; ADR-002 edited, see below)
            └── learnings/learnings.md
```

**Rationale for the split naming/nesting:**
- `seller_delivery_agent` stays a flat, top-level, importable Python package (valid identifier,
  no hyphens) — avoids touching its internal `from seller_agent import ...` style imports beyond
  the rename itself, and the new name matches its README title ("Seller Delivery Intelligence
  Agent").
- `apps/customer-experience-agent/` keeps the nesting convention it already used in
  Craft-Dogfooding, which anticipates more apps being added under `apps/` later.

## Mechanics

1. **Rename seller agent:** `git mv seller_agent seller_delivery_agent`. Fix the one place its
   own README references its old name/paths (e.g. `seller_agent/runs/...` →
   `seller_delivery_agent/runs/...`, `python -m seller_agent.agent` →
   `python -m seller_delivery_agent.agent`). No source files outside the package reference the
   old name, so no other import changes are needed.
2. **Copy customer-experience-agent:** copy
   `Craft-Dogfooding/apps/customer-experience-agent/` into
   `nebius-emergence-hackathon/apps/customer-experience-agent/` as new content (no `.git`,
   no history — a plain recursive copy, not a subtree/filter-branch).
3. **Fix dangling reference:** ADR-002
   (`apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md`) mentions an
   "f1-strategy-agent" that doesn't exist in either repo. Rephrase the "Consistent with
   f1-strategy-agent" positive point to state the SDK/pattern choice (`google-genai`, existing
   Gemini key) on its own merits, without the dangling cross-repo reference.

## Documentation changes

- **`seller_delivery_agent/README.md`:**
  - Remove the two internal Confluence links (Customer Experience Intelligence Agent wiki page,
    Nebius DEV Environment MCP Setup Guide).
  - Soften/remove the "internal `emergence.ai`" phrasing in the prerequisites section.
  - Update all `seller_agent` path and module references to `seller_delivery_agent`
    (project layout section, run commands, outputs section, troubleshooting section).
- **Top-level `README.md`:** replace the current one-line stub with a short repo introduction
  (two CRAFT/em-runtime MCP demo agents) and a table linking to both agents' subdirectory
  READMEs, modeled on Craft-Dogfooding's top-level README style (short blurb + stack + link per
  app).
- **`apps/customer-experience-agent/*`:** no changes except the ADR-002 edit above. Its README,
  `AGENT.md`, `.env.template`, and learnings doc already contain no internal-only links (verified
  during exploration) and are copied verbatim.
- **`LICENSE`:** add a standard MIT license at the repo root.

## Verification

- After the rename, run `seller_delivery_agent`'s test suite
  (`python -m pytest seller_delivery_agent/tests -q`) to confirm nothing broke from the
  directory rename.
- Grep both trees for leftover internal links/secrets (`atlassian`, `wiki`, `internal`,
  `AIza`, `sk-ant`, `sk-`, hardcoded `Bearer` tokens) before committing, to confirm nothing
  sensitive is left in what's being made public.
- Confirm `.gitignore` patterns from both agents (`__pycache__/`, `*.pyc`, `runs/`, `.env`,
  `.token_cache.json`, `.venv/`, `uv.lock`) are preserved and that no ignored artifacts
  (e.g. `seller_agent/runs/`, `.token_cache.json`) get accidentally committed during the move.

## Risks / edge cases

- **`uv.lock` in `.gitignore`:** Craft-Dogfooding's `.gitignore` for customer-experience-agent
  ignores `uv.lock`. This is copied as-is (out of scope to change); it means dependency
  resolution isn't pinned to exact transitive versions for a public clone, matching the
  source repo's existing behavior.
- **Two different dependency/tooling styles:** `seller_delivery_agent` uses `pip` +
  `requirements.txt`; `customer-experience-agent` uses `uv` + `pyproject.toml`. This is an
  existing inconsistency inherited from the two source repos and is left as-is per the
  "docs + hygiene only" scope — not unified in this pass.
