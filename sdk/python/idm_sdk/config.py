"""Configuration for the IDM SDK using pydantic-settings."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class IdmConfig(BaseSettings):
    """SDK configuration loaded from environment variables.

    All fields prefixed with ``VITAL_`` in the environment.
    Example: ``MICELIA_URL`` (con alias deprecado ``IDM_CORE_URL``), ``VITAL_API_KEY``, ``VITAL_SERVICE_NAME``.
    """

    # `extra="ignore"` — pydantic-settings 2.x aplica "forbid" por defecto.
    # Sin esto, cualquier var del .env del repo Micelia (APP_NAME, GATEWAY_PORT,
    # DATABASE_URL, etc., 52+ vars) hace fallar la validación porque no son
    # campos del SDK. "ignore" deja que sólo se carguen los campos declarados.
    model_config = SettingsConfigDict(
        env_prefix="VITAL_",
        env_file=".env",
        extra="ignore",
    )

    core_url: str = "http://localhost:8888"
    api_key: str
    service_name: str
    service_port: int
    service_version: str = "0.1.0"
    service_category: str = "system"
    capabilities: List[str] = []
    redis_url: str = "redis://localhost:6379"
