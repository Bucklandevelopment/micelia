"""
Frangels Policy Engine: routing inteligente de proveedores por política.

Políticas:
- free-first: usa gratis salvo que falle SLA
- paid-for-work: prompts laborales y estratégicos usan paid
- critical-reviewed: executor + reviewer en proveedores distintos
- privacy-high: restringe a proveedores permitidos
- budget-cap: no superar techo diario o mensual
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class PolicyType(str, Enum):
    FREE_FIRST = "free-first"
    PAID_FOR_WORK = "paid-for-work"
    CRITICAL_REVIEWED = "critical-reviewed"
    PRIVACY_HIGH = "privacy-high"
    BUDGET_CAP = "budget-cap"


@dataclass
class Budget:
    """Presupuesto configurable"""
    daily_limit_usd: float = 5.0
    monthly_limit_usd: float = 50.0
    spent_today_usd: float = 0.0
    spent_this_month_usd: float = 0.0
    last_reset_date: Optional[date] = None
    last_reset_month: Optional[int] = None

    def can_spend(self, amount_usd: float) -> bool:
        self._auto_reset()
        return (
            self.spent_today_usd + amount_usd <= self.daily_limit_usd
            and self.spent_this_month_usd + amount_usd <= self.monthly_limit_usd
        )

    def record_spend(self, amount_usd: float):
        self._auto_reset()
        self.spent_today_usd += amount_usd
        self.spent_this_month_usd += amount_usd

    def _auto_reset(self):
        today = date.today()
        if self.last_reset_date != today:
            self.spent_today_usd = 0.0
            self.last_reset_date = today
        if self.last_reset_month != today.month:
            self.spent_this_month_usd = 0.0
            self.last_reset_month = today.month

    def to_dict(self) -> dict:
        self._auto_reset()
        return {
            "daily_limit_usd": self.daily_limit_usd,
            "monthly_limit_usd": self.monthly_limit_usd,
            "spent_today_usd": round(self.spent_today_usd, 4),
            "spent_this_month_usd": round(self.spent_this_month_usd, 4),
            "remaining_today_usd": round(self.daily_limit_usd - self.spent_today_usd, 4),
            "remaining_month_usd": round(self.monthly_limit_usd - self.spent_this_month_usd, 4),
        }


@dataclass
class PolicyDecision:
    """Resultado de evaluar una política"""
    prefer_paid: bool = False
    force_free: bool = False
    require_different_reviewer: bool = False
    allowed_providers: Optional[List[str]] = None
    blocked_providers: Optional[List[str]] = None
    budget_available: bool = True
    reason: str = ""


@dataclass
class ProviderRoute:
    """Ruta de proveedor seleccionada"""
    provider_id: str
    is_paid: bool
    policy_applied: str
    fallback_chain: List[str] = field(default_factory=list)


# Category sets
WORK_CATEGORIES = {"work", "plan", "project"}
SENSITIVE_CATEGORIES = {"work", "plan", "project", "personal"}
PRIVACY_SENSITIVE = {"personal", "health"}


class PolicyEngine:
    """
    Motor de políticas para routing de proveedores.
    """

    def __init__(self):
        self.budget = Budget()
        self._policies: Dict[str, PolicyType] = {}
        self._category_overrides: Dict[str, str] = {}

    def evaluate(self, prompt: dict) -> PolicyDecision:
        """
        Evalúa qué política aplicar dado un prompt.

        Args:
            prompt: dict con category, tags, provider_policy, etc.

        Returns:
            PolicyDecision con las reglas a aplicar
        """
        policy_name = prompt.get("provider_policy", "free-first")
        category = prompt.get("category", "note")
        decision = PolicyDecision()

        # Apply category override if exists
        if category in self._category_overrides:
            policy_name = self._category_overrides[category]

        try:
            policy = PolicyType(policy_name)
        except ValueError:
            policy = PolicyType.FREE_FIRST

        if policy == PolicyType.FREE_FIRST:
            decision.prefer_paid = False
            decision.force_free = True
            decision.reason = "Free-first: using free providers"

        elif policy == PolicyType.PAID_FOR_WORK:
            if category in WORK_CATEGORIES:
                decision.prefer_paid = True
                decision.reason = f"Paid-for-work: category '{category}' uses paid providers"
            else:
                decision.force_free = True
                decision.reason = f"Paid-for-work: category '{category}' stays free"

        elif policy == PolicyType.CRITICAL_REVIEWED:
            decision.prefer_paid = True
            decision.require_different_reviewer = True
            decision.reason = "Critical-reviewed: executor and reviewer on different providers"

        elif policy == PolicyType.PRIVACY_HIGH:
            decision.prefer_paid = False
            decision.blocked_providers = ["openai", "anthropic"]  # Restrict to local/self-hosted
            decision.reason = "Privacy-high: restricted to local providers only"

        elif policy == PolicyType.BUDGET_CAP:
            estimated_cost = 0.005  # $0.005 per request estimate
            if self.budget.can_spend(estimated_cost):
                decision.prefer_paid = True
                decision.budget_available = True
                decision.reason = f"Budget-cap: ${self.budget.spent_today_usd:.3f}/${self.budget.daily_limit_usd:.2f} daily"
            else:
                decision.force_free = True
                decision.budget_available = False
                decision.reason = "Budget-cap: daily limit reached, forcing free providers"

        return decision

    def record_cost(self, cost_usd: float):
        """Registra un gasto"""
        self.budget.record_spend(cost_usd)

    def set_budget(self, daily: float = None, monthly: float = None):
        """Configura presupuesto"""
        if daily is not None:
            self.budget.daily_limit_usd = daily
        if monthly is not None:
            self.budget.monthly_limit_usd = monthly

    def set_category_policy(self, category: str, policy: str):
        """Asigna una política a una categoría específica"""
        self._category_overrides[category] = policy

    def get_status(self) -> dict:
        """Estado completo del policy engine"""
        return {
            "budget": self.budget.to_dict(),
            "category_overrides": dict(self._category_overrides),
            "available_policies": [p.value for p in PolicyType],
        }


# Singleton
_policy_engine: Optional[PolicyEngine] = None

def get_policy_engine() -> PolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
