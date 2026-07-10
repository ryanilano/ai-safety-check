# ADR-002: Use Gemini Flash for Engagement Synthesis

**Date:** 2026-06-25
**Status:** Accepted

## Context

Node 5 (compose_engagement) requires an LLM to synthesize structured data (purchase history, preferences, recommendations) into a personalized engagement brief. Options considered:
- Claude Sonnet 4.6 (Anthropic) — excellent at structured synthesis, already used in Claude Code harness
- Gemini 2.5 Flash (Google) — fast, cost-efficient, existing API key in project
- Gemini 2.5 Pro (Google) — higher quality but slower and more expensive

## Decision

Use **Gemini 2.5 Flash** (`gemini-2.5-flash`) for synthesis.

## Consequences

**Positive:**
- Fast enough for a live demo (< 5s synthesis latency)
- Cost-efficient at scale vs Pro
- Uses the `google-genai` SDK, consistent with the CRAFT MCP integration's existing tooling

**Negative / Trade-offs:**
- Flash may produce less nuanced personalization than Pro for complex customer profiles
- Locked to Google for LLM calls while CRAFT tools use Emergence AI's platform

**Neutral:**
- Model name is overridable via `GEMINI_SYNTHESIS_MODEL` env var — upgrading to Pro requires only a config change

> **Update:** the `GEMINI_FLASH_MODEL` default in `config.py` has since moved to a newer
> Flash release; see `config.py` for the current default. The decision to use the Flash
> tier over Pro, recorded above, still holds.
