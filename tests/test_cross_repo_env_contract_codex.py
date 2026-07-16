"""
Guard cross-repo del contrato de ENV que Micelia inyecta a cada dominio (DP-5, C82).

DP-5 (C37) se anotó como "solo drift de nombre" (los hermanos llaman `vital-core` al
orquestador; puerto 8888 correcto). **La auditoría C82 lo desmiente: era un BUG REAL.**

El `docker-compose.yml` de Micelia inyectaba a los 6 contenedores de dominio la URL del
gateway como `IDM_CORE_URL` (+ la key como `IDM_CORE_API_KEY`/`IDM_API_KEY`), pero
**NINGUNO de los 6 lee esos nombres**: los 6 leen `VITAL_CORE_URL` (+ `VITAL_CORE_API_KEY`
o `VITAL_API_KEY`). Como cada SDK tiene default `http://localhost:8888`, el efecto en el
perfil `full` era:

  - `core_url` → `http://localhost:8888`, que DENTRO del contenedor es **el propio
    contenedor**, no el gateway → REST a Micelia rechazado.
  - `api_key`  → `""` → aunque la URL fuese buena, `verify_auth` de Micelia responde 401.

…y con degradación elegante en los 6 → **fallo SILENCIOSO**: los dominios logueaban un
warning y seguían, sin registrarse jamás en el orquestador. Verificado empíricamente en
C82 con la clase de config REAL de canela (`VitalConfig`): inyectando `IDM_CORE_URL` el
`core_url` resuelto era `http://localhost:8888` y `api_key` `""`; inyectando
`VITAL_CORE_URL` resolvía a `http://idm-core:8888` con su key.

FIX (C82, aditivo): el compose ahora inyecta TAMBIÉN los nombres `VITAL_*` que los
dominios sí leen. Los `IDM_*` se conservan como alias — retirarlos (o migrar todo a
`MICELIA_*`) es la decisión de rebrand que DP-5 ESCALA al dueño, no la toma esta rutina.

Este guard es a la vez regresión-test del fix y tripwire de la clase entera: deriva el
contrato del compose (fuente) y del CÓDIGO REAL de cada hermano (lector), y asserta que
lo inyectado ⊇ lo leído. Si un dominio renombra su env-var, o alguien retira los `VITAL_*`
del compose, salta aquí en vez de en un deploy silencioso.

Read-only sobre los hermanos (mismo árbol de proyectos, cero secretos); SKIP por-dominio
si el hermano no está en el checkout (Micelia clonado solo). Test-only.
"""

import re
from pathlib import Path

import pytest
import yaml

_MICELIA = Path(__file__).resolve().parents[1]
_PROJECTS = _MICELIA.parent
_COMPOSE = _MICELIA / "docker-compose.yml"

# Para cada servicio de dominio del compose: el fichero del hermano que LEE la config y
# los nombres de env que ese código exige. Los nombres se VERIFICAN contra el fichero
# (no se asumen): si el patrón deja de aparecer, el test falla pidiendo re-auditar.
_DOMAIN_ENV_CONTRACT = {
    "biohack-app": {
        "reader": "biohack-app/backend/app/core/config.py",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_CORE_API_KEY",
    },
    "canela-molida": {
        # VitalConfig(env_prefix="VITAL_") → core_url/api_key = VITAL_CORE_URL/VITAL_API_KEY
        "reader": "canela-molida/app/integrations/vital_sdk/config.py",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_API_KEY",
        "prefix_class": True,
    },
    "ideacursi-backend": {
        "reader": "ideacursi-tool/backend/src/vital-core/vital-core.service.js",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_CORE_API_KEY",
    },
    "cybertools": {
        "reader": "cybertools/src/scanet/api.py",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_API_KEY",
    },
    "codking": {
        "reader": "codking/integrations/vital_sdk/config.py",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_API_KEY",
        "prefix_class": True,
    },
    "auto-mat-ion": {
        # URL en config/index.ts (zod), key leída directo en api/server.ts
        "reader": "auto-mat-ion/src/config/index.ts",
        "url_var": "VITAL_CORE_URL",
        "key_var": "VITAL_CORE_API_KEY",
        "key_reader": "auto-mat-ion/src/api/server.ts",
    },
}

_GATEWAY_SERVICE = "idm-core"


def _compose_env(service: str) -> dict[str, str]:
    """Env del servicio, normalizando las 2 sintaxis de compose (lista y mapping)."""
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    env = data["services"][service].get("environment", {})
    if isinstance(env, dict):
        return {k: str(v) for k, v in env.items()}
    out = {}
    for item in env:
        k, _, v = str(item).partition("=")
        out[k] = v
    return out


def _reader_text(rel: str) -> str | None:
    p = _PROJECTS / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


@pytest.mark.parametrize("service", sorted(_DOMAIN_ENV_CONTRACT))
def test_compose_injects_the_env_names_the_domain_actually_reads(service):
    """
    El contrato de DP-5: para cada dominio, el compose debe inyectar los nombres de env
    que su código REALMENTE lee (URL + API key), con el host del gateway (no localhost).

    Regresión de C82: antes del fix el compose solo inyectaba `IDM_CORE_URL`/`IDM_*_API_KEY`
    → los 6 dominios caían a su default `http://localhost:8888` (= su propio contenedor)
    y a api_key vacía → nunca se registraban en Micelia, en silencio.
    """
    contract = _DOMAIN_ENV_CONTRACT[service]
    reader = _reader_text(contract["reader"])
    if reader is None:
        pytest.skip(
            f"{contract['reader']} no presente; check cross-repo omitido "
            f"(esperado en checkout aislado de Micelia)."
        )

    # 1) El hermano LEE de verdad estos nombres (si no, el contrato cambió → re-auditar).
    if contract.get("prefix_class"):
        # SDK con pydantic-settings env_prefix="VITAL_": core_url/api_key → VITAL_CORE_URL/VITAL_API_KEY
        assert 'env_prefix="VITAL_"' in reader, (
            f"{service}: su SDK ya no usa env_prefix=\"VITAL_\"; los nombres de env "
            f"cambiaron y este contrato debe re-auditarse."
        )
        assert re.search(r"^\s*core_url\s*:", reader, re.M), (
            f"{service}: su SDK ya no expone `core_url`; re-audita el contrato de env."
        )
    else:
        assert contract["url_var"] in reader, (
            f"{service}: {contract['reader']} ya no lee {contract['url_var']}; "
            f"el contrato de env cambió y el compose debe seguirlo."
        )
        key_src = _reader_text(contract.get("key_reader", contract["reader"])) or ""
        assert contract["key_var"] in key_src, (
            f"{service}: ya no lee {contract['key_var']}; re-audita el contrato de env."
        )

    # 2) El compose INYECTA esos nombres…
    env = _compose_env(service)
    for var in (contract["url_var"], contract["key_var"]):
        assert var in env, (
            f"{service}: el compose NO inyecta {var}, que es lo que su código LEE. "
            f"El dominio caerá a su default (localhost:8888 = su propio contenedor / "
            f"api_key vacía) y NO se registrará en Micelia, en SILENCIO. Este es "
            f"exactamente el bug de DP-5 que C82 arregló — no lo reintroduzcas."
        )

    # 3) …apuntando al servicio gateway del compose, no a localhost.
    url = env[contract["url_var"]]
    assert _GATEWAY_SERVICE in url, (
        f"{service}: {contract['url_var']}={url!r} no apunta al servicio "
        f"'{_GATEWAY_SERVICE}' del compose. En la red de compose, 'localhost' es el "
        f"propio contenedor del dominio → jamás alcanzaría al gateway."
    )
    assert "localhost" not in url, (
        f"{service}: {contract['url_var']}={url!r} apunta a localhost → dentro del "
        f"contenedor eso es el propio dominio, no Micelia."
    )
    assert env[contract["key_var"]], (
        f"{service}: {contract['key_var']} está vacía → verify_auth de Micelia "
        f"responderá 401 a su registro/heartbeat."
    )


def test_gateway_service_name_is_the_one_domains_are_pointed_at():
    """Anti-tautología del pin de arriba: el servicio gateway existe en el compose con
    el nombre al que apuntan las URLs de los dominios."""
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    assert _GATEWAY_SERVICE in data["services"], (
        f"el servicio '{_GATEWAY_SERVICE}' ya no existe en el compose; las "
        f"{len(_DOMAIN_ENV_CONTRACT)} URLs de dominio apuntan a un host inexistente."
    )
