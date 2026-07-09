from apps.seller_delivery_agent import config


def test_qualified_builds_three_part_quoted_name():
    assert config.qualified("OLIST_SELLERS") == (
        '"BRAZILIAN_E_COMMERCE"."BRAZILIAN_E_COMMERCE"."OLIST_SELLERS"'
    )


def test_schema_fqn_is_three_parts():
    # connection-slug.database.schema = 3 parts / 2 dots (verified live vs generate_sql)
    assert config.SCHEMA_FQN.count(".") == 2


def test_headers_carry_project_id():
    assert config.HEADERS["X-Project-ID"] == config.PROJECT_ID
