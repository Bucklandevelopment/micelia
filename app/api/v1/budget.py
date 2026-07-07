"""
API Budget & Policy Engine: gestión de presupuestos y políticas de Frangels.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import verify_auth
from app.services.frangels.policy_engine import get_policy_engine

router = APIRouter(prefix="/budget", dependencies=[Depends(verify_auth)])


class BudgetUpdate(BaseModel):
    daily_limit_usd: Optional[float] = None
    monthly_limit_usd: Optional[float] = None


class CategoryPolicyUpdate(BaseModel):
    category: str
    policy: str  # free-first, paid-for-work, critical-reviewed, privacy-high, budget-cap


@router.get("/status")
async def budget_status():
    """Estado del presupuesto y políticas"""
    engine = get_policy_engine()
    return engine.get_status()


@router.patch("/limits")
async def update_budget(data: BudgetUpdate):
    """Actualizar límites de presupuesto"""
    engine = get_policy_engine()
    engine.set_budget(daily=data.daily_limit_usd, monthly=data.monthly_limit_usd)
    return {"success": True, "budget": engine.budget.to_dict()}


@router.post("/category-policy")
async def set_category_policy(data: CategoryPolicyUpdate):
    """Asignar política a una categoría"""
    engine = get_policy_engine()
    valid_policies = ["free-first", "paid-for-work", "critical-reviewed", "privacy-high", "budget-cap"]
    if data.policy not in valid_policies:
        raise HTTPException(400, f"Invalid policy. Must be one of: {valid_policies}")
    engine.set_category_policy(data.category, data.policy)
    return {"success": True, "category": data.category, "policy": data.policy}


@router.post("/evaluate")
async def evaluate_policy(category: str = "note", provider_policy: str = "free-first"):
    """Evaluar qué política se aplicaría a un prompt dado"""
    engine = get_policy_engine()
    decision = engine.evaluate({"category": category, "provider_policy": provider_policy})
    return {
        "prefer_paid": decision.prefer_paid,
        "force_free": decision.force_free,
        "require_different_reviewer": decision.require_different_reviewer,
        "budget_available": decision.budget_available,
        "reason": decision.reason,
    }
