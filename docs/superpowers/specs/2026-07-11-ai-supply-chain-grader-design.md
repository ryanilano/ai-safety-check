# LLM / AI Safety Check — Design

**Date:** 2026-07-11
**Status:** Draft for review
**Hackathon:** Nebius × Emergence — Scenario 5 (Software Supply Chain)
**Author:** Ryan Ilano (with Claude)

> ## 🔴🟡🟢 Red light, green light for self-hosted AI.
> **Would you run this on your laptop?** Every AI tool gets a nutrition label.

**Positioning layers:**
- **Lead hook:** "Red light, green light for self-hosted AI" — the branding *is* the 🔴🟡🟢 verdict.
- **Visceral question (demo opener):** "Would you run this on your laptop?" — your machine, your secrets.
- **Output format:** each tool gets a **nutrition-label** card.

> **Scope note (honesty to judges):** "safety" here = *is it safe to run this AI tool on your
> box* — deployment & supply-chain safety — **not** model alignment or content safety.

---

## 1. Concept

**LLM / AI Safety Check** — point it at the LLM agents, gateways, and inference servers people
`pip install` and `docker compose up`, and it returns a **🔴 RED / 🟡 YELLOW / 🟢 GREEN safety
verdict** for each, with the evidence and the fix.

It works over the hackathon's `DEPS_DEV_V1` + `GITHUB_REPOS` databases (a deps.dev / OSV
snapshot). The core loop:

> **Discover** the top AI/LLM tools in the snapshot (natural language) → **classify** what they
> actually are, why they mattered, and what makes them dangerous (NLP over free text) → **gate**
> each on data-provable safety signals into 🔴🟡🟢 → **validate** the verdicts against what
> actually happened after the snapshot (live web check) → **synthesize** the recurring dangers and
> how to fix them.

The output is a **Streamlit web app**: a traffic-light safety leaderboard, featured case studies, a
Common Dangers panel, and a **live natural-language ask-box** so judges can query the supply chain
in plain English.

### The narrative hook

The dataset is frozen at **~June/July 2023**. Rather than apologize for that, the demo weaponizes
it: the Safety Check verdicts use *only what was knowable in mid-2023*, then the app reveals — for
featured cases — the real post-2023 incident that followed. A **hindsight validation study**: proof
the gating predicts real-world blowups.

> "The data was already screaming in June 2023. Nobody listened. Here's what it cost."

**Hero example (verified in-data):** `significant-gravitas/autogpt` — the #1 AI project in the
snapshot at **164,209 stars** — is the autonomous-agent archetype that *by design* executes
model-generated code. The Safety Check is built to fail exactly this kind of tool loudly.

---

## 2. Goals & non-goals

### Goals
- Discover the top **10–20** LLM/AI tools in the snapshot via **natural-language** queries to CRAFT.
- **NLP classification** of each tool: what it *is* (agent / gateway / inference server / tutorial /
  false-positive), its safety-relevant capabilities (executes code? exposes a server? touches FS?),
  and a one-line **significance blurb** (what it was, why it mattered) — see §5 node 2.
- **Gate** each into **🔴 RED / 🟡 YELLOW / 🟢 GREEN** on transparent, data-backed safety signals.
- Every verdict is **traceable to the CRAFT query that produced it** (integrity rule).
- **3 featured case studies** validating the gating against post-2023 reality.
- A **Common Dangers** section: generalizable anti-patterns + remediation ("how to unscrew yourself").
- A **live NL ask-box** in the app (interactive Text2SQL).
- Ship as a **Streamlit web app**.
- Showcase the Nebius builder stack: CRAFT (NL→SQL + data), Nebius Token Factory / Nemotron
  (classification + narration), Tavily (hindsight web search).

### Non-goals (this hackathon build)
- **Not** model alignment / content safety — deployment & supply-chain safety only (see banner).
- **No deep forward dependency-tree grading for Python** — data doesn't support it (§3).
- **No runtime/config linting** (root, ports, capabilities) — not in the dataset; surfaced as
  Common Dangers *patterns*, not machine-gated.
- **No live/current data** — snapshot is fixed; live grading is Future Directions (§13).
- **No claim of CVE prediction** — the claim is "the risk profile was visible."

---

## 3. Data reality (load-bearing constraints)

Verified live against the hackathon project (`cb6bf32f…`, `nebius.emergence.ai`) during design:

| Finding | Evidence | Design consequence |
|---|---|---|
| **NL discovery works well** | "top AI/LLM projects by stars" → CRAFT wrote word-boundary regex itself; returned autogpt (164k) etc. | Discovery node + live ask-box are viable. |
| **Snapshot frozen ~June 2023** | `openai` latest 2023-06-07; `ollama` 2023-06-30; `mlflow` 2023-07-17 | Verdicts measure "knowable in 2023"; hindsight checks what followed. |
| **Discovery data is messy** | duplicates (`autogpt`/`auto-gpt`), tutorials (`ml-for-beginners`), false positives (`masscan`) | Needs an NLP **dedup + relevance-classification** step (§5 node 2). |
| **Repos ≠ packages** | `run-llama/llama_index` present in `PROJECTS` but PyPI `llama-index` absent from `PACKAGEVERSIONS` | A popular repo may not have a gradeable package/advisories; handle gracefully, disclose. |
| **Advisories rich & real** | `ADVISORIES` 30,212 rows; 6,371 CRITICAL/HIGH; real CVSS3 | CVE signal is strong. |
| **Severity column unusable** | `ADVISORIES.Severity` all `UNKNOWN`; real grades in **`GitHubSeverity`** | Gating uses `GitHubSeverity`. |
| **Forward dep trees: NPM & Maven only** | `DEPENDENCIES`/`DEPENDENCYGRAPHEDGES` have no PyPI | No forward-tree grade for Python. |
| **Reverse dependents cover PyPI & Cargo** | `DEPENDENTS` (has depth) | Blast-radius works for Python via reverse graph. |
| **Advisory linkage works** | `PACKAGEVERSIONS.Advisories` → `LATERAL FLATTEN` → join `ADVISORIES.SourceID` | mlflow → 13 advisories incl. 2× CVSS-10 (Appendix A). |

**Rate limits:** metadata 30/min, query execution 10/min per key — batch + cache; demo renders
from cache (§9).

---

## 4. Architecture

**Framework:** LangGraph fixed pipeline, cloning `apps/customer-experience-agent/` (LangGraph +
external OpenAI-style LLM + hand-rolled HTTP `CraftClient` + config-validated-at-import +
`runs/<id>/` trail).

**Reasoning LLM:** `nvidia/nemotron-3-super-120b-a12b` via **Nebius Token Factory**
(OpenAI-compatible: `base_url=https://api.tokenfactory.nebius.com/v1/`, `Bearer`). Covered by the
$50 Token Factory credit. CRAFT's `generate_sql` uses its own backend — no LLM key needed for data.

**Data / NLP-to-SQL:** CRAFT MCP tools (`generate_sql`→`execute_query`→`get_result_page`) against
`deps-dev-v1-cb6bf32f` and `github-repos-cb6bf32f` on `nebius.emergence.ai`.

**Hindsight web search:** Tavily ($25 credit). Enrichment only — never load-bearing.

**UI:** Streamlit (clones `apps/seller_delivery_agent/app.py`).

Rejected: Claude tool-loop (needs Anthropic key, not covered); pure Pydantic AI (kept as the
pattern for the ask-box's live tool-call).

---

## 5. Pipeline (LangGraph nodes)

```
discover_candidates → classify_and_filter → gate_tools → hindsight_check
    (CRAFT / NL)         (Nemotron NLP)      (CRAFT ×N)     (Tavily)
      → select_cases → synthesize_dangers → compose_report
        (agent+human)      (Nemotron)          (pure)

           [ live NL ask-box → generate_sql → execute_query ]  (interactive, app-side)
```

1. **`discover_candidates`** *(CRAFT / NL)* — natural-language queries surface the top AI/LLM tools
   by popularity (stars in `PROJECTS`, plus package presence in `PACKAGEVERSIONS`). Records
   **coverage**.
2. **`classify_and_filter`** *(Nemotron NLP)* — for each candidate: **dedup** near-identical names;
   classify **what it is** (agent / gateway / inference-server / vector-db / tutorial /
   false-positive) and **safety capabilities** (executes code? exposes server? filesystem access?).
   Drops tutorials/false-positives; keeps 10–20 real tools. Also writes a one-line **significance
   blurb** per surviving tool — grounded in its stars/classification, e.g.:
   - *AutoGPT (164k★): the tool that kicked off the autonomous-agent craze — the first "AI that
     does tasks for you." Also runs model-generated code on your machine by design.*
   - *llama.cpp: the project that made local LLM inference on consumer hardware real — the reason
     you can run models without the cloud.*
   This is what turns the leaderboard from a grade table into a story a non-expert can follow.
3. **`gate_tools`** *(CRAFT, fan-out)* — per tool, gather the safety signals (§6) and compute a
   🔴🟡🟢 verdict.
4. **`hindsight_check`** *(Tavily)* — one web lookup per tool → a "what happened next" tag + source URL.
5. **`select_cases`** *(agent-proposed, human-curated)* — rank by story score; user pins 3.
6. **`synthesize_dangers`** *(Nemotron)* — cluster findings into ranked Common Dangers + fixes.
7. **`compose_report`** *(pure)* — assemble the app data + chart; write `runs/<ts>/`.

**Live ask-box** *(app-side, interactive)* — free-text question → `generate_sql` → `execute_query`
→ show answer + the generated SQL. Independent of the batch pipeline.

Each node is a pure function with CRAFT + LLM clients bound via `functools.partial`.

---

## 6. Safety signals & gating

Each tool is gated on data-backed signals. NLP (§5 node 2) contributes the **capability** signal;
CRAFT contributes the rest.

| # | Signal | Question | Source | Contributes to verdict |
|---|---|---|---|---|
| 1 | **Known-CVE load** | Documented vulnerability on the books? | `PACKAGEVERSIONS.Advisories` → FLATTEN → `ADVISORIES` (`CVSS3Score`, `GitHubSeverity`) | any unpatched CRITICAL → **🔴 RED** |
| 2 | **Dangerous capability** *(NLP)* | Does it execute code / expose a server / touch FS by design? | Nemotron classification of repo + advisory text | executes-untrusted-code → at least **🟡 YELLOW**, **🔴 RED** if paired with CVEs |
| 3 | **Staleness / EOL drift** | Alive or coasting? | `PACKAGEVERSIONS.UpstreamPublishedAt` cadence | long gap → 🟡/🔴 |
| 4 | **Blast radius** | If compromised, who falls with it? | `DEPENDENTS` (PyPI/Cargo, depth); NPM reverse-lookup | high fan-in worsens verdict |
| 5 | **Upstream health** | Anyone home? | `PACKAGEVERSIONTOPROJECT` → `PROJECTS` (stars, issues, license) | abandoned / no repo link → 🟡 + flag |
| 6 | **Identity trust** | Is this the package you think? | cross-ecosystem name check + version/age heuristics | suspected squat → **🔴 RED** + callout |

**Verdict logic:** **worst-signal-wins** (compartmentalization thinking — your weakest wall is your
wall). Any 🔴 signal → overall **🔴 RED**; else any 🟡 → overall **🟡 YELLOW**; else **🟢 GREEN**.
The app shows the overall verdict *and* the per-signal breakdown with the query behind each.

**Honesty rules:**
- **Coverage disclosure** ("gated 6 of 14; 8 not in snapshot"; "repo popular but no package to grade").
- **Verdict ≠ prophecy** — verdicts measure July-2023 knowledge; hindsight (§7) checks outcomes,
  including "green-but-doomed" cases that expose the limit of CVE-counting → argues for defense-in-depth.

Thresholds tuned during implementation against the real distribution; the *structure* is approved
here. `gating.py` is pure (no network), unit-tested with fixtures.

---

## 7. Hindsight mechanics

### 7A. Universal shallow — "what happened next"
Per tool, one Tavily query; Nemotron distills returned sources to one tag **with a source URL**:
`⚠ 37 CVEs since snapshot` / `☠ actively exploited` / `✓ no known incidents` / `⚑ archived 2024`.

### 7B. Featured deep — 3 case studies
Full arc: *July-2023 data → the verdict we assigned → what actually happened (Tavily, multi-source)
→ remediation.*

**Selection — agent-proposed, human-curated:** agent ranks by story score (worst verdict + biggest
blast radius + strongest post-2023 signal), proposes a shortlist; **user pins the final 3**;
deterministic demo.

**Target archetypes:**
- **`mlflow`** — "the data was screaming": 13 advisories, 2× CVSS-10, verdict 🔴 RED, mass-exploited
  post-2023 (Appendix A).
- **`autogpt`** — "dangerous by design": 164k★, the tool that kicked off the autonomous-agent
  craze; executes model-generated code, so the capability signal reds it out even where a clean
  CVE sheet wouldn't.
- **A squat case** (`anthropic` on npm, 1 version) — "is this even the package you think?"

### Integrity / hallucination guard (critical)
- Tavily returns **real URLs + snippets**; Nemotron may only summarize those; **every hindsight
  claim carries its source URL** or it's omitted.
- **Provenance split:** in-snapshot claims cited from CRAFT; post-snapshot claims cited from Tavily.
  CVE IDs format-validated (`CVE-\d{4}-\d+`, `GHSA-…`).
- **Graceful degradation:** no Tavily / rate-limit / empty → report renders with verdicts + a
  "hindsight unavailable" note.

---

## 8. Common Dangers (synthesized tips)

`synthesize_dangers` (Nemotron) clusters the findings it *just produced* into patterns — grounded,
each = **pattern + evidence tools + remediation**:

- **⚠ Web UI bundled into the server process** — traversal/remote-file CVEs cluster in
  `<tool> server`/`<tool> ui`. *Seen in:* mlflow. *Unscrew:* never bind to `0.0.0.0`; auth the UI.
- **☠ Agents that execute model-generated code** — the capability *is* the vulnerability.
  *Seen in:* autogpt, agentgpt. *Unscrew:* sandbox/containerize; never run on a host with secrets.
- **☠ Zero CVEs ≠ safe** — squats carry clean sheets. *Seen in:* `anthropic` (npm). *Unscrew:*
  verify publisher + repo link; pin hashes.
- **⚑ "Recommended" but abandoned** — guides outlive maintainers. *Unscrew:* check last release +
  open-issue ratio first.

---

## 9. Output — Streamlit web app

Tiers, escalating data → stories → lessons, plus the interactive box:
1. **🔴🟡🟢 safety leaderboard** — every tool as a "nutrition label" row: traffic-light badge,
   category, the one-line significance blurb, the 6 signal chips, and the "what happened next"
   tag; click to expand each signal **and the query that produced it** (integrity made visible).
2. **Featured case studies** — 3 cards with the full hindsight arc + source links.
3. **Common Dangers** — ranked patterns + remediation.
4. **Live ask-box** — "Ask the supply chain" free-text field. Type a question in plain English,
   `generate_sql` answers it live, the app shows the answer **and the generated SQL**. Example
   prompts shown as clickable chips so it's obvious what to try:
   - *"What are the top 10 AI tools by stars, and what does their security / CVE-response look
     like over the trailing year (up to the snapshot)?"* — chains popularity ranking + temporal
     advisory analysis; the compound query that best shows off CRAFT's SQL generation.
   - *"Which AI agents can execute code but have unpatched critical CVEs?"*
   - *"Show me the most widely-depended-on LLM packages with no active maintainer."*
   - *"Compare mlflow's vulnerability count to how many projects depend on it."*

   (On "the past year": the snapshot freezes at ~July 2023, so temporal questions resolve against
   the trailing window inside the data — which reinforces the hindsight framing rather than
   fighting it.)
   This is the single most direct "watch NLP work" moment: unscripted, judge-driven, proves the
   system isn't replaying canned queries. Optional/cuttable if time runs short — the batch
   leaderboard stands on its own without it.

**Demo smoothness:** renders from a cached `runs/<ts>/` result by default; a **"re-run live"**
button and the ask-box show it working live within rate limits.

---

## 10. Module layout

New app: `apps/ai-safety-check/`

| Module | Responsibility | Reuse |
|---|---|---|
| `config.py` | CRAFT endpoint (nebius), Token Factory base-url+model, Tavily key, discovery seeds, gate thresholds, pinned case-study tools. Validated at import. | customer-agent |
| `craft_client.py` | MCP round-trip. | ~copy |
| `llm.py` | Nemotron via OpenAI client. Jobs: classify/dedup candidates, narrate, synthesize dangers. | new, thin |
| `tavily.py` | Hindsight lookups; graceful no-op without key. | new (~40 lines) |
| `queries.py` | Parameterized CRAFT questions (discover, CVE-flatten, staleness, blast-radius, health, identity). | new |
| `gating.py` | **Pure:** signals → 🔴🟡🟢, worst-wins. Unit-tested core. | new |
| `classify.py` | NLP: candidate dedup + what-is-it + capability tags (Nemotron). | new |
| `graph.py` | LangGraph wiring of §5 nodes. | customer-agent |
| `report.py` | Renders tiers + Plotly chart. | both apps |
| `app.py` | Streamlit UI (cached render, re-run button, live ask-box). | seller-agent |
| `main.py` | CLI entry. | customer-agent |

---

## 11. Config, artifacts, testing

**Config** (`config.py`, validated at import): CRAFT URL + connections + project id; Token Factory
base-url + model + key; Tavily key; discovery seeds; gate thresholds; pinned case-study tools.

**Run artifacts** (`runs/<ts>/`): `agent.log`, `sql_queries.txt` (audit trail — every verdict's
query), per-stage JSON, `report.md`, `leaderboard.png`.

**Testing:**
- `gating.py` — unit tests, no network ("unpatched CRITICAL → 🔴", "executes-code + CVE → 🔴",
  "clean + abandoned → 🟡").
- `classify.py`, CRAFT/LLM/Tavily — thin fakes + `monkeypatch` (seller-agent style).
- `app.py` — Streamlit `AppTest` smoke test from a cached fixture run.
- Demo run = integration test.

**Auth:** `config.py` points at `nebius.emergence.ai` (project `cb6bf32f…`) — working via the IDE
MCP OAuth flow used throughout design.

---

## 12. Deployment

- **Primary demo — local:** `streamlit run apps/ai-safety-check/app.py` on the laptop. Full live
  features (re-run, ask-box) work because the OAuth browser flow is available. Safest for the stage.
- **Hosted (optional, shareable):**
  - *Self-host on Proxmox + Cloudflare Tunnel (thematic favorite):* run the app in a Proxmox VM,
    expose it via Cloudflare Tunnel — stable HTTPS URL, no exposed ports, no inbound firewall
    holes. On-narrative: **a self-hosted-AI safety checker that is itself self-hosted.** Tunnel
    handles inbound (judges → app); the refresh-token grant handles outbound (app → CRAFT). Best
    story if the box is reliable for demo day.
  - *Cached-render deploy:* the app renders from a cached `runs/<ts>/` result with **no keys/auth**;
    live re-run + ask-box are disabled. Trivial to host anywhere (Streamlit Community Cloud, HF
    Spaces, Nebius AI Cloud, or the Proxmox VM). Good zero-risk leave-behind link.
  - *Full-live headless deploy:* host on **Nebius AI Cloud** ($50 AI Cloud credit; on-brand) or the
    Proxmox VM. Requires headless auth — see below.
- **Auth decision (affects every headless deploy):** use the **Keycloak refresh-token grant** (the
  `customer-experience-agent` pattern), **not** the interactive `localhost:9876` PKCE callback
  (`seller_delivery_agent` / `mcp_starter.py`). Browser login once → refresh token stored as a
  secret → app runs headless with full live CRAFT access. Building this from the start keeps both
  local and hosted-live options open with no rework.
- **Secrets on a host:** Token Factory key, Tavily key, Keycloak refresh token → env/secret store,
  never committed. `config.py` reads them; validated at import.

---

## 13. Future Directions (out of scope)

Proof-of-concept for a methodology (discover → classify → gate on knowable signals → validate
against outcomes) that currently runs on a frozen snapshot. Point it at live data →

- **CRAFT over live deps.dev + OSV** → a *current* pre-adoption gate ("safe to install today?").
- **Point at your own SBOM / lockfiles** → continuous monitoring; alert when a tool's verdict drops.
- **Defensive red-team recon (authorized only)** → blast-radius + identity-trust signals also map an
  attacker's softest targets; strictly authorized security research.

**Optional stretch this hackathon:** a `--audit <package>` flag running the same traffic-light
pipeline on one ad-hoc tool. Same code, different entry point.

---

## Appendix A — Verified evidence

### mlflow advisories in-snapshot
`PACKAGEVERSIONS`(Name='mlflow') → `LATERAL FLATTEN(Advisories)` → join `ADVISORIES` → 13 rows incl.:

| Advisory | CVSS3 | Severity | Title |
|---|---|---|---|
| GHSA-fmxj-6h9g-6vw3 | 10.0 | CRITICAL | MLflow Path Traversal |
| GHSA-x422-6qhv-p29g (CVE-2023-1177) | 10.0 | CRITICAL | Relative path traversal in mlflow |
| GHSA-wjq3-7jxx-whj9 | 9.8 | CRITICAL | mlflow Path Traversal |
| GHSA-xg73-94fp-g449 | 9.8 | CRITICAL | Remote file access in `mlflow server`/`ui` CLIs |
| … +9 more (incl. PYSEC-2023-28/68/69/70) | | | |

### Top AI/LLM projects in-snapshot (NL discovery, by stars)
"top AI/LLM projects by stars" → CRAFT auto-generated word-boundary regex → returned:

| Project | Stars | Note |
|---|---|---|
| significant-gravitas/autogpt | 164,209 | autonomous agent (hero case) |
| microsoft/ml-for-beginners | 54,077 | tutorial — NLP filter should drop |
| run-llama/llama_index | 33,515 | repo present; PyPI package absent |
| stability-ai/stablediffusion | 31,365 | |
| reworkd/agentgpt | 30,673 | autonomous agent |
| robertdavidgraham/masscan | 22,987 | false positive — NLP filter should drop |

Demonstrates both that NL discovery works *and* why the NLP classify/filter step (§5 node 2) is
required.
