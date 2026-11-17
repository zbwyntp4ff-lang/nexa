from app.api.routes.agents import get_agent_catalog
from app.orchestrator.catalog import AGENT_CATALOG, get_agent


def test_catalog_has_100_unique_roles_across_ten_domains():
    assert len(AGENT_CATALOG) == 100
    assert len({agent["id"] for agent in AGENT_CATALOG}) == 100
    assert len({agent["category"] for agent in AGENT_CATALOG}) == 10


def test_catalog_lookup_and_filtering():
    found = get_agent("coding-01")
    assert found is not None
    assert found["name"] == "Python-разработчик"

    result = get_agent_catalog(category="coding", q="python")
    assert result["count"] == 1
    assert result["total"] == 100
    assert result["agents"][0]["id"] == "coding-01"


def test_catalog_marks_roles_as_profiles_not_live_model_instances():
    assert all(agent["status"] == "catalog" for agent in AGENT_CATALOG)
