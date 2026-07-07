"""
Angel Registry - Definición de proveedores cloud (Free Angels)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class AngelCategory(str, Enum):
    """Categorías de ángeles cloud"""
    INFERENCE = "inference"
    GPU = "gpu"
    DATABASE = "database"
    INFRA = "infra"


class AngelTier(str, Enum):
    """Clasificación por calidad/velocidad"""
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"


class PrivacyLevel(str, Enum):
    """Nivel de privacidad del proveedor"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class QuotaConfig:
    """Configuración de cuotas del free tier"""
    requests_per_day: int = 0
    requests_per_minute: int = 0
    tokens_per_minute: int = 0
    tokens_per_day: int = 0
    storage_bytes: int = 0
    compute_hours_per_month: float = 0


@dataclass
class AngelCapabilities:
    """Capacidades del proveedor"""
    max_context_tokens: int = 0
    max_output_tokens: int = 0
    supports_streaming: bool = False
    supports_vision: bool = False
    supports_tools: bool = False
    supports_code: bool = False
    supports_embeddings: bool = False
    models: List[str] = field(default_factory=list)


@dataclass
class AngelHealth:
    """Estado de salud del proveedor"""
    is_available: bool = False
    last_check: Optional[datetime] = None
    latency_ms: float = 0
    error_rate_24h: float = 0
    last_error: Optional[str] = None


@dataclass
class Angel:
    """Definición completa de un proveedor cloud (Ángel)"""
    id: str
    name: str
    category: AngelCategory
    tier: AngelTier
    privacy_level: PrivacyLevel

    # Configuración
    base_url: str
    env_key: str
    env_key_extra: Optional[str] = None

    # Límites
    quota: QuotaConfig = field(default_factory=QuotaConfig)
    capabilities: AngelCapabilities = field(default_factory=AngelCapabilities)

    # Estado
    health: AngelHealth = field(default_factory=AngelHealth)

    # Metadata
    free_quota_description: str = ""
    console_url: str = ""
    blocked_regions: List[str] = field(default_factory=list)
    data_residency: Optional[str] = None


# === REGISTRO DE ÁNGELES ===

ANGEL_REGISTRY: Dict[str, Angel] = {
    # === INFERENCE ANGELS ===
    "groq": Angel(
        id="groq",
        name="Groq",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.PREMIUM,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://api.groq.com/openai/v1",
        env_key="GROQ_API_KEY",
        quota=QuotaConfig(
            requests_per_day=14400,
            requests_per_minute=30,
            tokens_per_minute=20000,
            tokens_per_day=500000,
        ),
        capabilities=AngelCapabilities(
            max_context_tokens=128000,
            max_output_tokens=32768,
            supports_streaming=True,
            supports_vision=True,
            supports_tools=True,
            supports_code=True,
            models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        ),
        free_quota_description="14,400 req/dia, 500K tokens/dia",
        console_url="https://console.groq.com/keys",
        data_residency="us"
    ),

    "gemini": Angel(
        id="gemini",
        name="Google AI Studio",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.PREMIUM,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        env_key="GOOGLE_AI_API_KEY",
        quota=QuotaConfig(
            requests_per_day=1000,
            requests_per_minute=15,
            tokens_per_minute=32000,
            tokens_per_day=1500000,
        ),
        capabilities=AngelCapabilities(
            max_context_tokens=1000000,
            max_output_tokens=8192,
            supports_streaming=True,
            supports_vision=True,
            supports_tools=True,
            supports_code=True,
            supports_embeddings=True,
            models=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
        ),
        free_quota_description="1M tokens/dia, contexto 1M",
        console_url="https://aistudio.google.com/apikey",
        blocked_regions=["EU", "EEA", "UK", "CH"],
        data_residency="us"
    ),

    "deepseek": Angel(
        id="deepseek",
        name="DeepSeek",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.LOW,
        base_url="https://api.deepseek.com/v1",
        env_key="DEEPSEEK_API_KEY",
        quota=QuotaConfig(
            tokens_per_day=5000000,
        ),
        capabilities=AngelCapabilities(
            max_context_tokens=128000,
            max_output_tokens=8192,
            supports_streaming=True,
            supports_tools=True,
            supports_code=True,
            models=["deepseek-chat", "deepseek-reasoner"]
        ),
        free_quota_description="5M tokens gratis iniciales",
        console_url="https://platform.deepseek.com/",
        data_residency="cn"
    ),

    "cohere": Angel(
        id="cohere",
        name="Cohere",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://api.cohere.ai/v1",
        env_key="COHERE_API_KEY",
        quota=QuotaConfig(
            requests_per_day=1000,
        ),
        capabilities=AngelCapabilities(
            max_context_tokens=128000,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
            supports_code=True,
            supports_embeddings=True,
            models=["command-r-plus", "command-r", "embed-english-v3.0"]
        ),
        free_quota_description="1,000 req/mes trial",
        console_url="https://dashboard.cohere.com/api-keys"
    ),

    "mistral": Angel(
        id="mistral",
        name="Mistral AI",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.HIGH,
        base_url="https://api.mistral.ai/v1",
        env_key="MISTRAL_API_KEY",
        quota=QuotaConfig(
            requests_per_minute=5,
            tokens_per_minute=10000,
        ),
        capabilities=AngelCapabilities(
            max_context_tokens=32768,
            max_output_tokens=8192,
            supports_streaming=True,
            supports_tools=True,
            supports_code=True,
            supports_embeddings=True,
            models=["mistral-small-latest", "mistral-medium-latest"]
        ),
        free_quota_description="Trial tier EU",
        console_url="https://console.mistral.ai/api-keys/",
        data_residency="eu"
    ),

    "openrouter": Angel(
        id="openrouter",
        name="OpenRouter",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.ECONOMY,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://openrouter.ai/api/v1",
        env_key="OPENROUTER_API_KEY",
        quota=QuotaConfig(),
        capabilities=AngelCapabilities(
            max_context_tokens=128000,
            max_output_tokens=4096,
            supports_streaming=True,
            supports_vision=True,
            supports_tools=True,
            supports_code=True,
            models=["meta-llama/llama-3.1-8b-instruct:free", "google/gemma-2-9b-it:free"]
        ),
        free_quota_description="Modelos gratuitos disponibles",
        console_url="https://openrouter.ai/keys"
    ),

    "huggingface": Angel(
        id="huggingface",
        name="HuggingFace",
        category=AngelCategory.INFERENCE,
        tier=AngelTier.ECONOMY,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://api-inference.huggingface.co",
        env_key="HUGGINGFACE_TOKEN",
        quota=QuotaConfig(
            requests_per_day=10000,
        ),
        capabilities=AngelCapabilities(
            supports_streaming=False,
            supports_embeddings=True,
            models=["sentence-transformers/all-MiniLM-L6-v2"]
        ),
        free_quota_description="Ilimitado modelos gratuitos",
        console_url="https://huggingface.co/settings/tokens"
    ),

    # === GPU ANGELS ===
    "kaggle": Angel(
        id="kaggle",
        name="Kaggle",
        category=AngelCategory.GPU,
        tier=AngelTier.PREMIUM,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://www.kaggle.com/api/v1",
        env_key="KAGGLE_KEY",
        env_key_extra="KAGGLE_USERNAME",
        quota=QuotaConfig(
            compute_hours_per_month=30,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="30h GPU/semana (T4/P100)",
        console_url="https://www.kaggle.com/settings"
    ),

    "lightning": Angel(
        id="lightning",
        name="Lightning.ai",
        category=AngelCategory.GPU,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://lightning.ai/api",
        env_key="LIGHTNING_API_KEY",
        quota=QuotaConfig(
            compute_hours_per_month=22,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="22h GPU/mes",
        console_url="https://lightning.ai/"
    ),

    "cloudflare_ai": Angel(
        id="cloudflare_ai",
        name="Cloudflare AI",
        category=AngelCategory.GPU,
        tier=AngelTier.ECONOMY,
        privacy_level=PrivacyLevel.HIGH,
        base_url="https://api.cloudflare.com/client/v4/accounts",
        env_key="CLOUDFLARE_API_TOKEN",
        env_key_extra="CLOUDFLARE_ACCOUNT_ID",
        quota=QuotaConfig(
            requests_per_day=100000,
        ),
        capabilities=AngelCapabilities(
            supports_streaming=True,
            models=["@cf/meta/llama-2-7b-chat-int8", "@cf/mistral/mistral-7b-instruct-v0.1"]
        ),
        free_quota_description="100K req/dia edge",
        console_url="https://dash.cloudflare.com/"
    ),

    # === DATABASE ANGELS ===
    "qdrant": Angel(
        id="qdrant",
        name="Qdrant Cloud",
        category=AngelCategory.DATABASE,
        tier=AngelTier.PREMIUM,
        privacy_level=PrivacyLevel.HIGH,
        base_url="",
        env_key="QDRANT_API_KEY",
        env_key_extra="QDRANT_URL",
        quota=QuotaConfig(
            storage_bytes=1024 * 1024 * 1024,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="1GB vectors",
        console_url="https://cloud.qdrant.io/"
    ),

    "turso": Angel(
        id="turso",
        name="Turso",
        category=AngelCategory.DATABASE,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.HIGH,
        base_url="",
        env_key="TURSO_AUTH_TOKEN",
        env_key_extra="TURSO_DATABASE_URL",
        quota=QuotaConfig(
            storage_bytes=9 * 1024 * 1024 * 1024,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="9GB SQLite edge",
        console_url="https://turso.tech/"
    ),

    "supabase": Angel(
        id="supabase",
        name="Supabase",
        category=AngelCategory.DATABASE,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.HIGH,
        base_url="",
        env_key="SUPABASE_KEY",
        env_key_extra="SUPABASE_URL",
        quota=QuotaConfig(
            storage_bytes=500 * 1024 * 1024,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="500MB + Auth + Realtime",
        console_url="https://supabase.com/dashboard"
    ),

    "upstash": Angel(
        id="upstash",
        name="Upstash Redis",
        category=AngelCategory.DATABASE,
        tier=AngelTier.ECONOMY,
        privacy_level=PrivacyLevel.HIGH,
        base_url="",
        env_key="UPSTASH_REDIS_TOKEN",
        env_key_extra="UPSTASH_REDIS_URL",
        quota=QuotaConfig(
            requests_per_day=10000,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="10K cmd/dia",
        console_url="https://console.upstash.com/"
    ),

    # === INFRA ANGELS ===
    "oracle": Angel(
        id="oracle",
        name="Oracle Cloud",
        category=AngelCategory.INFRA,
        tier=AngelTier.PREMIUM,
        privacy_level=PrivacyLevel.HIGH,
        base_url="https://iaas.region.oraclecloud.com",
        env_key="ORACLE_FINGERPRINT",
        quota=QuotaConfig(
            compute_hours_per_month=720,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="4 ARM cores + 24GB RAM",
        console_url="https://cloud.oracle.com/"
    ),

    "vercel": Angel(
        id="vercel",
        name="Vercel",
        category=AngelCategory.INFRA,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.MEDIUM,
        base_url="https://api.vercel.com",
        env_key="VERCEL_TOKEN",
        quota=QuotaConfig(
            requests_per_day=100000,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="100K func invocations/mes",
        console_url="https://vercel.com/account/tokens"
    ),

    "aws": Angel(
        id="aws",
        name="AWS Lambda",
        category=AngelCategory.INFRA,
        tier=AngelTier.STANDARD,
        privacy_level=PrivacyLevel.HIGH,
        base_url="",
        env_key="AWS_SECRET_ACCESS_KEY",
        env_key_extra="AWS_ACCESS_KEY_ID",
        quota=QuotaConfig(
            requests_per_day=33333,
        ),
        capabilities=AngelCapabilities(),
        free_quota_description="1M req/mes Lambda",
        console_url="https://aws.amazon.com/console/"
    ),
}


def get_angels_by_category(category: AngelCategory) -> List[Angel]:
    """Obtiene ángeles por categoría"""
    return [a for a in ANGEL_REGISTRY.values() if a.category == category]


def get_inference_angels() -> List[Angel]:
    """Obtiene ángeles de inferencia LLM"""
    return get_angels_by_category(AngelCategory.INFERENCE)


def get_available_angels() -> List[Angel]:
    """Obtiene ángeles disponibles (con health check OK)"""
    return [a for a in ANGEL_REGISTRY.values() if a.health.is_available]
