"""
Tripwire que ata los response_model del router de prompts (DP-10) a los serializers
REALES del store, para que el modelo no drifte de lo que el store devuelve.

Contexto (Ciclo 78, cierre de DP-10): C52 observó que los GET del router de prompts
devolvían el dict del store SIN `response_model` → el contrato con el panel se sostenía
solo por tests de serialización, no por el schema de FastAPI. C78 añade los
response_model (`PromptOut`, `PromptListOut`, `PromptStatsOut` + wrappers) con
`extra="allow"` + `response_model_exclude_unset=True` (non-lossy: no añaden ni quitan
claves; documentan el shape en OpenAPI). Como `extra="allow"` permite claves no
declaradas, un campo nuevo en `_prompt_to_dict` NO rompería runtime pero quedaría
FUERA del schema de OpenAPI (sub-documentado). Este test lo caza: el set de campos
declarados de cada modelo == el set de claves del serializer correspondiente del store.

Mutación: añade una clave a `_prompt_to_dict` (`app/services/prompt_store.py`) sin
declararla en `PromptOut` → falla, obligando a mantener el modelo y el store en
lockstep. El inverso (declarar en el modelo una clave que el store no emite) también
rompe. Test-only; lee el código del store (mismo repo) e importa los modelos (sin DB).
"""

import inspect
import re

from app.api.v1 import prompts as prompts_router
from app.services.prompt_store import PromptStore


def _return_dict_keys(func) -> set[str]:
    """Claves del dict-literal `return { "k": ... }` del cuerpo de una función."""
    src = inspect.getsource(func)
    # Toma desde el último `return {` hasta el cierre; captura las claves "..." de nivel.
    m = re.search(r"return\s*\{(.*?)\n\s*\}", src, re.DOTALL)
    assert m, f"no se encontró un `return {{...}}` en {func.__qualname__}"
    body = m.group(1)
    # Claves de primer nivel: `"key":` (ignora dicts anidados por indentación mínima).
    return set(re.findall(r'"([a-z_]+)"\s*:', body))


def _model_fields(model) -> set[str]:
    return set(model.model_fields.keys())


# --------------------------------------------------------------------------- #
# Guards anti-vacío.
# --------------------------------------------------------------------------- #
def test_serializer_keys_are_not_vacuously_empty():
    assert len(_return_dict_keys(PromptStore._prompt_to_dict)) >= 20
    assert len(_return_dict_keys(PromptStore._list_to_dict)) >= 8
    assert len(_return_dict_keys(PromptStore.get_stats)) >= 6


# --------------------------------------------------------------------------- #
# Los pins: cada modelo declara EXACTAMENTE las claves de su serializer.
# --------------------------------------------------------------------------- #
def test_prompt_out_matches_prompt_to_dict():
    """`PromptOut` (response_model de get_prompt y de los items de las listas) declara
    exactamente las claves de `PromptStore._prompt_to_dict`."""
    store_keys = _return_dict_keys(PromptStore._prompt_to_dict)
    model_keys = _model_fields(prompts_router.PromptOut)
    assert model_keys == store_keys, (
        f"DRIFT PromptOut ↔ _prompt_to_dict:\n"
        f"  solo en el store (falta declarar → sub-documentado en OpenAPI): "
        f"{store_keys - model_keys}\n"
        f"  solo en el modelo (declarado pero el store no lo emite): "
        f"{model_keys - store_keys}\n"
        f"Mantén app/api/v1/prompts.py:PromptOut y prompt_store._prompt_to_dict en lockstep."
    )


def test_prompt_list_out_matches_list_to_dict():
    store_keys = _return_dict_keys(PromptStore._list_to_dict)
    model_keys = _model_fields(prompts_router.PromptListOut)
    assert model_keys == store_keys, (
        f"DRIFT PromptListOut ↔ _list_to_dict: "
        f"store-only={store_keys - model_keys}, model-only={model_keys - store_keys}"
    )


def test_prompt_stats_out_matches_get_stats():
    store_keys = _return_dict_keys(PromptStore.get_stats)
    model_keys = _model_fields(prompts_router.PromptStatsOut)
    assert model_keys == store_keys, (
        f"DRIFT PromptStatsOut ↔ get_stats: "
        f"store-only={store_keys - model_keys}, model-only={model_keys - store_keys}"
    )


def test_wrapper_models_declare_their_structural_keys():
    """Los wrappers documentan las claves que el endpoint construye (no el item)."""
    assert _model_fields(prompts_router.PromptListResponse) == {
        "prompts", "count", "limit", "offset", "total",
    }
    assert _model_fields(prompts_router.PromptCollectionView) == {"prompts", "count", "view"}
    assert _model_fields(prompts_router.PromptArchiveResponse) == {
        "prompts", "total", "limit", "offset",
    }
    assert _model_fields(prompts_router.PromptListsResponse) == {"lists", "count"}
