"""
Tripwire de coherencia entre el LAUNCHER nativo del ecosistema y el HUB del panel.

Contexto (Ciclo 71→72): una misma pasada del día creó dos artefactos acoplados por
un mapa de puertos que vive DUPLICADO y sin ningún guard:

  * `scripts/run-ecosystem.sh` — bindea cada frontend de dominio en un puerto fijo
    (tabla `SERVICES`, columna 4): biohack-fe:5173, canela:8501, ideacursi:6060,
    codking-vis:3009, automation:8891.
  * `frontend/src/lib/services.ts` — la página `/servicios` (hub) enlaza cada tarjeta
    a `NEXT_PUBLIC_*_URL || 'http://localhost:<puerto>'`, con el MISMO puerto por
    default para que el botón "Abrir…" caiga sobre el servicio que el launcher levantó.

Hoy los dos mapas coinciden, pero NADA lo verifica: cambiar un puerto en un solo
fichero (p.ej. `codking-vis` 3009→3010 en el launcher, sin tocar `services.ts`)
dejaría el botón del hub apuntando a un puerto muerto —404 silencioso— sin romper
ni un test ni el `tsc` (la unión de tipos de `registryKey` no cubre el puerto). No
hay runner de frontend (solo lint+tsc), así que este pin en la suite de pytest
—que `make verify` sí ejecuta— es el único lugar donde el drift se caza.

`cybertools` (hub → :8000/docs) queda FUERA del acoplamiento a propósito: no tiene
SPA (`tieneWebUI:false`) y `run-ecosystem.sh` NO lo arranca como frontend; su tarjeta
enlaza a la API docs, no a un dev-server que el launcher bindee. `codking-be` (:8000,
opt-in) tampoco es un frontend del hub. Solo se pinea la correspondencia real
frontend-launcher ↔ tarjeta-hub (5 dominios).
"""

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_LAUNCHER = _REPO / "scripts" / "run-ecosystem.sh"
_SERVICES_TS = _REPO / "frontend" / "src" / "lib" / "services.ts"
_ENV_EXAMPLE = _REPO / "frontend" / ".env.local.example"

# id de tarjeta en services.ts  ->  id de servicio en la tabla SERVICES del launcher.
# Dominios que el launcher arranca Y el hub enlaza (el botón "Abrir…" debe caer
# sobre el puerto que el launcher bindeó).
# C85: `cybertools` entra aquí. No es un frontend (sigue sin SPA; su tarjeta enlaza a
# :8000/docs), pero desde C85 el launcher SÍ bindea ese puerto — sirve el slot
# `security` del registry —, así que la tarjeta y el launcher pasan a estar acoplados
# por el puerto igual que el resto. Antes el acoplamiento no existía y este test
# pineaba la EXCLUSIÓN (ver test_cybertools_launched_for_the_registry_not_the_hub).
_HUB_TO_LAUNCHER = {
    "biohack": "biohack-fe",
    "canela": "canela",
    "ideacursi": "ideacursi",
    "codking": "codking-vis",
    "automation": "automation",
    "cybertools": "cybertools",
}


def _launcher_ports() -> dict[str, int]:
    """id -> puerto, parseado de la tabla `SERVICES` (líneas `id|label|dir|puerto|...`)."""
    text = _LAUNCHER.read_text(encoding="utf-8")
    ports: dict[str, int] = {}
    for m in re.finditer(r"^([a-z0-9-]+)\|[^|\n]*\|[^|\n]*\|(\d+)\|", text, re.MULTILINE):
        ports[m.group(1)] = int(m.group(2))
    return ports


def _hub_default_ports() -> dict[str, int]:
    """id de tarjeta -> puerto del default `http://localhost:<puerto>` en services.ts."""
    text = _SERVICES_TS.read_text(encoding="utf-8")
    ports: dict[str, int] = {}
    for m in re.finditer(
        r"id:\s*'([^']+)'[\s\S]*?localhost:(\d+)", text
    ):
        # finditer no solapa: cada bloque de tarjeta se empareja con SU primer localhost.
        ports.setdefault(m.group(1), int(m.group(2)))
    return ports


def test_launcher_and_hub_files_exist():
    assert _LAUNCHER.is_file(), f"falta el launcher del ecosistema: {_LAUNCHER}"
    assert _SERVICES_TS.is_file(), f"falta el catálogo del hub: {_SERVICES_TS}"


def test_parsers_are_not_vacuously_empty():
    """Si un parser deja de encontrar entradas, el pin de abajo pasaría en vacío."""
    launcher = _launcher_ports()
    hub = _hub_default_ports()
    assert "biohack-fe" in launcher and "automation" in launcher, launcher
    assert "biohack" in hub and "cybertools" in hub, hub


@pytest.mark.parametrize("hub_id,launcher_id", sorted(_HUB_TO_LAUNCHER.items()))
def test_hub_default_port_matches_launcher_bind_port(hub_id: str, launcher_id: str):
    """
    El puerto por default de la tarjeta del hub == puerto que el launcher bindea.

    Mutación: cambia `codking-vis|...|3009` a `3010` en run-ecosystem.sh (sin tocar
    services.ts) y este test falla nombrando ambos ficheros. Actualízalos en lockstep.
    """
    launcher = _launcher_ports()
    hub = _hub_default_ports()
    assert hub_id in hub, f"'{hub_id}' no está en services.ts (¿renombrada la tarjeta?)"
    assert launcher_id in launcher, (
        f"'{launcher_id}' no está en la tabla SERVICES de run-ecosystem.sh "
        f"(¿renombrado el servicio?)"
    )
    assert hub[hub_id] == launcher[launcher_id], (
        f"DRIFT de puerto para '{hub_id}': el hub (frontend/src/lib/services.ts) "
        f"enlaza a :{hub[hub_id]} pero run-ecosystem.sh arranca '{launcher_id}' en "
        f":{launcher[launcher_id]}. El botón del hub caería en un puerto muerto. "
        f"Actualiza ambos ficheros en lockstep."
    )


def _services_ts_default_urls() -> dict[str, str]:
    """NEXT_PUBLIC_*_URL -> URL por default en el `|| '...'` de services.ts."""
    text = _SERVICES_TS.read_text(encoding="utf-8")
    urls: dict[str, str] = {}
    for m in re.finditer(
        r"process\.env\.(NEXT_PUBLIC_\w+)\s*\|\|\s*'([^']+)'", text
    ):
        urls[m.group(1)] = m.group(2)
    return urls


def _env_example_urls() -> dict[str, str]:
    """NEXT_PUBLIC_*_URL -> valor documentado en frontend/.env.local.example."""
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    urls: dict[str, str] = {}
    for m in re.finditer(
        r"^(NEXT_PUBLIC_\w+)=(\S+)$", text, re.MULTILINE
    ):
        urls[m.group(1)] = m.group(2)
    return urls


def test_env_example_documents_the_same_defaults_as_services_ts():
    """
    Tercer vértice del mapa: el default embebido en services.ts (el `|| '...'` que se
    usa cuando la env-var no está definida) debe coincidir con lo que
    frontend/.env.local.example documenta como valor de esa misma var. Un dev que
    copia el .env.local.example espera que refleje los defaults del código; si uno
    cambia y el otro no, el ejemplo miente. Se comparan URLs completas (incluye el
    sufijo `/docs` de cybertools, no solo el puerto).

    Mutación: cambia NEXT_PUBLIC_CODKING_URL en el .env.local.example (sin tocar
    services.ts) y este test falla nombrando ambos ficheros.
    """
    ts = _services_ts_default_urls()
    env = _env_example_urls()
    assert ts, "no se parseó ningún default de services.ts"
    assert env, "no se parseó ninguna var de .env.local.example"
    # Toda var NEXT_PUBLIC_*_URL con default en services.ts debe estar documentada
    # con el MISMO valor en el .env.local.example.
    for var, default_url in sorted(ts.items()):
        assert var in env, (
            f"{var} tiene default en services.ts ('{default_url}') pero no está "
            f"documentada en frontend/.env.local.example. Añádela o el ejemplo queda cojo."
        )
        assert env[var] == default_url, (
            f"DRIFT de default para {var}: services.ts usa '{default_url}' pero "
            f".env.local.example documenta '{env[var]}'. Actualiza ambos en lockstep."
        )


def test_cybertools_launched_for_the_registry_not_the_hub():
    """
    C85 invierte el guard de C72 (que pineaba que el launcher NO arrancaba cybertools).

    Motivo del cambio, y por qué NO contradice el razonamiento de C72: C72 razonaba
    desde el HUB ("no tiene SPA → no es un frontend que el launcher deba arrancar"),
    y eso sigue siendo cierto. Lo que C72 no miraba es el REGISTRY: `security` es uno
    de los 5 slots que Micelia sondea (`security_service_url` = :8000, `/health`), así
    que sin cybertools corriendo el slot queda unhealthy aunque el launcher haya
    levantado todo lo demás. Precedente exacto: `biohack-be` (:8080) lleva en la tabla
    desde siempre por ser backend del slot `health`, no por tener UI.

    El pin exige el `.venv` como marker (no `node_modules`): cybertools es Python y su
    arranque real es `.venv/bin/uvicorn scanet.api:app`.
    """
    launcher = _launcher_ports()
    assert launcher.get("cybertools") == 8000, (
        "run-ecosystem.sh debe bindear cybertools en :8000 (slot `security` del "
        f"registry). Tabla SERVICES parseada: {launcher}"
    )

    text = _LAUNCHER.read_text(encoding="utf-8")
    line = next(
        ln for ln in text.splitlines() if ln.startswith("cybertools|")
    )
    assert ".venv" in line and "scanet.api:app" in line, (
        f"el arranque de cybertools dejó de ser uvicorn sobre su .venv: {line!r}"
    )


def test_cybertools_and_codking_be_are_mutually_exclusive_on_8000():
    """
    DP-12 (C76) declara que cybertools y codking-be comparten :8000 y "no correr ambos
    a la vez". C85 mete cybertools en el launcher, así que esa exclusión pasa de nota
    en el manifest a comportamiento: el launcher elige por el flag (`if/else`), no por
    carrera de `port_in_use`. Este pin muerde si alguien pone los dos en la misma rama.
    """
    text = _LAUNCHER.read_text(encoding="utf-8")
    assert re.search(
        r'if \[ "\$WITH_CODKING_INFERENCE" = "1" \]; then'
        r"[\s\S]*?codking-be\|[\s\S]*?"
        r"^else$"
        r"[\s\S]*?cybertools\|[\s\S]*?^fi$",
        text,
        re.MULTILINE,
    ), (
        "cybertools y codking-be deben seguir en ramas EXCLUYENTES del flag "
        "--with-codking-inference (comparten :8000, DP-12)."
    )
