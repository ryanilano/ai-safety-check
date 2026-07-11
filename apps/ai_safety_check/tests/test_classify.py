from apps.ai_safety_check import classify


def test_parse_tolerates_code_fence():
    raw = '```json\n[{"name":"autogpt","category":"AGENT","capabilities":["executes_code"],"significance":"kicked off agents"}]\n```'
    out = classify.parse_classification(raw)
    assert out[0]["name"] == "autogpt"
    assert "executes_code" in out[0]["capabilities"]


def test_filter_drops_tutorials_and_dedups():
    classified = [
        {"name": "autogpt", "category": "AGENT", "capabilities": [], "significance": "x"},
        {"name": "auto-gpt", "category": "AGENT", "capabilities": [], "significance": "x"},
        {"name": "ml-for-beginners", "category": "TUTORIAL", "capabilities": [], "significance": "course"},
        {"name": "masscan", "category": "FALSE_POSITIVE", "capabilities": [], "significance": "scanner"},
    ]
    out = classify.filter_real_tools(classified, max_tools=20)
    names = {t["name"] for t in out}
    assert "ml-for-beginners" not in names and "masscan" not in names
    assert len(out) == 1  # autogpt / auto-gpt deduped
