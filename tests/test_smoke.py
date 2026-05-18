"""Bare-minimum smoke test — confirm the package imports."""
def test_import_package():
    import ugc
    assert ugc.__version__

def test_config_loads_with_env():
    import os
    os.environ.setdefault("HEYGEN_API_KEY", "test-key")
    from ugc.config import settings
    s = settings()
    assert s.heygen_api_base == "https://api.heygen.com"

def test_heygen_client_requires_key():
    import os
    # Force-clear cached settings + key for this test
    os.environ["HEYGEN_API_KEY"] = ""
    from ugc.config import settings
    settings.cache_clear()
    from ugc.integrations.heygen import HeyGenClient, HeyGenError
    try:
        HeyGenClient()
    except HeyGenError as e:
        assert "HEYGEN_API_KEY" in str(e)
        return
    raise AssertionError("Expected HeyGenError when no key set")
