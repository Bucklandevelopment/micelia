"""
Frangels Orchestrator - Orquestación inteligente de proveedores cloud
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.logging import log

from .angels import ANGEL_REGISTRY, Angel, AngelCategory, PrivacyLevel
from .provider_store import get_provider_store
from .quota_manager import get_quota_manager


@dataclass
class AngelSelection:
    """Resultado de selección de ángel"""
    angel: Angel
    model: str
    reasoning: List[str]
    fallbacks: List[Angel]
    estimated_latency_ms: float


@dataclass
class InferenceResult:
    """Resultado de inferencia de un ángel"""
    provider_id: str
    model: str
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    success: bool
    error: Optional[str] = None


class FrangelsOrchestrator:
    """
    Orquestador principal de Frangels.
    Selecciona el mejor ángel disponible y ejecuta tareas.
    """

    def __init__(self):
        self.provider_store = get_provider_store()
        self.quota_manager = get_quota_manager()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtiene cliente HTTP reutilizable"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    def get_configured_providers(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene estado de todos los proveedores"""
        result = {}
        configured = self.provider_store.get_all_status()

        for provider_id, angel in ANGEL_REGISTRY.items():
            status = configured.get(provider_id, {})
            result[provider_id] = {
                "id": provider_id,
                "name": angel.name,
                "category": angel.category.value,
                "tier": angel.tier.value,
                "configured": status.get("configured", False),
                "enabled": status.get("enabled", False),
                "healthy": angel.health.is_available,
                "lastCheck": angel.health.last_check.isoformat() if angel.health.last_check else None,
                "error": angel.health.last_error
            }

        return result

    async def test_provider(self, provider_id: str) -> Dict[str, Any]:
        """Prueba conexión con un proveedor"""
        angel = ANGEL_REGISTRY.get(provider_id)
        if not angel:
            return {"healthy": False, "error": "Provider not found"}

        api_key = self.provider_store.get_api_key(provider_id)
        if not api_key:
            return {"healthy": False, "error": "API key not configured"}

        try:
            client = await self._get_client()
            start = datetime.now(timezone.utc)

            # Test específico por proveedor
            if provider_id == "groq":
                result = await self._test_groq(client, api_key)
            elif provider_id == "gemini":
                result = await self._test_gemini(client, api_key)
            elif provider_id == "deepseek":
                result = await self._test_deepseek(client, api_key)
            elif provider_id == "cohere":
                result = await self._test_cohere(client, api_key)
            elif provider_id == "mistral":
                result = await self._test_mistral(client, api_key)
            elif provider_id == "openrouter":
                result = await self._test_openrouter(client, api_key)
            else:
                # Test genérico
                result = await self._test_generic(client, angel.base_url, api_key)

            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            # Actualizar health del angel
            angel.health.is_available = result["healthy"]
            angel.health.last_check = datetime.now(timezone.utc)
            angel.health.latency_ms = latency_ms
            angel.health.last_error = result.get("error")

            return {
                "healthy": result["healthy"],
                "latency_ms": latency_ms,
                "error": result.get("error")
            }

        except Exception as e:
            angel.health.is_available = False
            angel.health.last_check = datetime.now(timezone.utc)
            angel.health.last_error = str(e)
            return {"healthy": False, "error": str(e)}

    async def _test_groq(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test Groq API"""
        response = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_gemini(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test Google AI Studio API"""
        response = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_deepseek(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test DeepSeek API"""
        response = await client.get(
            "https://api.deepseek.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_cohere(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test Cohere API"""
        response = await client.get(
            "https://api.cohere.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_mistral(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test Mistral API"""
        response = await client.get(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_openrouter(self, client: httpx.AsyncClient, api_key: str) -> Dict:
        """Test OpenRouter API"""
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False, "error": f"HTTP {response.status_code}"}

    async def _test_generic(self, client: httpx.AsyncClient,
                           base_url: str, api_key: str) -> Dict:
        """Test genérico de conectividad"""
        try:
            response = await client.head(base_url, timeout=10)
            return {"healthy": response.status_code < 500}
        except Exception:
            return {"healthy": False, "error": "Connection failed"}

    def select_angel(self, category: str = "inference",
                     privacy_required: str = "medium",
                     require_vision: bool = False,
                     require_tools: bool = False,
                     min_context: int = 0) -> Optional[AngelSelection]:
        """
        Selecciona el mejor ángel disponible según criterios.
        """
        try:
            cat = AngelCategory(category)
        except ValueError:
            cat = AngelCategory.INFERENCE

        try:
            privacy = PrivacyLevel(privacy_required)
        except ValueError:
            privacy = PrivacyLevel.MEDIUM

        # Filtrar ángeles elegibles
        eligible = []
        for angel in ANGEL_REGISTRY.values():
            if angel.category != cat:
                continue

            # Verificar credenciales configuradas
            if not self.provider_store.get_api_key(angel.id):
                continue

            # Verificar cuota disponible
            if not self.quota_manager.can_use(angel.id):
                continue

            # Verificar privacidad
            privacy_levels = {
                PrivacyLevel.HIGH: [PrivacyLevel.HIGH],
                PrivacyLevel.MEDIUM: [PrivacyLevel.HIGH, PrivacyLevel.MEDIUM],
                PrivacyLevel.LOW: [PrivacyLevel.HIGH, PrivacyLevel.MEDIUM, PrivacyLevel.LOW]
            }
            if angel.privacy_level not in privacy_levels.get(privacy, []):
                continue

            # Verificar capacidades
            if require_vision and not angel.capabilities.supports_vision:
                continue
            if require_tools and not angel.capabilities.supports_tools:
                continue
            if min_context > 0 and angel.capabilities.max_context_tokens < min_context:
                continue

            eligible.append(angel)

        if not eligible:
            return None

        # Ordenar por tier y salud
        tier_order = {"premium": 0, "standard": 1, "economy": 2}
        eligible.sort(key=lambda a: (
            tier_order.get(a.tier.value, 3),
            0 if a.health.is_available else 1,
            a.health.latency_ms or 9999
        ))

        best = eligible[0]
        model = best.capabilities.models[0] if best.capabilities.models else ""

        reasoning = [
            f"Seleccionado {best.name} (tier: {best.tier.value})",
            f"Privacidad: {best.privacy_level.value}",
            "Cuota disponible: Sí"
        ]
        if best.health.is_available:
            reasoning.append(f"Latencia: {best.health.latency_ms:.0f}ms")

        return AngelSelection(
            angel=best,
            model=model,
            reasoning=reasoning,
            fallbacks=eligible[1:4],
            estimated_latency_ms=best.health.latency_ms or 1000
        )

    async def chat(self, messages: List[Dict[str, str]],
                   model: Optional[str] = None,
                   provider_id: Optional[str] = None,
                   prefer_paid: bool = False,
                   **kwargs) -> InferenceResult:
        """
        Ejecuta chat con el mejor ángel disponible.
        Si prefer_paid=True, intenta OpenAI/Anthropic primero.
        """
        # Intentar paid providers primero si se solicita
        if prefer_paid and not provider_id:
            paid_result = await self._try_paid_provider(messages, model)
            if paid_result and paid_result.success:
                return paid_result

        # Seleccionar proveedor free si no se especifica
        if not provider_id:
            selection = self.select_angel(
                category="inference",
                require_vision=kwargs.get("require_vision", False),
                require_tools=kwargs.get("require_tools", False)
            )
            if not selection:
                return InferenceResult(
                    provider_id="none",
                    model="",
                    content="",
                    tokens_input=0,
                    tokens_output=0,
                    latency_ms=0,
                    success=False,
                    error="No providers available"
                )
            provider_id = selection.angel.id
            model = model or selection.model

        # Handle paid providers que no están en ANGEL_REGISTRY
        if provider_id in ("openai", "anthropic"):
            return await self._chat_paid_provider(provider_id, model, messages)

        angel = ANGEL_REGISTRY.get(provider_id)
        if not angel:
            return InferenceResult(
                provider_id=provider_id,
                model=model or "",
                content="",
                tokens_input=0,
                tokens_output=0,
                latency_ms=0,
                success=False,
                error="Provider not found"
            )

        api_key = self.provider_store.get_api_key(provider_id)
        if not api_key:
            return InferenceResult(
                provider_id=provider_id,
                model=model or "",
                content="",
                tokens_input=0,
                tokens_output=0,
                latency_ms=0,
                success=False,
                error="API key not configured"
            )

        model = model or (angel.capabilities.models[0] if angel.capabilities.models else "")

        try:
            client = await self._get_client()
            start = datetime.now(timezone.utc)

            # Ejecutar según proveedor
            if provider_id == "groq":
                result = await self._chat_groq(client, api_key, model, messages)
            elif provider_id == "gemini":
                result = await self._chat_gemini(client, api_key, model, messages)
            elif provider_id == "deepseek":
                result = await self._chat_deepseek(client, api_key, model, messages)
            elif provider_id == "openrouter":
                result = await self._chat_openrouter(client, api_key, model, messages)
            else:
                # OpenAI-compatible por defecto
                result = await self._chat_openai_compatible(
                    client, angel.base_url, api_key, model, messages
                )

            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            # Registrar uso
            self.quota_manager.record_usage(
                provider_id,
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                latency_ms=latency_ms,
                success=result.get("success", True)
            )
            self.provider_store.mark_used(provider_id)

            return InferenceResult(
                provider_id=provider_id,
                model=model,
                content=result.get("content", ""),
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                latency_ms=latency_ms,
                success=result.get("success", True),
                error=result.get("error")
            )

        except Exception as e:
            log.error(f"Frangels chat error with {provider_id}: {e}")
            self.quota_manager.record_usage(
                provider_id, success=False, error=str(e)
            )
            return InferenceResult(
                provider_id=provider_id,
                model=model,
                content="",
                tokens_input=0,
                tokens_output=0,
                latency_ms=0,
                success=False,
                error=str(e)
            )

    async def _chat_groq(self, client: httpx.AsyncClient, api_key: str,
                         model: str, messages: List[Dict]) -> Dict:
        """Chat con Groq"""
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages}
        )
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}"}

        data = response.json()
        return {
            "success": True,
            "content": data["choices"][0]["message"]["content"],
            "tokens_input": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_output": data.get("usage", {}).get("completion_tokens", 0)
        }

    async def _chat_gemini(self, client: httpx.AsyncClient, api_key: str,
                           model: str, messages: List[Dict]) -> Dict:
        """Chat con Gemini"""
        # Convertir formato de mensajes
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            json={"contents": contents}
        )
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}"}

        data = response.json()
        content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

        return {
            "success": True,
            "content": content,
            "tokens_input": data.get("usageMetadata", {}).get("promptTokenCount", 0),
            "tokens_output": data.get("usageMetadata", {}).get("candidatesTokenCount", 0)
        }

    async def _chat_deepseek(self, client: httpx.AsyncClient, api_key: str,
                             model: str, messages: List[Dict]) -> Dict:
        """Chat con DeepSeek (OpenAI compatible)"""
        return await self._chat_openai_compatible(
            client, "https://api.deepseek.com/v1", api_key, model, messages
        )

    async def _chat_openrouter(self, client: httpx.AsyncClient, api_key: str,
                               model: str, messages: List[Dict]) -> Dict:
        """Chat con OpenRouter"""
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://idm-panel.local",
                "X-Title": "IDM Panel"
            },
            json={"model": model, "messages": messages}
        )
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}"}

        data = response.json()
        return {
            "success": True,
            "content": data["choices"][0]["message"]["content"],
            "tokens_input": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_output": data.get("usage", {}).get("completion_tokens", 0)
        }

    async def _chat_openai_compatible(self, client: httpx.AsyncClient,
                                       base_url: str, api_key: str,
                                       model: str, messages: List[Dict]) -> Dict:
        """Chat con API compatible con OpenAI"""
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages}
        )
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}"}

        data = response.json()
        return {
            "success": True,
            "content": data["choices"][0]["message"]["content"],
            "tokens_input": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_output": data.get("usage", {}).get("completion_tokens", 0)
        }


    async def _try_paid_provider(self, messages: List[Dict], model: Optional[str]) -> Optional[InferenceResult]:
        """Intenta usar un provider de pago (OpenAI o Anthropic)"""
        from app.core.config import settings

        # Intentar OpenAI primero
        openai_key = self.provider_store.get_api_key("openai") or settings.openai_api_key
        if openai_key and self.quota_manager.can_use("openai"):
            result = await self._chat_paid_provider("openai", model or "gpt-4o", messages)
            if result.success:
                return result

        # Intentar Anthropic
        anthropic_key = self.provider_store.get_api_key("anthropic") or settings.anthropic_api_key
        if anthropic_key and self.quota_manager.can_use("anthropic"):
            result = await self._chat_paid_provider("anthropic", model or "claude-sonnet-4-20250514", messages)
            if result.success:
                return result

        return None

    async def _chat_paid_provider(self, provider_id: str, model: Optional[str],
                                   messages: List[Dict]) -> InferenceResult:
        """Chat con provider de pago (OpenAI o Anthropic)"""
        from app.core.config import settings

        api_key = self.provider_store.get_api_key(provider_id)
        if not api_key:
            # Fallback a config
            if provider_id == "openai":
                api_key = settings.openai_api_key
            elif provider_id == "anthropic":
                api_key = settings.anthropic_api_key

        if not api_key:
            return InferenceResult(
                provider_id=provider_id, model=model or "", content="",
                tokens_input=0, tokens_output=0, latency_ms=0,
                success=False, error=f"{provider_id} API key not configured"
            )

        try:
            client = await self._get_client()
            start = datetime.now(timezone.utc)

            if provider_id == "openai":
                result = await self._chat_openai(client, api_key, model or "gpt-4o", messages)
            elif provider_id == "anthropic":
                result = await self._chat_anthropic(client, api_key, model or "claude-sonnet-4-20250514", messages)
            else:
                return InferenceResult(
                    provider_id=provider_id, model=model or "", content="",
                    tokens_input=0, tokens_output=0, latency_ms=0,
                    success=False, error="Unknown paid provider"
                )

            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            # Calcular costo
            cost_per_1k = {"openai": 0.005, "anthropic": 0.003}.get(provider_id, 0.005)
            total_tokens = result.get("tokens_input", 0) + result.get("tokens_output", 0)
            cost_usd = (total_tokens / 1000) * cost_per_1k

            self.quota_manager.record_usage(
                provider_id,
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                latency_ms=latency_ms,
                success=result.get("success", True),
                cost_usd=cost_usd
            )

            return InferenceResult(
                provider_id=provider_id,
                model=model or "",
                content=result.get("content", ""),
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                latency_ms=latency_ms,
                success=result.get("success", True),
                error=result.get("error")
            )

        except Exception as e:
            log.error(f"Paid provider {provider_id} error: {e}")
            return InferenceResult(
                provider_id=provider_id, model=model or "", content="",
                tokens_input=0, tokens_output=0, latency_ms=0,
                success=False, error=str(e)
            )

    async def _chat_openai(self, client: httpx.AsyncClient, api_key: str,
                            model: str, messages: List[Dict]) -> Dict:
        """Chat con OpenAI API"""
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages}
        )
        if response.status_code != 200:
            return {"success": False, "error": f"OpenAI HTTP {response.status_code}"}

        data = response.json()
        return {
            "success": True,
            "content": data["choices"][0]["message"]["content"],
            "tokens_input": data.get("usage", {}).get("prompt_tokens", 0),
            "tokens_output": data.get("usage", {}).get("completion_tokens", 0)
        }

    async def _chat_anthropic(self, client: httpx.AsyncClient, api_key: str,
                               model: str, messages: List[Dict]) -> Dict:
        """Chat con Anthropic API"""
        # Separar system message
        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        body = {
            "model": model,
            "max_tokens": 4096,
            "messages": user_messages
        }
        if system_msg:
            body["system"] = system_msg

        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=body
        )
        if response.status_code != 200:
            return {"success": False, "error": f"Anthropic HTTP {response.status_code}"}

        data = response.json()
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return {
            "success": True,
            "content": content,
            "tokens_input": data.get("usage", {}).get("input_tokens", 0),
            "tokens_output": data.get("usage", {}).get("output_tokens", 0)
        }


# Singleton global
_orchestrator: Optional[FrangelsOrchestrator] = None


def get_frangels_orchestrator() -> FrangelsOrchestrator:
    """Obtiene la instancia singleton del orquestador"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = FrangelsOrchestrator()
    return _orchestrator
