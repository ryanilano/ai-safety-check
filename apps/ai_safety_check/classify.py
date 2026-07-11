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
