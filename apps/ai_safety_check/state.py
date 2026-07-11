# apps/ai_safety_check/state.py
from typing import TypedDict


class SafetyCheckState(TypedDict, total=False):
    candidates: list[dict]
    tools: list[dict]
    coverage: dict
    dangers: list[dict]
    cases: list[str]
    errors: list[str]
    sql_log: list
