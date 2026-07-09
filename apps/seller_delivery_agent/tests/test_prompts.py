from apps.seller_delivery_agent import prompts


def test_system_prompt_frames_investigation_and_lists_all_tools():
    sp = prompts.system_prompt()
    for tool in [
        "search_schema", "get_schema", "sample_data",
        "generate_sql", "execute_query", "get_result_page",
        "generate_plotly_chart", "note",
    ]:
        assert tool in sp
    # framed as a root-cause investigation, not a fixed report
    assert "ROOT CAUSE" in sp
    assert "hypothesis" in sp.lower()
    # does NOT spoon-feed the schema — the agent must discover it
    assert "discover" in sp.lower()
    assert "NEVER write SQL yourself" in sp


def test_user_message_includes_the_question():
    assert "why are freight costs high" in prompts.user_message("why are freight costs high")
