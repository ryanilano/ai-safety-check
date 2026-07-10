"""Bridge between Claude's tool calls and the CRAFT MCP session.

Claude orchestrates the investigation; each tool it calls is forwarded through our
already-authenticated CraftClient MCP session. Fixed connection args are injected here so
the model only supplies the variable parts. SQL text, collected rows, chart paths, and the
model's reasoning notes are captured as side effects for the live trace and run outputs.
"""
import asyncio
import json
import os

from . import config
from .craft_client import (
    MCPResponseError,
    parse_execute_query,
    parse_generate_sql,
    parse_plotly,
    parse_result_page,
)


async def _with_retry(fn, *, attempts: int = 7, base_delay: float = 1.0, max_delay: float = 20.0):
    """Retry a coroutine factory on transient MCPResponseError (em-runtime's result
    endpoints intermittently return an error/ErrorResponse shape, in bad windows that can
    last tens of seconds). Exponential backoff capped at max_delay — total coverage ~60s —
    then re-raise the last error so the model still gets a clear message on a real outage."""
    last = None
    for i in range(attempts):
        try:
            return await fn()
        except MCPResponseError as e:
            last = e
            if i < attempts - 1:
                await asyncio.sleep(min(base_delay * (2 ** i), max_delay))
    raise last

# Anthropic tool definitions exposed to the LLM: schema-discovery + the raw MCP query
# surface + a note() narration tool. The model sequences everything itself.
TOOL_DEFINITIONS = [
    {
        "name": "note",
        "description": (
            "Record your current reasoning for the user to see live: the hypothesis you're "
            "about to test, what a result implies, or why you're pivoting. Call this BEFORE "
            "each investigative step. This does not query anything — it just narrates your "
            "thinking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your reasoning, stated specifically."}
            },
            "required": ["thought"],
        },
    },
    {
        "name": "search_schema",
        "description": (
            "Find tables and columns by keyword when you don't yet know where something "
            "lives. Returns matching entities with their fully-qualified names (use those "
            "with get_schema)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword(s), e.g. 'freight' or 'review score'."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_schema",
        "description": (
            "Read a table's columns, types, and business definitions. Pass the exact "
            "fully-qualified name (4 dot-separated parts) from a search_schema result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fqn": {"type": "string", "description": "4-part FQN, e.g. 'eval-x.DB.SCHEMA.TABLE'."}
            },
            "required": ["fqn"],
        },
    },
    {
        "name": "sample_data",
        "description": (
            "Peek at a few real rows of a table to understand its values and formats. Pass "
            "the 3-part table name: DATABASE.SCHEMA.TABLE."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table_fqn": {"type": "string", "description": "3-part name: DATABASE.SCHEMA.TABLE."},
                "limit": {"type": "integer", "description": "Rows to sample (default 5)."},
            },
            "required": ["table_fqn"],
        },
    },
    {
        "name": "generate_sql",
        "description": (
            "Translate a natural-language analytical question into schema-bound SQL. Returns "
            "the SQL string. Do NOT write SQL yourself — describe the question in plain words."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The analytical question in plain words."}
            },
            "required": ["question"],
        },
    },
    {
        "name": "execute_query",
        "description": (
            "Execute a SQL string previously returned by generate_sql. Returns an "
            "artifact_fqn handle (page it with get_result_page)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL returned by generate_sql."},
                "max_rows": {"type": "integer", "description": "Max rows (default 500)."},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_result_page",
        "description": (
            "Read a page of rows from a previously executed query. Returns columns and rows "
            "(values come back as strings)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_fqn": {"type": "string", "description": "The artifact_fqn from execute_query."},
                "offset": {"type": "integer", "description": "Row offset (default 0)."},
                "limit": {"type": "integer", "description": "Max rows (default 500)."},
            },
            "required": ["artifact_fqn"],
        },
    },
    {
        "name": "generate_plotly_chart",
        "description": (
            "Build a chart from rows you collected and save it as a PNG in the run folder. "
            "Returns the saved file path. Use it for the key finding worth showing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {"type": "string", "description": "e.g. 'bar' or 'line'."},
                "data": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Row objects, e.g. [{'x': 'a', 'y': 1}, ...].",
                },
                "options": {"type": "object", "description": "title, x_label, y_label."},
            },
            "required": ["chart_type", "data"],
        },
    },
]

# Tools that don't hit the data plane / are cheap — used only for trace labeling.
_DISCOVERY_TOOLS = {"search_schema", "get_schema", "sample_data"}


class ToolExecutor:
    """Dispatches Claude's tool calls to the MCP session and captures side effects.

    Args:
        client: an entered CraftClient (live MCP session).
        out_dir: directory to write chart PNGs into.
    """

    def __init__(self, client, out_dir: str):
        self._client = client
        self._out_dir = out_dir
        self.sql_log: list[tuple[str, str]] = []  # (question, sql)
        self.chart_paths: list[str] = []
        self.collected: list[dict] = []  # {question, columns, rows}
        self.notes: list[str] = []  # the model's reasoning, in order
        self._last_question: str | None = None
        self._chart_index = 0

    async def run(self, name: str, tool_input: dict) -> str:
        """Execute one tool call; return a compact string result for the LLM."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"ERROR: unknown tool '{name}'"
        try:
            return await handler(tool_input)
        except Exception as e:  # surface tool errors to the model so it can adapt
            return f"ERROR: {type(e).__name__}: {e}"

    # --- narration ---
    async def _tool_note(self, args: dict) -> str:
        self.notes.append(args["thought"])
        return "noted"

    # --- schema discovery ---
    async def _tool_search_schema(self, args: dict) -> str:
        resp = await self._client._call(
            "search_schema", {"connection": config.CONNECTION_SLUG, "query": args["query"], "limit": 15}
        )
        return _compact_search(resp)

    async def _tool_get_schema(self, args: dict) -> str:
        resp = await self._client._call(
            "get_schema",
            {"connection": config.CONNECTION_SLUG, "fqn": args["fqn"], "include_children": True},
        )
        return _compact_schema(resp)

    async def _tool_sample_data(self, args: dict) -> str:
        resp = await self._client._call(
            "sample_data",
            {
                "connection": config.CONNECTION_SLUG,
                "table_fqn": args["table_fqn"],
                "limit": args.get("limit", 5),
            },
        )
        sample = resp.get("sample", resp)
        return json.dumps({"columns": sample.get("columns"), "rows": sample.get("rows")})

    # --- query triplet ---
    async def _tool_generate_sql(self, args: dict) -> str:
        question = args["question"]
        self._last_question = question
        resp = await self._client._call(
            "generate_sql",
            {
                "connection": config.CONNECTION_SLUG,
                "question": question,
                "schema": {"schema_name": config.SCHEMA_NAME, "schema_fqn": config.SCHEMA_FQN},
            },
        )
        sql = parse_generate_sql(resp)
        self.sql_log.append((question, sql))
        return sql

    async def _tool_execute_query(self, args: dict) -> str:
        async def call():
            resp = await self._client._call(
                "execute_query",
                {
                    "connection": config.CONNECTION_SLUG,
                    "sql": args["sql"],
                    "max_rows": args.get("max_rows", 500),
                },
            )
            return parse_execute_query(resp)  # raises MCPResponseError on transient error

        return await _with_retry(call)

    async def _tool_get_result_page(self, args: dict) -> str:
        async def call():
            resp = await self._client._call(
                "get_result_page",
                {
                    "artifact_fqn": args["artifact_fqn"],
                    "offset": args.get("offset", 0),
                    "limit": args.get("limit", 500),
                },
            )
            return parse_result_page(resp)  # raises MCPResponseError on transient error

        columns, rows = await _with_retry(call)
        self.collected.append(
            {"question": self._last_question, "columns": columns, "rows": rows}
        )
        return json.dumps({"columns": columns, "rows": rows})

    async def _tool_generate_plotly_chart(self, args: dict) -> str:
        from .charts import render_chart

        resp = await self._client._call(
            "generate_plotly_chart",
            {
                "chart_type": args["chart_type"],
                "data": args["data"],
                "options": args.get("options", {}),
            },
        )
        figure = parse_plotly(resp)
        self._chart_index += 1
        path = os.path.join(self._out_dir, f"chart_{self._chart_index}.png")
        render_chart(figure, path)
        self.chart_paths.append(path)
        return f"Chart saved to {os.path.basename(path)}"


def _compact_search(resp: dict) -> str:
    """Reduce a search_schema response to name/type/fqn/description per hit — the catalog
    payload is huge and the model only needs enough to pick where to look next."""
    results = resp.get("list_metadata", {}).get("results", [])
    out = []
    for r in results:
        out.append(
            {
                "name": r.get("name"),
                "type": r.get("type"),
                "fqn": r.get("fully_qualified_name"),
                "description": (r.get("description") or "")[:200],
            }
        )
    return json.dumps(out)


def _compact_schema(resp: dict) -> str:
    """Reduce a get_schema response to the table's columns (name/type/description)."""
    meta = resp.get("metadata", {})
    cols = []
    for c in meta.get("children") or []:
        if c.get("type") == "column":
            cols.append(
                {
                    "name": c.get("name"),
                    "data_type": c.get("data_type"),
                    "description": (c.get("description") or "")[:160],
                }
            )
    return json.dumps(
        {"table": meta.get("name"), "fqn": meta.get("fully_qualified_name"), "columns": cols}
    )
