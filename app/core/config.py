"""
Configuración centralizada de IDM-Core usando Pydantic Settings.
Singleton via lru_cache para evitar múltiples lecturas de .env.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    """Configuración de un microservicio"""
    url: str
    enabled: bool = True
    timeout: int = 30
    retries: int = 3


class Settings(BaseSettings):
    """Configuración global de IDM-Core"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # === Core ===
    app_name: str = "idm-core"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    secret_key: str = Field(default="change-me-in-production")

    @field_validator("secret_key", mode="after")
    @classmethod
    def warn_default_secret_key(cls, v):
        if v == "change-me-in-production":
            import warnings
            warnings.warn(
                "SECURITY WARNING: secret_key is set to the default value "
                "'change-me-in-production'. Set SECRET_KEY environment variable "
                "to a strong random value before deploying to production.",
                stacklevel=2,
            )
        return v

    # === API Gateway ===
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8888
    gateway_workers: int = 1
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    rate_limit_per_minute: int = 100

    # === Service Endpoints ===
    health_service_url: str = "http://localhost:8080"
    health_service_enabled: bool = True

    research_service_url: str = "http://localhost:3690"
    research_service_enabled: bool = True

    education_service_url: str = "http://localhost:5050"
    education_service_enabled: bool = True

    security_service_url: str = "http://localhost:8000"
    security_service_enabled: bool = True

    # === DevTools Services ===
    ollama_code_url: str = "http://localhost:8890"
    ollama_code_enabled: bool = True

    imperio_lab_url: str = "http://localhost:8891"
    imperio_lab_enabled: bool = True  # Mobile device testing lab

    # === Databases ===
    database_url: str = "postgresql+asyncpg://idm:idm_password@localhost:5432/idm_core"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    # Loguea cada query SQL (verboso). Independiente de `debug` porque DEBUG=true
    # se usa para otros modos dev sin querer spam de SQL. Activar con
    # DATABASE_ECHO=true en .env cuando se quiera depurar queries.
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    lancedb_uri: str = "./data/vectors/lancedb"

    # === AI Services ===
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.1:8b"
    ollama_embedding_model: str = "bge-m3"

    codking_enabled: bool = True
    codking_model_path: str = "./models/codking"
    codking_device: str = "auto"

    compute_router_enabled: bool = True
    prefer_local: bool = True

    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # === Energy System ===
    energy_monitor_enabled: bool = True
    energy_check_interval: int = 30
    solar_api_url: Optional[str] = None
    solar_api_type: str = "generic"
    ups_api_url: Optional[str] = None

    # === Event Sourcing ===
    event_store_enabled: bool = True
    event_retention_days: int = 365
    event_batch_size: int = 100

    # === Monitoring ===
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    health_check_interval: int = 30
    service_timeout: int = 10

    # === Prompt System ===
    prompt_system_enabled: bool = True
    prompt_agent_interval: int = 5  # seconds between prioritization scans
    prompt_max_concurrent: int = 3  # max parallel prompt executions
    prompt_review_enabled: bool = True  # cross-model review for work/plan
    prompt_default_model: Optional[str] = None  # override frangels auto-selection
    prompt_lists_dir: str = "./data/prompt-lists"

    # === ngrok Tunnel ===
    ngrok_enabled: bool = False
    ngrok_authtoken: str = ""
    ngrok_domain: Optional[str] = None  # custom domain (e.g., idmmortality.com)

    # === Google Calendar ===
    google_calendar_enabled: bool = False
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_calendar_sync_interval: int = 60  # seconds

    # === OSASCRIPT Security ===
    osascript_enabled: bool = True
    osascript_require_auth: bool = True
    osascript_rate_limit: int = 30  # requests per minute
    osascript_allow_high_risk: bool = False  # toggle_dark_mode, set_volume, etc.
    osascript_disabled_operations: List[str] = []  # explicitly disabled operations
    osascript_allowed_paths: List[str] = ["/Users/", "/tmp/", "/var/folders/"]
    system_api_key: str = Field(default="change-me-in-production")  # Master API key

    @field_validator("system_api_key", mode="after")
    @classmethod
    def warn_default_system_api_key(cls, v):
        if v == "change-me-in-production":
            import warnings
            warnings.warn(
                "SECURITY WARNING: system_api_key is set to the default value. "
                "Set SYSTEM_API_KEY environment variable to a strong random value.",
                stacklevel=2,
            )
        return v
    system_api_key_readonly: Optional[str] = None  # Read-only API key

    # === Auth (JWT for dashboard access) ===
    auth_username: str = "admin"
    auth_password_hash: str = ""  # bcrypt hash — set AUTH_PASSWORD_HASH in .env
    jwt_secret_key: str = "change-me-jwt-secret"  # set JWT_SECRET_KEY in .env
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    jwt_refresh_token_expire_days: int = 30

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    @field_validator("osascript_disabled_operations", mode="before")
    @classmethod
    def parse_disabled_operations(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [op.strip() for op in v.split(",") if op.strip()]
        return v

    @field_validator("osascript_allowed_paths", mode="before")
    @classmethod
    def parse_allowed_paths(cls, v):
        if v is None or v == "":
            return ["/Users/", "/tmp/", "/var/folders/"]
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def services(self) -> dict:
        """Retorna configuración de todos los servicios"""
        return {
            "health": ServiceConfig(
                url=self.health_service_url,
                enabled=self.health_service_enabled,
                timeout=self.service_timeout
            ),
            "research": ServiceConfig(
                url=self.research_service_url,
                enabled=self.research_service_enabled,
                timeout=self.service_timeout
            ),
            "education": ServiceConfig(
                url=self.education_service_url,
                enabled=self.education_service_enabled,
                timeout=self.service_timeout
            ),
            "security": ServiceConfig(
                url=self.security_service_url,
                enabled=self.security_service_enabled,
                timeout=self.service_timeout
            ),
            "devtools": ServiceConfig(
                url=self.ollama_code_url,
                enabled=self.ollama_code_enabled,
                timeout=self.service_timeout
            ),
            "testlab": ServiceConfig(
                url=self.imperio_lab_url,
                enabled=self.imperio_lab_enabled,
                timeout=self.service_timeout
            ),
        }


@lru_cache()
def get_settings() -> Settings:
    """Singleton de configuración"""
    return Settings()


# Alias para acceso rápido
settings = get_settings()
