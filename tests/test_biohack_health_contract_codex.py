"""
Tripwire cross-repo del contrato de health de biohack-app (C91).

biohack es el `health` slot del registry y el ÚNICO dominio cuyo endpoint de salud NO es
`/health`: el registry lo sondea en **`/api/v1/service-health`**
(`ServiceRegistry.HEALTH_ENDPOINTS["health"]`). Ese endpoint es un contrato de DOS lados
que nada verificaba junto:

  - Micelia PROBE-ea `{health_service_url}/api/v1/service-health`.
  - biohack debe SERVIR exactamente esa ruta.

Si cualquiera de los dos deriva (biohack renombra/mueve el endpoint, o Micelia cambia
`HEALTH_ENDPOINTS["health"]`), el registry sondearía un 404 → el slot `health` quedaría
**eternamente unhealthy EN SILENCIO** (el mismo modo de fallo que DP-14 destapó con
`testlab`). Este test lo pinea leyendo el código REAL de biohack (read-only, como el pin
de canela DP-8), sin arrancarlo.

CONTEXTO C91 — por qué se pinea en vez de arrancar: la tarea del ciclo era el arranque
LIVE de biohack (3er dominio tras cybertools/canela). Está **BLOQUEADO** (DP-17): su
`requirements.txt` fija `numpy==1.25.2` (+ scipy/scikit-learn/pandas de 2023) que **no
tienen wheel para python 3.14** (la única versión del sistema; brew desinstaló 3.13, ver
C87). Editar los pins de biohack es tocar código del hermano (fuera de scope). Así que se
extrae el valor verificable SIN arrancar: el contrato del endpoint, leído del código.

Contraste con canela (DP-8): canela OMITE `version` en su `/health`; biohack SÍ lo emite
(`version: "0.1.0"`) en `/api/v1/service-health`. Ambos son healthy en el registry; solo
difiere si el panel muestra versión.

Solo lectura del código de biohack + import de símbolos de Micelia (sin DB). Test-only.
"""

import re
from pathlib import Path

import pytest

_PROJECTS = Path(__file__).resolve().parents[2]
_BIOHACK_MAIN = _PROJECTS / "biohack-app" / "backend" / "main.py"

# La ruta que el registry de Micelia sondea para el slot `health`. Fuente de verdad:
# ServiceRegistry.HEALTH_ENDPOINTS["health"]. Se referencia literal aquí y se cruza con
# el símbolo real en test_micelia_probes_biohack_service_health_path (anti-drift interno).
_PROBED_PATH = "/api/v1/service-health"


def _service_health_region() -> str | None:
    """Texto del handler `@app.get("/api/v1/service-health")` de biohack: desde su
    decorador hasta el siguiente `@app.` o EOF. None si el fichero no está o no parsea."""
    if not _BIOHACK_MAIN.is_file():
        return None
    text = _BIOHACK_MAIN.read_text(encoding="utf-8")
    m = re.search(
        r'@app\.get\("/api/v1/service-health"\)(.*?)(?:\n@app\.|\Z)', text, re.DOTALL
    )
    return m.group(1) if m else None


def _top_level_return_keys(region: str) -> set[str]:
    """Claves del `return {…}` de nivel SUPERIOR del handler.

    El return de biohack tiene un dict anidado (`dependencies: {...}`), así que no vale el
    parse ingenuo `[^}]*`. Se recorta el dict del return balanceando llaves y se toman solo
    las claves cuya `"clave":` aparece en profundidad 1 (fuera de cualquier sub-dict)."""
    start = re.search(r"return\s*\{", region)
    if not start:
        return set()
    i = start.end()  # justo tras la llave de apertura del dict del return
    depth = 1
    keys: set[str] = set()
    body_start = i
    while i < len(region) and depth > 0:
        c = region[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    body = region[body_start : i - 1]
    # Claves en profundidad 1: rastrea el anidamiento y solo registra `"x":` cuando depth==0
    # relativo al body.
    d = 0
    for m in re.finditer(r'\{|\}|"([a-z_]+)"\s*:', body):
        tok = m.group(0)
        if tok == "{":
            d += 1
        elif tok == "}":
            d -= 1
        elif d == 0:
            keys.add(m.group(1))
    return keys


# --------------------------------------------------------------------------- #
# Lado MICELIA (siempre ejecutable): la ruta que sondea el slot `health`.
# --------------------------------------------------------------------------- #
def test_micelia_probes_biohack_service_health_path():
    """El registry sondea el slot `health` en `/api/v1/service-health` (no en `/health`).

    Pin del lado Micelia del contrato: si alguien cambia `HEALTH_ENDPOINTS["health"]`, este
    test lo caza y obliga a re-verificar que biohack sirve la nueva ruta."""
    from app.services.service_registry import ServiceRegistry

    assert ServiceRegistry.HEALTH_ENDPOINTS["health"] == _PROBED_PATH, (
        "el registry ya no sondea el slot health en '/api/v1/service-health'. Si biohack "
        "cambió su endpoint, actualiza _PROBED_PATH y verifica el otro lado; si no, es una "
        "regresión que dejaría health unhealthy."
    )


def test_micelia_service_status_accepts_biohack_version():
    """`ServiceStatus.version` (str|None) acepta el `version: "0.1.0"` que biohack emite —
    biohack es el contraste de canela (DP-8): aquí SÍ hay version que consumir."""
    from app.api.v1.health import ServiceStatus

    s = ServiceStatus(
        name="health",
        url="http://localhost:8080",
        enabled=True,
        healthy=True,
        version="0.1.0",
    )
    assert s.version == "0.1.0"


# --------------------------------------------------------------------------- #
# Lado BIOHACK (cross-repo, SKIP si ausente): sirve la ruta sondeada + emite version.
# --------------------------------------------------------------------------- #
def test_biohack_serves_the_exact_path_micelia_probes():
    """
    El contrato que nada verificaba: biohack SIRVE `/api/v1/service-health`, la ruta que
    Micelia sondea. Si biohack la renombra/mueve, el registry sondea un 404 y el slot
    `health` queda unhealthy para siempre, en silencio (modo de fallo de DP-14).
    """
    if not _BIOHACK_MAIN.is_file():
        pytest.skip(
            "biohack-app/backend/main.py no presente; check cross-repo omitido "
            "(esperado en checkout aislado de Micelia)."
        )
    text = _BIOHACK_MAIN.read_text(encoding="utf-8")
    served = set(re.findall(r'@app\.get\("([^"]+)"\)', text))
    assert _PROBED_PATH in served, (
        f"biohack ya NO sirve '{_PROBED_PATH}' (rutas @app.get halladas: {sorted(served)}). "
        f"El registry lo sondea ahí → health quedaría unhealthy en silencio. Re-alinea el "
        f"endpoint o HEALTH_ENDPOINTS['health']."
    )


def test_biohack_service_health_emits_version_and_identity():
    """
    A diferencia de canela (DP-8, sin version), biohack SÍ emite `version` + `service` en su
    `/api/v1/service-health` → el registry obtiene versión para el slot health. Pin del
    shape para que un refactor no lo rompa en silencio.
    """
    region = _service_health_region()
    if region is None:
        pytest.skip(
            "biohack-app/backend/main.py no presente o el handler service-health no "
            "parseable; check cross-repo omitido."
        )
    keys = _top_level_return_keys(region)
    assert "status" in keys, (
        f"service-health de biohack no expone 'status' (claves: {keys}); ¿cambió el "
        f"handler? Revisa el parser antes de confiar en el pin."
    )
    assert "version" in keys, (
        f"service-health de biohack ya NO emite 'version' a nivel superior (claves: {keys}). "
        f"Si es intencional pasa a la política de canela (DP-8) y actualiza este test; si no, "
        f"es una regresión: el panel perdería la versión del slot health."
    )
    assert "service" in keys, (
        f"service-health de biohack ya no emite 'service' (claves: {keys})."
    )
