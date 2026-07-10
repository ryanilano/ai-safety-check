# ADR-003: Use CRAFT generate_sql for All Data Queries

**Date:** 2026-06-25
**Status:** Accepted

## Context

Data queries in nodes 1–3 could be implemented in two ways:
- **Option A**: Hardcode SQL strings in node code (fast to write, brittle to schema changes)
- **Option B**: Use CRAFT `generate_sql` (Text2SQL) to generate SQL from natural-language questions

## Decision

Use **CRAFT `generate_sql`** for all data queries. Raw SQL is never hardcoded in node logic.

## Consequences

**Positive:**
- Schema changes in TheLook automatically propagate — no SQL maintenance required in application code
- Natural-language questions are readable and self-documenting in the code
- Demonstrates the full CRAFT MCP toolchain as a differentiator (showcasing Text2SQL capability)
- SQL audit trail (`sql_queries.txt`) provides full transparency into what was actually executed

**Negative / Trade-offs:**
- Each `generate_sql` call adds ~1–3s latency (network round-trip to Talk2Data)
- Text2SQL may occasionally generate suboptimal SQL for highly specific queries (mitigated by retry logic)
- Harder to test offline without CRAFT connectivity

**Neutral:**
- The `_run_nl_query` helper in nodes.py encapsulates the generate_sql → execute_query → get_result_page pattern, keeping node code clean
