"""LangGraph pipeline nodes. Each returns a partial-state dict."""
import json
import re
from datetime import datetime, timezone

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
            if len(row) > 1:
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
