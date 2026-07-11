"""Pure safety-signal grading. No network, no I/O. Fully unit-tested."""

_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}


def _worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: _RANK[v])


def grade_cve(counts: dict, worst_cvss: float | None) -> dict:
    crit = counts.get("CRITICAL", 0)
    high = counts.get("HIGH", 0)
    mod = counts.get("MODERATE", 0)
    if crit > 0:
        verdict = "RED"
    elif high > 0:
        verdict = "YELLOW"
    else:
        verdict = "GREEN"
    detail = f"{crit} CRITICAL / {high} HIGH / {mod} MODERATE advisories"
    if worst_cvss is not None:
        detail += f"; worst CVSS {worst_cvss}"
    return {"verdict": verdict, "detail": detail, "worst_cvss": worst_cvss, "counts": counts}


def grade_capability(flags: list[str], has_cve: bool) -> dict:
    dangerous = "executes_code" in flags
    if dangerous and has_cve:
        verdict = "RED"
    elif dangerous or "exposes_server" in flags:
        verdict = "YELLOW"
    else:
        verdict = "GREEN"
    detail = "capabilities: " + (", ".join(flags) if flags else "none detected")
    return {"verdict": verdict, "detail": detail, "flags": flags}


def grade_staleness(days_since_last_release: int | None) -> dict:
    d = days_since_last_release
    if d is None:
        verdict, detail = "YELLOW", "no release date available"
    elif d > 730:
        verdict, detail = "RED", f"last release {d} days ago (>2y)"
    elif d > 365:
        verdict, detail = "YELLOW", f"last release {d} days ago (>1y)"
    else:
        verdict, detail = "GREEN", f"last release {d} days ago"
    return {"verdict": verdict, "detail": detail, "days_since_last_release": d}


def grade_blast(dependent_count: int | None) -> dict:
    c = dependent_count
    if c is None:
        verdict, detail = "GREEN", "no dependents recorded"
    elif c >= 1000:
        verdict, detail = "RED", f"{c} downstream dependents (systemic)"
    elif c >= 100:
        verdict, detail = "YELLOW", f"{c} downstream dependents"
    else:
        verdict, detail = "GREEN", f"{c} downstream dependents"
    return {"verdict": verdict, "detail": detail, "dependent_count": c}


def grade_health(stars: int | None, open_issues: int | None, has_repo: bool) -> dict:
    if not has_repo:
        return {"verdict": "YELLOW", "detail": "no linked source repo (unauditable)",
                "stars": stars, "open_issues": open_issues, "has_repo": False}
    if open_issues is not None and stars is not None and stars > 0 and open_issues > stars:
        verdict, detail = "YELLOW", f"{open_issues} open issues vs {stars} stars"
    else:
        verdict, detail = "GREEN", f"{stars} stars / {open_issues} open issues"
    return {"verdict": verdict, "detail": detail, "stars": stars,
            "open_issues": open_issues, "has_repo": has_repo}


def grade_identity(suspected_squat: bool) -> dict:
    if suspected_squat:
        return {"verdict": "RED", "detail": "suspected squat / name-confusion package",
                "suspected_squat": True}
    return {"verdict": "GREEN", "detail": "identity looks legitimate", "suspected_squat": False}


def composite(signals: dict) -> str:
    return _worst(*(s["verdict"] for s in signals.values()))
