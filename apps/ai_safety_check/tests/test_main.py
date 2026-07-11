import asyncio, json, os
from apps.ai_safety_check.tests.test_nodes import FakeCraft, FakeLLM, FakeTavily
from apps.ai_safety_check import main


def test_run_and_save_writes_artifacts(tmp_path):
    craft = FakeCraft()
    async def nl_query(question, connection, schema_name, schema_fqn, max_rows=200):
        if "most-starred" in question:
            return ({"columns": ["ProjectName", "ProjectType", "StarsCount"],
                     "rows": [["org/mlflow", "GITHUB", 15000]]}, "SELECT discover")
        return await FakeCraft().nl_query(question, connection, schema_name, schema_fqn, max_rows)
    craft.nl_query = nl_query
    state = asyncio.run(main.run(craft=craft, llm=FakeLLM(), tavily=FakeTavily()))
    out = str(tmp_path / "run")
    main.save_artifacts(state, out)
    assert os.path.exists(os.path.join(out, "report.md"))
    assert os.path.exists(os.path.join(out, "sql_queries.txt"))
    saved = json.load(open(os.path.join(out, "state.json")))
    assert saved["tools"][0]["verdict"] == "RED"
