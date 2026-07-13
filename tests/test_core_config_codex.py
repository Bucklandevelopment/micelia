"""
Tests for app/core/config.py (Settings + validators + services property).

Everything is exercised in-process by instantiating ``Settings`` with explicit
init kwargs (which take priority over env/.env in pydantic-settings) and
``_env_file=None`` so the real repo ``.env`` is never read. No infra, no network,
no ``.env`` mutation — just the pure validators and derived properties that were
previously uncovered (the two security warnings, the comma/JSON parsers with
their empty-string branches, and the ``services`` map).
"""

import warnings

import pytest

from app.core.config import ServiceConfig, Settings, get_settings


def _settings(**overrides) -> Settings:
    """Build Settings ignoring the real .env, with safe non-warning defaults."""
    base: dict[str, object] = dict(
        _env_file=None,
        secret_key="a-strong-secret",
        system_api_key="a-strong-system-key",
    )
    base.update(overrides)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Settings(**base)


# ==================== SECURITY WARNINGS ====================


def test_default_secret_key_warns():
    with pytest.warns(UserWarning, match="secret_key is set to the default"):
        Settings(_env_file=None, secret_key="change-me-in-production",
                 system_api_key="a-strong-system-key")


def test_default_system_api_key_warns():
    with pytest.warns(UserWarning, match="system_api_key is set to the default"):
        Settings(_env_file=None, secret_key="a-strong-secret",
                 system_api_key="change-me-in-production")


def test_non_default_secrets_do_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error
        s = Settings(_env_file=None, secret_key="x-secret", system_api_key="x-key")
    assert s.secret_key == "x-secret"
    assert s.system_api_key == "x-key"


# ==================== cors_origins parser ====================


def test_cors_origins_from_json_string():
    s = _settings(cors_origins='["http://a", "http://b"]')
    assert s.cors_origins == ["http://a", "http://b"]


def test_cors_origins_passthrough_list():
    s = _settings(cors_origins=["http://a"])
    assert s.cors_origins == ["http://a"]


# ==================== osascript_disabled_operations parser ====================


@pytest.mark.parametrize("empty", [None, ""])
def test_disabled_operations_empty_defaults_to_list(empty):
    s = _settings(osascript_disabled_operations=empty)
    assert s.osascript_disabled_operations == []


def test_disabled_operations_from_csv():
    s = _settings(osascript_disabled_operations="set_volume, toggle_dark_mode ,")
    assert s.osascript_disabled_operations == ["set_volume", "toggle_dark_mode"]


# ==================== osascript_allowed_paths parser ====================


@pytest.mark.parametrize("empty", [None, ""])
def test_allowed_paths_empty_restores_defaults(empty):
    s = _settings(osascript_allowed_paths=empty)
    assert s.osascript_allowed_paths == ["/Users/", "/tmp/", "/var/folders/"]


def test_allowed_paths_from_csv():
    s = _settings(osascript_allowed_paths="/foo/, /bar/ ,")
    assert s.osascript_allowed_paths == ["/foo/", "/bar/"]


# ==================== derived properties ====================


def test_is_production_flag():
    assert _settings(environment="production").is_production is True
    assert _settings(environment="development").is_production is False


def test_services_map_reflects_config():
    s = _settings(
        health_service_url="http://h:1",
        health_service_enabled=False,
        service_timeout=7,
    )
    services = s.services
    assert set(services) == {
        "health", "research", "education", "security", "devtools", "testlab",
    }
    assert all(isinstance(v, ServiceConfig) for v in services.values())
    assert services["health"].url == "http://h:1"
    assert services["health"].enabled is False
    assert services["health"].timeout == 7


def test_get_settings_is_cached_singleton():
    assert get_settings() is get_settings()
