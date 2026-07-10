# Learnings — Customer Experience Agent

Newest entries at the top.

---

## 2026-06-25 — get_schema requires can_read_metadata; agent must not hard-fail on it

**Symptom:** `get_schema` returns `{'ok': False, 'error': {'code': 'INSUFFICIENT_PERMISSIONS', 'message': 'Insufficient permissions: can_read_metadata'}}`. Agent stops at Node 1.

**Root cause:** `get_schema` enforces `can_read_metadata` on the data connection. The Keycloak token may not have this permission for the target database even if `execute_query` and `generate_sql` work fine.

**Fix:** `get_schema` failure is now non-fatal. `discover_profile_node` appends the error to `errors` and continues with an empty `schema_summary`/`tables_available` rather than stopping the graph.

---

## 2026-06-25 — generate_sql (Talk2Data) returns talk2data_error when metadata is unavailable

**Symptom:** `generate_sql` returns `{'ok': False, 'error': {'code': 'talk2data_error', 'message': 'Talk2Data returned...'}}` immediately after a `get_schema` failure.

**Root cause:** Talk2Data uses the catalog metadata to understand the schema before generating SQL. If `get_schema` failed (metadata unavailable), Talk2Data may also fail to resolve the database schema.

**Fix:** `_run_nl_query` treats this as non-fatal: it appends the error to `node_errors` and returns an empty row list, so the node continues (with that piece of data missing) instead of crashing the graph. There is no SQL fallback — if `generate_sql` fails, that query simply returns no rows.

---

## 2026-06-25 — execute_query returns artifact_fqn, not rows directly

**Symptom:** Calling `execute_query` MCP tool returns `{"ok": true, "execute_query": {"artifact_fqn": "...", "row_count": N}}` — NOT the actual rows.

**Root cause:** CRAFT's `execute_query` stores results as an artifact for large-result pagination. Rows must be fetched separately via `get_result_page` using the returned `artifact_fqn`.

**Fix:** The `CraftClient.execute_query()` helper wraps both calls internally — callers receive `{"ok": true, "rows": [...], "columns": [...]}` directly. Never call the raw MCP `execute_query` without immediately following up with `get_result_page`.

---

## 2026-06-25 — get_result_page returns rows as arrays-of-arrays, not dicts

**Symptom:** `page_resp["preview"]["rows"]` is `[[val1, val2, ...], ...]` not `[{"col1": val1}, ...]`.

**Root cause:** MCP `get_result_page` response nests rows under `preview.rows` as a 2D array (positional, not named). Columns are in `preview.columns`.

**Fix:** Zip columns and rows: `[dict(zip(columns, row)) for row in raw_rows]`. This is done inside `CraftClient.execute_query()`.

---

## 2026-06-25 — generate_sql may return talk2data_unreachable on first call

**Symptom:** First `generate_sql` call returns `{"ok": false, "error": {"code": "talk2data_unreachable"}}`, but retrying immediately succeeds.

**Root cause:** Talk2Data service cold-start or transient availability issue.

**Fix:** `CraftClient.generate_sql()` retries up to `AGENT_MAX_RETRIES` times with exponential backoff (2s, 4s) specifically on this error code.
