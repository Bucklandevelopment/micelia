"""
Tests for the thin registry helpers of app.services.frangels.angels.

`get_inference_angels()` and `get_available_angels()` were the only two
uncovered lines of the module (455, 460). The ANGEL_REGISTRY is static data,
so these are pure lookups — no infra, no network.
"""

from app.services.frangels.angels import (
    ANGEL_REGISTRY,
    AngelCategory,
    get_angels_by_category,
    get_available_angels,
    get_inference_angels,
)


def test_get_inference_angels_matches_category():
    angels = get_inference_angels()
    assert angels  # el registro incluye ángeles de inferencia (groq, gemini, ...)
    assert all(a.category == AngelCategory.INFERENCE for a in angels)
    # Equivalente a filtrar por categoría INFERENCE directamente.
    assert {a.id for a in angels} == {
        a.id for a in get_angels_by_category(AngelCategory.INFERENCE)
    }


def test_get_available_angels_filters_by_health():
    available = get_available_angels()
    # Todo ángel devuelto se declara disponible; los no disponibles se excluyen.
    assert all(a.health.is_available for a in available)
    assert len(available) <= len(ANGEL_REGISTRY)
