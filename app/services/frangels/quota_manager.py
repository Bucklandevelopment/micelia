"""
Quota Manager - Gestión de cuotas y uso de proveedores
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.logging import log

from .angels import ANGEL_REGISTRY


@dataclass
class UsageRecord:
    """Registro de uso de un proveedor"""
    provider_id: str
    timestamp: str
    requests: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0
    success: bool = True
    error: Optional[str] = None


@dataclass
class ProviderUsage:
    """Uso acumulado de un proveedor"""
    provider_id: str
    requests_today: int = 0
    requests_this_minute: int = 0
    tokens_today: int = 0
    tokens_this_minute: int = 0
    last_request: Optional[str] = None
    last_reset_day: str = ""
    last_reset_minute: str = ""
    errors_24h: int = 0


@dataclass
class QuotaStatus:
    """Estado de cuota de un proveedor"""
    provider_id: str
    provider_name: str
    category: str
    used: int
    limit: int
    unit: str
    percentage: float
    reset_time: str
    is_exhausted: bool = False


class QuotaManager:
    """
    Gestiona cuotas y uso de proveedores cloud.
    Trackea uso en tiempo real y determina disponibilidad.
    """

    def __init__(self, storage_path: str = "./data/frangels"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.usage_file = self.storage_path / "usage.json"
        self._usage: Dict[str, ProviderUsage] = {}
        self._history: List[UsageRecord] = []
        self._load()

    def _load(self):
        """Carga datos de uso desde disco"""
        if not self.usage_file.exists():
            return

        try:
            data = json.loads(self.usage_file.read_text())
            self._usage = {
                k: ProviderUsage(**v) for k, v in data.get("usage", {}).items()
            }
            self._history = [
                UsageRecord(**r) for r in data.get("history", [])[-1000:]  # Últimos 1000
            ]
        except Exception as e:
            log.error(f"Failed to load usage data: {e}")

    def _save(self):
        """Guarda datos de uso a disco"""
        try:
            data = {
                "usage": {k: asdict(v) for k, v in self._usage.items()},
                "history": [asdict(r) for r in self._history[-1000:]]
            }
            self.usage_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.error(f"Failed to save usage data: {e}")

    def _get_usage(self, provider_id: str) -> ProviderUsage:
        """Obtiene o crea registro de uso para un proveedor"""
        if provider_id not in self._usage:
            self._usage[provider_id] = ProviderUsage(provider_id=provider_id)
        return self._usage[provider_id]

    def _check_reset(self, usage: ProviderUsage):
        """Verifica si hay que resetear contadores"""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        this_minute = now.strftime("%Y-%m-%d %H:%M")

        if usage.last_reset_day != today:
            usage.requests_today = 0
            usage.tokens_today = 0
            usage.errors_24h = 0
            usage.last_reset_day = today

        if usage.last_reset_minute != this_minute:
            usage.requests_this_minute = 0
            usage.tokens_this_minute = 0
            usage.last_reset_minute = this_minute

    def record_usage(self, provider_id: str, tokens_input: int = 0,
                     tokens_output: int = 0, latency_ms: float = 0,
                     success: bool = True, error: Optional[str] = None,
                     cost_usd: float = 0.0):
        """Registra uso de un proveedor (soporta paid providers con cost_usd)"""
        usage = self._get_usage(provider_id)
        self._check_reset(usage)

        # Actualizar contadores
        usage.requests_today += 1
        usage.requests_this_minute += 1
        usage.tokens_today += tokens_input + tokens_output
        usage.tokens_this_minute += tokens_input + tokens_output
        usage.last_request = datetime.now(timezone.utc).isoformat()

        if not success:
            usage.errors_24h += 1

        # Agregar a historial
        self._history.append(UsageRecord(
            provider_id=provider_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            requests=1,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=latency_ms,
            success=success,
            error=error
        ))

        self._save()

    def can_use(self, provider_id: str) -> bool:
        """Verifica si un proveedor puede usarse (no agotó cuota)"""
        angel = ANGEL_REGISTRY.get(provider_id)
        if not angel:
            # Paid providers (openai, anthropic) no están en registry
            # pero pueden usarse si tienen key configurada
            if provider_id in ("openai", "anthropic"):
                return True
            return False

        usage = self._get_usage(provider_id)
        self._check_reset(usage)

        quota = angel.quota

        # Verificar límites por minuto
        if quota.requests_per_minute > 0:
            if usage.requests_this_minute >= quota.requests_per_minute:
                return False

        if quota.tokens_per_minute > 0:
            if usage.tokens_this_minute >= quota.tokens_per_minute:
                return False

        # Verificar límites diarios
        if quota.requests_per_day > 0:
            if usage.requests_today >= quota.requests_per_day:
                return False

        if quota.tokens_per_day > 0:
            if usage.tokens_today >= quota.tokens_per_day:
                return False

        return True

    def get_quota_status(self, provider_id: str) -> Optional[QuotaStatus]:
        """Obtiene estado de cuota de un proveedor"""
        angel = ANGEL_REGISTRY.get(provider_id)
        if not angel:
            return None

        usage = self._get_usage(provider_id)
        self._check_reset(usage)

        quota = angel.quota

        # Determinar el límite principal
        if quota.requests_per_day > 0:
            used = usage.requests_today
            limit = quota.requests_per_day
            unit = "requests"
            reset_time = "Mañana 00:00 UTC"
        elif quota.tokens_per_day > 0:
            used = usage.tokens_today
            limit = quota.tokens_per_day
            unit = "tokens"
            reset_time = "Mañana 00:00 UTC"
        elif quota.tokens_per_minute > 0:
            used = usage.tokens_this_minute
            limit = quota.tokens_per_minute
            unit = "tokens/min"
            reset_time = "Próximo minuto"
        else:
            used = usage.requests_today
            limit = 10000  # Ilimitado
            unit = "requests"
            reset_time = "N/A"

        percentage = (used / limit * 100) if limit > 0 else 0

        return QuotaStatus(
            provider_id=provider_id,
            provider_name=angel.name,
            category=angel.category.value,
            used=used,
            limit=limit,
            unit=unit,
            percentage=min(percentage, 100),
            reset_time=reset_time,
            is_exhausted=percentage >= 100
        )

    def get_all_quotas(self) -> List[QuotaStatus]:
        """Obtiene estado de cuotas de todos los proveedores configurados"""
        quotas = []
        for provider_id in self._usage.keys():
            status = self.get_quota_status(provider_id)
            if status:
                quotas.append(status)
        return quotas

    def get_usage_stats(self) -> Dict:
        """Obtiene estadísticas de uso agregadas"""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        month_start = now.replace(day=1).strftime("%Y-%m-%d")

        # Filtrar historial
        today_records = [r for r in self._history if r.timestamp.startswith(today)]
        month_records = [r for r in self._history if r.timestamp >= month_start]

        def aggregate(records: List[UsageRecord]) -> Dict:
            total_requests = sum(r.requests for r in records)
            total_tokens = sum(r.tokens_input + r.tokens_output for r in records)
            # Estimación de costo equivalente ($0.002 por 1K tokens promedio)
            cost_equivalent = total_tokens / 1000 * 0.002
            return {
                "requests": total_requests,
                "tokens": total_tokens,
                "cost_equivalent_usd": round(cost_equivalent, 4)
            }

        return {
            "today": aggregate(today_records),
            "thisMonth": aggregate(month_records),
            "quotas": [asdict(q) for q in self.get_all_quotas()]
        }

    def get_best_provider(self, category: str = "inference",
                          require_vision: bool = False,
                          require_tools: bool = False,
                          min_context: int = 0) -> Optional[str]:
        """
        Obtiene el mejor proveedor disponible según criterios.
        Considera cuotas, tier y capacidades.
        """
        from .angels import AngelCategory, get_angels_by_category

        try:
            cat = AngelCategory(category)
        except ValueError:
            cat = AngelCategory.INFERENCE

        angels = get_angels_by_category(cat)

        # Filtrar por capacidades
        eligible = []
        for angel in angels:
            if require_vision and not angel.capabilities.supports_vision:
                continue
            if require_tools and not angel.capabilities.supports_tools:
                continue
            if min_context > 0 and angel.capabilities.max_context_tokens < min_context:
                continue
            if not self.can_use(angel.id):
                continue
            eligible.append(angel)

        if not eligible:
            return None

        # Ordenar por tier (premium primero)
        tier_order = {"premium": 0, "standard": 1, "economy": 2}
        eligible.sort(key=lambda a: tier_order.get(a.tier.value, 3))

        return eligible[0].id


# Singleton global
_quota_manager: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """Obtiene la instancia singleton del quota manager"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = QuotaManager()
    return _quota_manager
