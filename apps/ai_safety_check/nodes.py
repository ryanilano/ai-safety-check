"""LangGraph pipeline nodes. Each returns a partial-state dict.

Row parsing is COLUMN-NAME-AWARE: CRAFT `generate_sql` decides its own column
aliases and ordering, so we locate cells by fuzzy column-name match against the
returned `columns` list rather than by fixed position. Column names below were
verified against live CRAFT output for each query in queries.py.
"""
import json
import re
from datetime import datetime, timezone

from . import config, gating, classify, queries


def _rows(result: dict) -> list[list]:
    return result.get("rows", []) if isinstance(result, dict) else []


def _columns(result: dict) -> list[str]:
    return [str(c) for c in result.get("columns", [])] if isinstance(result, dict) else []


def _find_col(columns: list[str], *needles: str):
    """Index of the first column whose lowercased name contains any needle, else None."""
    low = [c.lower() for c in columns]
    for needle in needles:
        for i, name in enumerate(low):
            if needle in name:
                return i
    return None


def _cell(row: list, columns: list[str], *needles: str, default=None):
    i = _find_col(columns, *needles)
    if i is None or i >= len(row):
        return default
    return row[i]


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def discover_candidates_node(state, craft) -> dict:
    # PROJECTS (stars/forks/issues) lives in the deps-dev connection, not github-repos.
    q = queries.discover_top_ai_projects(30)
    result, sql = await craft.nl_query(q, config.DEPS_CONNECTION,
                                        config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
    cols = _columns(result)
    cands = []
    for row in _rows(result):
        name_cell = _cell(row, cols, "projectname", "name", "repo")
        stars = _to_int(_cell(row, cols, "star", "watch"))
        if name_cell is None:
            continue
        name = str(name_cell).split("/")[-1].strip()
        if name:
            cands.append({"name": name, "stars": stars})
    return {"candidates": cands, "coverage": {"discovered": len(cands)},
            "sql_log": state.get("sql_log", []) + [("discover", sql)]}


async def classify_node(state, llm) -> dict:
    cands = state.get("candidates", [])
    prompt = classify.build_classify_prompt(cands)
    raw = llm.complete(prompt, json_mode=True)
    try:
        parsed = classify.parse_classification(raw)
        kept = classify.filter_real_tools(parsed, config.MAX_TOOLS)
    except Exception:
        kept = []
    stars_by = {c["name"]: c.get("stars") for c in cands}
    tools = [{"name": t["name"], "system": "PYPI", "category": t["category"],
              "capabilities": t["capabilities"], "significance": t["significance"],
              "stars": stars_by.get(t["name"]), "sql_log": []} for t in kept]
    return {"tools": tools}


async def gate_node(state, craft) -> dict:
    graded = []
    errors = list(state.get("errors", []))
    for tool in state.get("tools", []):
        log = list(tool.get("sql_log", []))
        try:
            # --- CVE load (deps-dev ADVISORIES) ---
            r, sql = await craft.nl_query(queries.advisories_for(tool["name"]),
                                          config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
            log.append(("advisories:" + tool["name"], sql))
            cols = _columns(r)
            counts = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0}
            worst = None
            for row in _rows(r):
                sev = str(_cell(row, cols, "sever", default="")).upper()
                if sev in counts:
                    counts[sev] += 1
                cv = _to_float(_cell(row, cols, "cvss", "score"))
                if cv is not None:
                    worst = cv if worst is None else max(worst, cv)
            cve = gating.grade_cve(counts, worst)
            has_cve = cve["verdict"] in ("RED", "YELLOW")

            # --- Dangerous capability (from NLP classification) ---
            cap = gating.grade_capability(tool.get("capabilities", []), has_cve)

            # --- Staleness (deps-dev PACKAGEVERSIONS) ---
            r, sql = await craft.nl_query(queries.staleness_for(tool["name"], tool["system"]),
                                          config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
            log.append(("staleness:" + tool["name"], sql))
            cols = _columns(r)
            first = _rows(r)[0] if _rows(r) else []
            days = _days_since(_cell(first, cols, "publish", "upstream", "date"))
            stale = gating.grade_staleness(days)

            # --- Blast radius (deps-dev DEPENDENTS) ---
            r, sql = await craft.nl_query(queries.dependents_for(tool["name"], tool["system"]),
                                          config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
            log.append(("dependents:" + tool["name"], sql))
            cols = _columns(r)
            first = _rows(r)[0] if _rows(r) else []
            blast = gating.grade_blast(_to_int(_cell(first, cols, "depend", "count")))

            # --- Upstream health (deps-dev PROJECTS) ---
            r, sql = await craft.nl_query(queries.health_for(tool["name"]),
                                          config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
            log.append(("health:" + tool["name"], sql))
            cols = _columns(r)
            rows = _rows(r)
            if rows:
                stars = _to_int(_cell(rows[0], cols, "star", "watch"))
                if stars is None:
                    stars = tool.get("stars")
                issues = _to_int(_cell(rows[0], cols, "issue"))
                health = gating.grade_health(stars, issues, True)
            else:
                health = gating.grade_health(tool.get("stars"), None, False)

            # --- Identity trust (deps-dev PACKAGEVERSIONS across systems) ---
            r, sql = await craft.nl_query(queries.identity_check(tool["name"]),
                                          config.DEPS_CONNECTION, config.DEPS_SCHEMA_NAME, config.DEPS_SCHEMA_FQN)
            log.append(("identity:" + tool["name"], sql))
            identity = gating.grade_identity(_looks_like_squat(r))

            signals = {"cve": cve, "capability": cap, "staleness": stale,
                       "blast": blast, "health": health, "identity": identity}
            graded.append({**tool, "signals": signals,
                           "verdict": gating.composite(signals), "sql_log": log})
        except Exception as exc:
            errors.append(f"gate failed for {tool['name']}: {exc}")
            graded.append({**tool, "signals": {"error": {"verdict": "YELLOW",
                           "detail": f"gate failed: {exc}"}},
                           "verdict": "YELLOW", "sql_log": log})
    return {"tools": graded, "errors": errors}


def _days_since(date_str):
    if not date_str:
        return None
    try:
        d = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    # Snapshot horizon is fixed at 2023-07-31 for "days since" purposes.
    horizon = datetime(2023, 7, 31, tzinfo=timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (horizon - d).days


def _looks_like_squat(r) -> bool:
    """Identity query returns one row per ecosystem (System, version-count), most
    with 0. Squat-suspicious = the package is present (>=1 version) in exactly ONE
    ecosystem and that presence is a lone version — the classic single-version
    vendor-name squat (e.g. `anthropic` on npm, 1 version). Refined during tuning."""
    cols = _columns(r)
    sys_i = _find_col(cols, "system")
    cnt_i = _find_col(cols, "count", "version")
    if sys_i is None or cnt_i is None:
        return False
    present = []
    for row in _rows(r):
        n = _to_int(row[cnt_i]) if cnt_i < len(row) else None
        if n and n >= 1:
            present.append(n)
    return len(present) == 1 and present[0] <= 1


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
        f"cve={t['signals'].get('cve', {}).get('detail', 'n/a')}"
        for t in tools if t.get("signals"))
    prompt = ("From these graded AI tools, identify the 3-5 recurring supply-chain danger PATTERNS. "
              "Return a JSON array of objects with keys 'pattern', 'seen_in' (list of tool names), "
              "'remediation' (one sentence). Return ONLY JSON.\n\n" + summary)
    try:
        raw = llm.complete(prompt, json_mode=True)
        dangers = json.loads(_strip_fence(raw))
    except Exception:
        dangers = []
    return {"dangers": dangers}


def _strip_fence(raw: str) -> str:
    t = re.sub(r"^```(?:json)?", "", raw.strip()).strip()
    t = re.sub(r"```$", "", t).strip()
    s, e = t.find("["), t.rfind("]")
    return t[s:e + 1] if s != -1 else t
