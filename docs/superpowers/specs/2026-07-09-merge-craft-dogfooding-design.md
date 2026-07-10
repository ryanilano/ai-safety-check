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
- Rename and relocate `seller_agent/` → `apps/seller_delivery_agent/`, nested under `apps/`
  alongside the customer agent.
- Update both agents' READMEs for correctness (renamed paths, module names) and to remove
  internal-only references (Confluence links, dangling cross-repo mentions).
- Rewrite the top-level `README.md` to introduce the repo and link to both agents.
- Add a root `LICENSE` (MIT).

**Out of scope (explicitly deferred):**
- No behavioral changes to either agent, and no refactors beyond the import-path updates that
  are mechanically required by the move to `apps/` (see Mechanics below).
- No change to `seller_delivery_agent/config.py`'s hardcoded `PROJECT_ID` / dev-environment URLs
  — these are being kept as-is.
- No CI/CD setup.
- No preservation of `Craft-Dogfooding`'s git history — files are copied as fresh content.

## Final structure

```
nebius-emergence-hackathon/
├── README.md                          (rewritten: intro + links to both agents)
├── LICENSE                            (new: MIT)
└── apps/
    ├── seller_delivery_agent/         (renamed + relocated from seller_agent/)
    │   ├── README.md                  (updated: new name/path, internal links removed)
    │   ├── agent.py, app.py, config.py, craft_client.py, craft_auth.py,
    │   │   llm.py, prompts.py, tools.py, charts.py, __init__.py
    │   ├── requirements.txt
    │   ├── tests/
    │   └── .gitignore
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
- Both agents now live under `apps/`, giving the repo one clear top-level convention for
  "a demo app lives here" — matching the nesting Craft-Dogfooding already established and
  leaving room for future apps.
- `seller_delivery_agent` keeps a valid Python-identifier name (no hyphens), since it's used as
  an importable package, not just a directory. The new name matches its README title
  ("Seller Delivery Intelligence Agent").

## Mechanics

1. **Rename + relocate seller agent:** `git mv seller_agent apps/seller_delivery_agent`.
   This is not a pure directory move — the package is imported by absolute dotted path in
   several places, and those paths gain an `apps.` prefix:
   - `apps/seller_delivery_agent/app.py`: `from seller_agent import config` →
     `from apps.seller_delivery_agent import config` (and the sibling `agent`/`craft_auth`
     imports on the following two lines). The `sys.path.insert(0, ...)` call that puts the repo
     root on `sys.path` needs one more `os.path.dirname(...)` wrap, since `app.py` is now two
     directories below the repo root instead of one.
   - All 8 files under `apps/seller_delivery_agent/tests/` that write
     `from seller_agent import ...` / `from seller_agent.X import ...` /
     `import seller_agent.X as ...` → same imports with an `apps.` prefix.
   - `apps/seller_delivery_agent/tests/test_app_renders.py`: `AppTest.from_file("seller_agent/app.py", ...)`
     → `AppTest.from_file("apps/seller_delivery_agent/app.py", ...)`.
   - Internal package files (`agent.py`, `llm.py`, `tools.py`, etc.) already use relative
     imports (`from .craft_client import ...`) and are unaffected by the move.
   - Fix the same old-name/path references in its own README (see Documentation changes below).
2. **Copy customer-experience-agent:** copy
   `Craft-Dogfooding/apps/customer-experience-agent/` into
   `nebius-emergence-hackathon/apps/customer-experience-agent/` as new content (no `.git`,
   no history — a plain recursive copy, not a subtree/filter-branch). No import changes needed;
   its path within `apps/` is unchanged and it doesn't use repo-root-relative absolute imports.
3. **Fix dangling reference:** ADR-002
   (`apps/customer-experience-agent/docs/decisions/002-llm-provider-selection.md`) mentions an
   "f1-strategy-agent" that doesn't exist in either repo. Rephrase the "Consistent with
   f1-strategy-agent" positive point to state the SDK/pattern choice (`google-genai`, existing
   Gemini key) on its own merits, without the dangling cross-repo reference.

## Documentation changes

- **`apps/seller_delivery_agent/README.md`:**
  - Remove the two internal Confluence links (Customer Experience Intelligence Agent wiki page,
    Nebius DEV Environment MCP Setup Guide).
  - Soften/remove the "internal `emergence.ai`" phrasing in the prerequisites section.
  - Update all `seller_agent` path and module references to `apps/seller_delivery_agent`
    (setup/run commands, project layout section, outputs section, troubleshooting section) —
    e.g. `streamlit run seller_agent/app.py` → `streamlit run apps/seller_delivery_agent/app.py`,
    `python -m seller_agent.agent` → `python -m apps.seller_delivery_agent.agent`.
- **Top-level `README.md`:** replace the current one-line stub with a short repo introduction
  (two CRAFT/em-runtime MCP demo agents) and a table linking to both agents' subdirectory
  READMEs, modeled on Craft-Dogfooding's top-level README style (short blurb + stack + link per
  app).
- **`apps/customer-experience-agent/*`:** no changes except the ADR-002 edit above. Its README,
  `AGENT.md`, `.env.template`, and learnings doc already contain no internal-only links (verified
  during exploration) and are copied verbatim.
- **`LICENSE`:** add a standard MIT license at the repo root.

## Verification

- After the rename/relocation, run `seller_delivery_agent`'s test suite
  (`python -m pytest apps/seller_delivery_agent/tests -q`) to confirm the new `apps.` import
  paths resolve correctly.
- Manually sanity-check `streamlit run apps/seller_delivery_agent/app.py` starts without an
  import error (the `sys.path` depth fix is easy to get off-by-one).
- Grep both trees for leftover internal links/secrets (`atlassian`, `wiki`, `internal`,
  `AIza`, `sk-ant`, `sk-`, hardcoded `Bearer` tokens) before committing, to confirm nothing
  sensitive is left in what's being made public.
- Grep for any remaining bare `seller_agent` references (old package name) across the repo to
  catch anything the mechanics list above missed.
- Confirm `.gitignore` patterns from both agents (`__pycache__/`, `*.pyc`, `runs/`, `.env`,
  `.token_cache.json`, `.venv/`, `uv.lock`) are preserved and that no ignored artifacts
  (e.g. `apps/seller_delivery_agent/runs/`, `.token_cache.json`) get accidentally committed
  during the move.

## Risks / edge cases

- **`uv.lock` in `.gitignore`:** Craft-Dogfooding's `.gitignore` for customer-experience-agent
  ignores `uv.lock`. This is copied as-is (out of scope to change); it means dependency
  resolution isn't pinned to exact transitive versions for a public clone, matching the
  source repo's existing behavior.
- **Two different dependency/tooling styles:** `seller_delivery_agent` uses `pip` +
  `requirements.txt`; `customer-experience-agent` uses `uv` + `pyproject.toml`. This is an
  existing inconsistency inherited from the two source repos and is left as-is per the
  "docs + hygiene only" scope — not unified in this pass.
