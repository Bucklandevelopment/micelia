"""
Tripwire cross-repo del NAMESPACE de canal del Event Bus Redis (DP-7, cerrada Ciclo 80).

DP-7 (C41): conviven TRES eras de prefijo de canal y nadie las ha unificado:

  * `idm.*`     — Micelia, el orquestador (`app/sdk/models.py` EVENT_CHANNELS,
                  `app/services/event_bus.py` CHANNELS). Herencia del Panel IDM.
  * `vital.*`   — los 5 SDK de dominio (biohack, canela, cybertools, codking,
                  auto-mat-ion). Herencia de vital-core.
  * `micelia.*` — destino del rebrand. NO lo usa NADIE.

Un publisher en `vital.security` y un subscriber en `idm.security` están en canales
Redis DISTINTOS → una entrega pub/sub cruzada fallaría EN SILENCIO.

SEVERIDAD HOY = LATENTE (verificado C80, no asumido): ningún llamador de producción de
`app/` se suscribe a un canal de DOMINIO — los únicos `subscribe()` son los métodos
genéricos de la librería (`event_bus.py:112`, `sdk/client.py:374`). Micelia publica
`idm.prompts` (interno: prompt_agent/prompt_executor) y sus helpers `CHANNELS[...]`,
que ningún dominio consume. El flujo REAL dominio→Micelia va por REST
(`POST /api/v1/events`), donde los source-id SÍ coinciden. **Nada está roto hoy.**

DECISIÓN (DP-7, cerrada C80 — tomada por el usuario, no unilateralmente): **documentar
y guardar, NO migrar.** Migrar exigiría renombrar canales en runtime de 6 repos (~80
refs, incluidos sus tests que fijan `vital.*`) y 3 hermanos tienen WIP activo
(cybertools 70 ficheros, canela 27, biohack 2) → el guardarraíl "no tocar WIP de otros
repos" + "decisión irreversible → no la tomes" lo prohíben. Como NADIE consume pub/sub
cruzado, migrar hoy sería fabricar trabajo. La elección real (alinear a `vital.*`,
migrar los 6 a `micelia.*`, o capa de compat) queda para cuando exista un consumidor
VIVO que la justifique.

Este test convierte esa decisión en contrato ejecutable: pinea las 3 eras tal como
están, para que el drift quede TESTeado y avise si alguien cambia un prefijo o si las
eras convergen (→ DP-7 puede avanzar). SKIP por-hermano si no está en el checkout.

Solo lectura del código de los hermanos (cero secretos, cero escritura). Test-only.
"""

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_PROJECTS = _REPO.parent

# Fichero que define el mapa de canales en el SDK de cada dominio. Formatos
# heterogéneos a propósito (dict, Enum, template-literal TS): el parser extrae el
# PREFIJO de los literales de string, así que es agnóstico al formato.
_DOMAIN_SDK_CHANNEL_FILES = {
    "biohack": "biohack-app/backend/app/integrations/vital_sdk/models.py",
    "canela": "canela-molida/app/integrations/vital_sdk/events.py",
    "cybertools": "cybertools/src/scanet/vital_sdk/models.py",
    "codking": "codking/integrations/vital_sdk/events.py",
    "auto-mat-ion": "auto-mat-ion/src/integrations/vital-core.ts",
}

_PREFIX_RE = re.compile(r"""["'`](vital|idm|micelia)\.""")


def _prefixes_in(path: Path) -> set[str]:
    """Prefijos de canal que aparecen en literales de string del fichero."""
    return set(_PREFIX_RE.findall(path.read_text(encoding="utf-8")))


def _micelia_channel_values() -> dict[str, str]:
    from app.sdk.models import EVENT_CHANNELS

    return dict(EVENT_CHANNELS)


# --------------------------------------------------------------------------- #
# Lado MICELIA (siempre ejecutable): la era `idm.*`.
# --------------------------------------------------------------------------- #
def test_micelia_channels_use_idm_prefix():
    """
    Los 7 canales públicos de Micelia usan el prefijo `idm.` (era del orquestador).

    Mutación: cambiar EVENT_CHANNELS a `micelia.*` o `vital.*` rompe este pin → señal de
    que DP-7 se está resolviendo; actualiza el test y revisa el otro extremo (los 5 SDK)
    antes de dar por buena la migración.
    """
    channels = _micelia_channel_values()
    assert channels, "EVENT_CHANNELS está vacío: ¿se movió el mapa de canales?"
    prefixes = {v.split(".", 1)[0] for v in channels.values()}
    assert prefixes == {"idm"}, (
        f"El namespace de Micelia cambió: prefijos {sorted(prefixes)} en EVENT_CHANNELS "
        f"(esperado solo 'idm'). Si es una migración intencionada de DP-7, alinéala con "
        f"los 5 SDK de dominio y actualiza este pin en lockstep."
    )


# --------------------------------------------------------------------------- #
# Lado DOMINIOS (cross-repo, SKIP si ausente): la era `vital.*`.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("domain", sorted(_DOMAIN_SDK_CHANNEL_FILES))
def test_domain_sdk_uses_vital_prefix(domain: str):
    """
    Cada SDK de dominio define sus canales bajo `vital.*` (era vital-core).

    Mutación: si un dominio migra a `micelia.*`/`idm.*`, este pin falla → DP-7 avanza y
    Micelia debe decidir si converge (hoy quedaría a medias, con parte del ecosistema
    en un prefijo y parte en otro).
    """
    path = _PROJECTS / _DOMAIN_SDK_CHANNEL_FILES[domain]
    if not path.is_file():
        pytest.skip(
            f"SDK de '{domain}' no presente en el checkout ({path}); "
            f"check cross-repo omitido (esperado en checkout aislado de Micelia)."
        )
    prefixes = _prefixes_in(path)
    assert prefixes, (
        f"no se halló ningún literal de canal en {path}; ¿cambió el formato del SDK? "
        f"Revisa el parser antes de confiar en el pin."
    )
    assert prefixes == {"vital"}, (
        f"El SDK de '{domain}' ya no usa solo `vital.*`: prefijos {sorted(prefixes)} en "
        f"{path}. Si es la migración de DP-7, coordina los 6 repos y actualiza este pin."
    )


# --------------------------------------------------------------------------- #
# El pin del DRIFT en sí: las eras siguen SIN converger → pub/sub cruzado NO funciona.
# --------------------------------------------------------------------------- #
def test_namespace_drift_between_micelia_and_domains_is_unresolved():
    """
    Pin del estado documentado de DP-7: Micelia (`idm.*`) y los dominios (`vital.*`)
    NO comparten prefijo, así que el pub/sub cruzado NO entrega. Nadie depende de él hoy
    (el flujo real es REST `POST /api/v1/events`), por eso se documenta en vez de migrar.

    Si este test falla porque las eras CONVERGIERON, es una buena noticia: DP-7 se
    resolvió → habilita el pub/sub cruzado conscientemente y borra este pin. No lo
    "arregles" alineando un solo lado a ciegas: romperías la entrega en silencio.
    """
    micelia_prefixes = {v.split(".", 1)[0] for v in _micelia_channel_values().values()}
    domain_prefixes: set[str] = set()
    for rel in _DOMAIN_SDK_CHANNEL_FILES.values():
        path = _PROJECTS / rel
        if path.is_file():
            domain_prefixes |= _prefixes_in(path)
    if not domain_prefixes:
        pytest.skip("ningún SDK de dominio presente; drift cross-repo no verificable.")

    assert micelia_prefixes.isdisjoint(domain_prefixes), (
        f"Las eras de namespace CONVERGIERON: Micelia usa {sorted(micelia_prefixes)} y "
        f"los dominios {sorted(domain_prefixes)}. DP-7 puede cerrarse de verdad: decide "
        f"el prefijo canónico, habilita el pub/sub cruzado y elimina este pin."
    )
