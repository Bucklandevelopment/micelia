"""
API Frangels: Free Angels Cloud Helpers

Gestión de proveedores cloud gratuitos:
- Configuración de API keys
- Monitoreo de cuotas
- Chat unificado multi-proveedor
"""

from dataclasses import asdict
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import log
from app.core.security import verify_auth
from app.services.frangels import ANGEL_REGISTRY, AngelCategory, PrivacyLevel
from app.services.frangels.orchestrator import get_frangels_orchestrator
from app.services.frangels.provider_store import get_provider_store
from app.services.frangels.quota_manager import get_quota_manager

router = APIRouter(prefix="/frangels", dependencies=[Depends(verify_auth)])


# === REQUEST/RESPONSE MODELS ===

class ProviderCredentialRequest(BaseModel):
    provider_id: str
    api_key: str
    extra_key: Optional[str] = None
    enabled: bool = True


class ProviderToggleRequest(BaseModel):
    enabled: bool


class ChatMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessageRequest]
    model: Optional[str] = None
    provider: Optional[str] = None
    category: str = "inference"
    temperature: float = 0.7
    max_tokens: int = 2048
    require_vision: bool = False
    require_tools: bool = False
    privacy_level: Optional[str] = None


class SystemSettingsRequest(BaseModel):
    prefer_local: bool = True
    allow_cloud_for_sensitive_data: bool = False
    solar_threshold: float = 0.3
    battery_conserve_threshold: float = 0.2
    battery_critical_threshold: float = 0.1
    osascript_enabled: bool = True
    osascript_require_auth: bool = True


# === PROVIDER MANAGEMENT ===

@router.get("/providers")
async def list_providers():
    """
    Lista todos los proveedores disponibles con su estado.
    Incluye configurados y no configurados.
    """
    store = get_provider_store()
    quota_manager = get_quota_manager()

    configured = store.get_all_status()

    providers = []
    for provider_id, angel in ANGEL_REGISTRY.items():
        config = configured.get(provider_id, {})
        quota_status = quota_manager.get_quota_status(provider_id)

        providers.append({
            "id": angel.id,
            "name": angel.name,
            "category": angel.category.value,
            "tier": angel.tier.value,
            "privacy_level": angel.privacy_level.value,
            "configured": config.get("configured", False),
            "enabled": config.get("enabled", False),
            "env_key": angel.env_key,
            "env_key_extra": angel.env_key_extra,
            "free_quota_description": angel.free_quota_description,
            "console_url": angel.console_url,
            "capabilities": {
                "max_context_tokens": angel.capabilities.max_context_tokens,
                "max_output_tokens": angel.capabilities.max_output_tokens,
                "supports_streaming": angel.capabilities.supports_streaming,
                "supports_vision": angel.capabilities.supports_vision,
                "supports_tools": angel.capabilities.supports_tools,
                "supports_code": angel.capabilities.supports_code,
                "supports_embeddings": angel.capabilities.supports_embeddings,
                "models": angel.capabilities.models
            },
            "quota": {
                "used": quota_status.used if quota_status else 0,
                "limit": quota_status.limit if quota_status else 0,
                "percentage": quota_status.percentage if quota_status else 0,
                "is_exhausted": quota_status.is_exhausted if quota_status else False
            } if quota_status else None,
            "health": {
                "is_available": angel.health.is_available,
                "latency_ms": angel.health.latency_ms,
                "last_error": angel.health.last_error
            },
            "last_used": config.get("last_used")
        })

    # Agrupar por categoría
    by_category = {
        "inference": [],
        "gpu": [],
        "database": [],
        "infra": []
    }

    for p in providers:
        cat = p["category"]
        if cat in by_category:
            by_category[cat].append(p)

    return {
        "providers": providers,
        "by_category": by_category,
        "summary": {
            "total": len(providers),
            "configured": len([p for p in providers if p["configured"]]),
            "enabled": len([p for p in providers if p["enabled"]])
        }
    }


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str):
    """Obtiene detalles de un proveedor específico."""
    angel = ANGEL_REGISTRY.get(provider_id)
    if not angel:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    store = get_provider_store()
    quota_manager = get_quota_manager()

    config = store.get_all_status().get(provider_id, {})
    quota_status = quota_manager.get_quota_status(provider_id)

    return {
        "id": angel.id,
        "name": angel.name,
        "category": angel.category.value,
        "tier": angel.tier.value,
        "privacy_level": angel.privacy_level.value,
        "base_url": angel.base_url,
        "env_key": angel.env_key,
        "env_key_extra": angel.env_key_extra,
        "configured": config.get("configured", False),
        "enabled": config.get("enabled", False),
        "free_quota_description": angel.free_quota_description,
        "console_url": angel.console_url,
        "blocked_regions": angel.blocked_regions,
        "data_residency": angel.data_residency,
        "capabilities": asdict(angel.capabilities),
        "quota_config": asdict(angel.quota),
        "quota_status": asdict(quota_status) if quota_status else None,
        "health": asdict(angel.health),
        "created_at": config.get("created_at"),
        "updated_at": config.get("updated_at"),
        "last_used": config.get("last_used")
    }


@router.post("/providers")
async def save_provider_credentials(request: ProviderCredentialRequest):
    """
    Guarda o actualiza credenciales de un proveedor.
    Las credenciales se almacenan encriptadas.
    """
    if request.provider_id not in ANGEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{request.provider_id}'"
        )

    store = get_provider_store()

    # Validar que la API key no está vacía
    if not request.api_key or not request.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    store.set(
        provider_id=request.provider_id,
        api_key=request.api_key.strip(),
        extra_key=request.extra_key.strip() if request.extra_key else None,
        enabled=request.enabled
    )

    log.info(f"Saved credentials for provider: {request.provider_id}")

    return {
        "success": True,
        "provider_id": request.provider_id,
        "message": f"Credentials saved for {ANGEL_REGISTRY[request.provider_id].name}"
    }


@router.delete("/providers/{provider_id}")
async def delete_provider_credentials(provider_id: str):
    """Elimina credenciales de un proveedor."""
    store = get_provider_store()

    if provider_id not in ANGEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'")

    store.delete(provider_id)

    return {
        "success": True,
        "provider_id": provider_id,
        "message": f"Credentials deleted for {ANGEL_REGISTRY[provider_id].name}"
    }


@router.patch("/providers/{provider_id}/toggle")
async def toggle_provider(provider_id: str, request: ProviderToggleRequest):
    """Habilita o deshabilita un proveedor."""
    store = get_provider_store()

    if provider_id not in ANGEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'")

    cred = store.get(provider_id)
    if not cred:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_id}' not configured"
        )

    if request.enabled:
        store.enable(provider_id)
    else:
        store.disable(provider_id)

    return {
        "success": True,
        "provider_id": provider_id,
        "enabled": request.enabled
    }


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """
    Prueba la conexión con un proveedor.
    Realiza una llamada simple para verificar que las credenciales funcionan.
    """
    orchestrator = get_frangels_orchestrator()

    if provider_id not in ANGEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_id}'")

    try:
        result = await orchestrator.test_provider(provider_id)
        return result
    except Exception as e:
        log.error(f"Provider test failed for {provider_id}: {e}")
        return {
            "provider_id": provider_id,
            "success": False,
            "error": str(e),
            "latency_ms": 0
        }


# === QUOTA & USAGE ===

@router.get("/usage")
async def get_usage_stats():
    """
    Obtiene estadísticas de uso de todos los proveedores.
    Incluye uso diario, mensual y estado de cuotas.
    """
    quota_manager = get_quota_manager()
    return quota_manager.get_usage_stats()


@router.get("/quotas")
async def get_all_quotas():
    """Obtiene estado de cuotas de todos los proveedores configurados."""
    quota_manager = get_quota_manager()
    quotas = quota_manager.get_all_quotas()

    return {
        "quotas": [asdict(q) for q in quotas],
        "summary": {
            "total": len(quotas),
            "exhausted": len([q for q in quotas if q.is_exhausted]),
            "warning": len([q for q in quotas if 80 <= q.percentage < 100])
        }
    }


@router.get("/quotas/{provider_id}")
async def get_provider_quota(provider_id: str):
    """Obtiene estado de cuota de un proveedor específico."""
    quota_manager = get_quota_manager()

    status = quota_manager.get_quota_status(provider_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    return asdict(status)


# === CHAT UNIFICADO ===

@router.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Chat unificado usando proveedores Frangels.

    Selecciona automáticamente el mejor proveedor disponible según:
    - Cuotas disponibles
    - Capacidades requeridas (vision, tools)
    - Nivel de privacidad
    - Tier (premium primero)
    """
    orchestrator = get_frangels_orchestrator()

    # Convertir mensajes
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Determinar nivel de privacidad
    privacy_level = None
    if request.privacy_level:
        try:
            privacy_level = PrivacyLevel(request.privacy_level)
        except ValueError:
            pass

    try:
        result = await orchestrator.chat(
            messages=messages,
            model=request.model,
            preferred_provider=request.provider,
            category=request.category,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            require_vision=request.require_vision,
            require_tools=request.require_tools,
            min_privacy=privacy_level
        )

        return {
            "provider": result.provider_id,
            "model": result.model,
            "message": {
                "role": "assistant",
                "content": result.content
            },
            "usage": {
                "prompt_tokens": result.tokens_input,
                "completion_tokens": result.tokens_output,
                "total_tokens": result.tokens_input + result.tokens_output
            },
            "latency_ms": result.latency_ms,
            "cached": result.cached
        }

    except Exception as e:
        log.error(f"Frangels chat error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/chat/available-providers")
async def get_available_chat_providers():
    """
    Lista proveedores de inferencia disponibles para chat.
    Solo incluye los que tienen cuota disponible.
    """
    quota_manager = get_quota_manager()
    store = get_provider_store()

    available = []
    for provider_id, angel in ANGEL_REGISTRY.items():
        if angel.category != AngelCategory.INFERENCE:
            continue

        cred = store.get(provider_id)
        if not cred or not cred.enabled:
            continue

        if not quota_manager.can_use(provider_id):
            continue

        available.append({
            "id": provider_id,
            "name": angel.name,
            "tier": angel.tier.value,
            "models": angel.capabilities.models,
            "supports_vision": angel.capabilities.supports_vision,
            "supports_tools": angel.capabilities.supports_tools
        })

    # Ordenar por tier
    tier_order = {"premium": 0, "standard": 1, "economy": 2}
    available.sort(key=lambda x: tier_order.get(x["tier"], 3))

    return {
        "providers": available,
        "count": len(available)
    }


# === SISTEMA ===

@router.get("/status")
async def get_frangels_status():
    """Estado general del sistema Frangels."""
    store = get_provider_store()
    quota_manager = get_quota_manager()

    configured = store.list_configured()
    usage = quota_manager.get_usage_stats()

    # Contar proveedores disponibles por categoría
    available_by_category = {
        "inference": 0,
        "gpu": 0,
        "database": 0,
        "infra": 0
    }

    for provider_id, enabled in configured.items():
        if enabled:
            angel = ANGEL_REGISTRY.get(provider_id)
            if angel and quota_manager.can_use(provider_id):
                cat = angel.category.value
                if cat in available_by_category:
                    available_by_category[cat] += 1

    return {
        "status": "operational",
        "providers": {
            "configured": len(configured),
            "enabled": len([v for v in configured.values() if v]),
            "available_by_category": available_by_category
        },
        "usage": {
            "today": usage["today"],
            "this_month": usage["thisMonth"]
        },
        "estimated_monthly_value_usd": 650  # Valor aproximado de free tiers
    }


@router.post("/sync-env")
async def sync_from_environment():
    """
    Sincroniza credenciales desde variables de entorno.
    Útil para migración inicial desde .env
    """
    store = get_provider_store()

    before = len(store.list_configured())
    store.sync_from_env()
    after = len(store.list_configured())

    imported = after - before

    return {
        "success": True,
        "imported": imported,
        "total_configured": after,
        "message": f"Imported {imported} providers from environment variables"
    }


@router.get("/export-env")
async def export_to_environment():
    """
    Exporta credenciales configuradas como variables de entorno.
    Útil para backup o migración.
    """
    store = get_provider_store()
    env_vars = store.export_to_env()

    # Ofuscar valores para seguridad
    masked = {}
    for key, value in env_vars.items():
        if len(value) > 8:
            masked[key] = value[:4] + "*" * (len(value) - 8) + value[-4:]
        else:
            masked[key] = "*" * len(value)

    return {
        "env_vars": masked,
        "count": len(env_vars),
        "note": "Values are masked for security. Use 'download' parameter to get full values."
    }
