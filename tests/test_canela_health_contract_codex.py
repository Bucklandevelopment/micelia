"""
Tripwire cross-repo del contrato de health de canela-molida (DP-8, cerrada Ciclo 79).

DP-8 (C42): de los 4 dominios, `canela-molida` es el ÚNICO cuyo `/health` NO devuelve
`version` a nivel superior — emite un shape propio de diagnóstico RAG (`status`,
`embedding_model`, `embedding_cache`, `vectorstore`). Por eso en el registry/panel de
Micelia canela aparece con `version: null`. No es un bug (Micelia degrada limpio:
`ServiceStatus.version` es `str | None` y el registry lee `data.get("version")`), pero
rompe la homogeneidad del panel.

DECISIÓN (DP-8, cerrada): NO se fuerza el contrato estándar sobre canela desde esta
rutina — es deep-work en un hermano (fuera de scope) y ADEMÁS canela tiene WIP sin
commitear (`app/main.py` modificado), así que el guardarraíl "no tocar WIP de otros
repos" lo prohíbe. En su lugar se PINEA el estado auditado como contrato ejecutable:
Micelia YA maneja la ausencia (version→null), y este test lo verifica LEYENDO el
`/health` real de canela (read-only, como DP-11) en vez de confiar en un comentario.

Valor de tripwire: el día que canela AÑADA `version` a su `/health` (p.ej. en su WIP
actual), este test falla → señal para que Micelia empiece a consumirlo y el panel se
homogeneíce. Si canela no está en el checkout, SKIP (nunca falso-falla).

Solo lectura del código de canela (mismo árbol de proyectos, cero secretos) + import
del modelo de Micelia (sin DB). Test-only; no modifica `app/`, canela ni nada.
"""

import re
from pathlib import Path

import pytest

_PROJECTS = Path(__file__).resolve().parents[2]
_CANELA_MAIN = _PROJECTS / "canela-molida" / "app" / "main.py"


def _canela_health_return_keys() -> set[str] | None:
    """Claves del `return {…}` del handler `@app.get("/health")` de canela.

    Devuelve None si el fichero no está o el handler no se puede parsear con
    confianza (→ el test hace SKIP en vez de fallar en falso)."""
    if not _CANELA_MAIN.is_file():
        return None
    text = _CANELA_MAIN.read_text(encoding="utf-8")
    # Región del handler de /health: desde su decorador hasta el siguiente @app. o EOF.
    m = re.search(r'@app\.get\("/health"\)(.*?)(?:\n@app\.|\Z)', text, re.DOTALL)
    if not m:
        return None
    region = m.group(1)
    # El `return {…}` real (el docstring de ejemplo no usa `return {`). Los valores son
    # llamadas a función, sin dict-literales anidados → un solo nivel de llaves.
    ret = re.search(r"return\s*\{([^}]*)\}", region, re.DOTALL)
    if not ret:
        return None
    return set(re.findall(r'"([a-z_]+)"\s*:', ret.group(1)))


# --------------------------------------------------------------------------- #
# Lado MICELIA (siempre ejecutable): maneja la ausencia de version.
# --------------------------------------------------------------------------- #
def test_micelia_service_status_version_is_optional():
    """`ServiceStatus.version` acepta None → el `version: null` de canela no rompe el
    panel ni `/api/v1/health/services`."""
    from app.api.v1.health import ServiceStatus

    field = ServiceStatus.model_fields["version"]
    assert not field.is_required(), (
        "ServiceStatus.version dejó de ser opcional; el /health de canela (que omite "
        "version) provocaría un fallo de validación. Mantén version: str | None."
    )
    # Un ServiceStatus sin version debe construirse sin error (rama canela).
    canela = ServiceStatus(
        name="canela", url="http://localhost:3690", enabled=True, healthy=True
    )
    assert canela.version is None


# --------------------------------------------------------------------------- #
# Lado CANELA (cross-repo, SKIP si ausente): pin del estado auditado de DP-8.
# --------------------------------------------------------------------------- #
def test_canela_health_omits_version_but_serves_rag_shape():
    """
    Pin del contrato auditado (DP-8): el `/health` de canela emite su shape RAG
    (`status` + al menos `embedding_model`) y NO `version` a nivel superior.

    Mutación (la deseable): canela añade `"version": ...` a su `/health` → este test
    falla, señalando a Micelia que ya puede consumir `version` de canela y homogeneizar
    el panel. Cuando eso pase, actualiza este test para EXIGIR `version` y ajusta el
    registry/panel si hiciera falta.
    """
    keys = _canela_health_return_keys()
    if keys is None:
        pytest.skip(
            "canela-molida/app/main.py no presente o el handler /health no parseable; "
            "check cross-repo omitido (esperado en checkout aislado de Micelia)."
        )
    assert keys is not None  # narrowing tras el skip
    # Anti-vacío: el parser encontró un health con forma reconocible.
    assert "status" in keys, (
        f"el /health de canela no expone 'status' (claves halladas: {keys}); "
        f"¿cambió el handler? Revisa el parser antes de confiar en el pin."
    )
    assert "embedding_model" in keys, (
        f"el /health de canela ya no expone su shape RAG (embedding_model); claves: {keys}"
    )
    assert "version" not in keys, (
        "canela-molida/app/main.py:/health AHORA emite 'version' a nivel superior. "
        "DP-8 puede AVANZAR: haz que el registry/panel de Micelia lo consuma y actualiza "
        "este test para EXIGIR version (homogeneidad del panel alcanzable)."
    )
