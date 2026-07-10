# ADR-002: Use Gemini Flash for Engagement Synthesis

**Date:** 2026-06-25
**Status:** Accepted

## Context

Node 5 (compose_engagement) requires an LLM to synthesize structured data (purchase history, preferences, recommendations) into a personalized engagement brief. Options considered:
- Claude Sonnet 4.6 (Anthropic) — excellent at structured synthesis, already used in Claude Code harness
- Gemini Flash (Google) — fast, cost-efficient, existing API key in project
- Gemini Pro (Google) — higher quality but slower and more expensive

## Decision

Use the **Gemini Flash** tier for synthesis (see `config.py`'s `GEMINI_FLASH_MODEL` for the current default model name — it moves as Google releases newer Flash versions).

## Consequences

**Positive:**
- Fast enough for a live demo (< 5s synthesis latency)
- Cost-efficient at scale vs Pro
- Uses the `google-genai` SDK, consistent with the CRAFT MCP integration's existing tooling

**Negative / Trade-offs:**
- Flash may produce less nuanced personalization than Pro for complex customer profiles
- Locked to Google for LLM calls while CRAFT tools use Emergence AI's platform

**Neutral:**
- Model name is overridable via the `GEMINI_FLASH_MODEL` env var — upgrading to Pro requires only pointing `GEMINI_SYNTHESIS_MODEL` (in `config.py`) at `GEMINI_PRO_MODEL` instead
