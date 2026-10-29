from alphaview_integrations.connectors.base import growth_ratio
from alphaview_integrations.connectors.registry import REGISTRY


def test_growth_ratio():
    assert growth_ratio([10, 10, 10, 10, 20, 20, 20, 20]) == 1.0
    assert growth_ratio([1, 2]) == 0.0
    assert growth_ratio([0, 0, 0, 0, 5, 5, 5, 5]) == 1.0


def test_registry_contract():
    assert set(REGISTRY) == {"ga4", "gsc", "dataforseo", "serpapi", "semrush"}
    for c in REGISTRY.values():
        assert c.auth_type in ("api_key", "oauth2")
        assert c.capabilities
        if c.auth_type == "oauth2":
            assert c.oauth_scopes
        else:
            assert c.credential_fields
