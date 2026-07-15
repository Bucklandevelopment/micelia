"""
Tripwire de coherencia Makefile ↔ docker-compose.yml (nombres de servicio y perfiles).

Contexto (Ciclo 74, vector (b) de C73): al construir las imágenes de deploy de
Micelia (gateway en C73, dashboard en el follow-up de C73) quedó a la vista que el
`Makefile` es un LECTOR VIVO del `docker-compose.yml`: varios targets invocan
`podman-compose` nombrando servicios y perfiles CONCRETOS. Ninguno de esos nombres
está atado por un test al compose, y `make verify` nunca ejecuta `podman-compose`
→ un rename de servicio o de perfil en el compose rompe el target del Makefile EN
SILENCIO. El caso de mayor valor: `make docker-infra` —el comando local-first
documentado para M1 (levanta solo postgres+redis+ollama)— bombea 3 nombres de
servicio; si alguno se renombra en el compose, `podman-compose up -d <svc>` falla
con "no such service" y la infra local del dev nunca arranca, sin que nada lo avise.

Contratos VIVOS que este pin blinda (todos leídos del propio `Makefile`, no
hardcodeados — si el Makefile cambia sus invocaciones, el test se reconfigura solo):

  * `docker-infra`  → `podman-compose up -d postgres redis ollama`
      Los 3 nombres deben existir como servicios Y estar en el perfil DEFAULT (sin
      clave `profiles:`), porque el comando NO pasa `--profile`. Si alguno cayera
      tras un perfil, `docker-infra` lo saltaría en silencio.
  * `docker-logs`   → `logs -f micelia-core || logs -f idm-core`
      Al menos uno de los dos candidatos debe ser un servicio real (si no, el target
      queda muerto). Hoy `idm-core` resuelve y `micelia-core` es aspiracional (el
      rebrand conserva `idm` como alias; ver `test_deploy_contract_codex.py`
      `_GATEWAY_SERVICE`). El que resuelve HOY debe ser exactamente ese `idm-core`,
      para mantener ambos ficheros en lockstep.
  * `docker-full` / `docker-monitoring` / `docker-health` → `--profile <X>`
      Cada perfil nombrado debe estar declarado por al menos un servicio del compose;
      si no, el target arranca el set vacío/default sin avisar.

Complementa a `test_deploy_contract_codex.py` (puerto+ruta de health del gateway
código↔Dockerfile↔compose): aquel ata el CONTENIDO del servicio del gateway; este
ata que los NOMBRES de servicio/perfil que el Makefile bombea existan de verdad.

Solo lee ficheros del propio repo (Makefile + compose, cero secretos). Test-only;
no toca `app/`, infra, `.env` ni repos hermanos.
"""

import re
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parent.parent
_MAKEFILE = _REPO / "Makefile"
_COMPOSE = _REPO / "docker-compose.yml"

# Debe coincidir con `_GATEWAY_SERVICE` de test_deploy_contract_codex.py. El servicio
# del gateway en compose se llama `idm-core` (retrocompat). `docker-logs` intenta
# `micelia-core` primero (aspiracional) y cae a este.
_GATEWAY_SERVICE = "idm-core"


# --------------------------------------------------------------------------- #
# Parsers del Makefile (el LECTOR vivo). Extraen las invocaciones reales de
# podman-compose, no una lista hardcodeada.
# --------------------------------------------------------------------------- #
def _makefile_text() -> str:
    return _MAKEFILE.read_text(encoding="utf-8")


def _infra_services() -> list[str]:
    """
    Servicios que `podman-compose up -d <svc...>` nombra SIN `--profile` (target
    docker-infra). Captura la cola de nombres tras `up -d ` cuando no hay perfil.
    """
    services: list[str] = []
    for line in _makefile_text().splitlines():
        # Solo invocaciones bare `podman-compose up -d <names>` (sin --profile entre
        # medias): las de perfil llevan `--profile X up -d` sin cola de servicios.
        m = re.search(r"podman-compose\s+up\s+-d\s+(.+)$", line)
        if m:
            services.extend(m.group(1).split())
    return services


def _logs_candidates() -> list[str]:
    """Servicios que los `podman-compose logs -f <svc>` del Makefile nombran."""
    return re.findall(r"podman-compose\s+logs\s+-f\s+(\S+)", _makefile_text())


def _referenced_profiles() -> list[str]:
    """Perfiles que los targets `--profile <X>` del Makefile invocan."""
    return re.findall(r"podman-compose\s+--profile\s+(\S+)\s+up", _makefile_text())


# --------------------------------------------------------------------------- #
# Parsers del compose (la fuente de verdad).
# --------------------------------------------------------------------------- #
def _compose() -> dict:
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))


def _service_names() -> set[str]:
    return set(_compose()["services"].keys())


def _default_profile_services() -> set[str]:
    """Servicios sin clave `profiles:` → arrancan en el perfil default."""
    services = _compose()["services"]
    return {name for name, spec in services.items() if not spec.get("profiles")}


def _declared_profiles() -> set[str]:
    profiles: set[str] = set()
    for spec in _compose()["services"].values():
        profiles.update(spec.get("profiles") or [])
    return profiles


# --------------------------------------------------------------------------- #
# Guards anti-vacío: si un parser deja de encontrar su patrón, el pin pasaría en
# vacío. Fijamos lo conocido hoy para que un parser roto se note.
# --------------------------------------------------------------------------- #
def test_artifacts_exist():
    assert _MAKEFILE.is_file(), "falta el Makefile"
    assert _COMPOSE.is_file(), "falta docker-compose.yml"


def test_parsers_are_not_vacuously_empty():
    assert set(_infra_services()) == {"postgres", "redis", "ollama"}, (
        "el parser de docker-infra no encontró los 3 servicios esperados; "
        f"halló {_infra_services()!r}"
    )
    assert set(_logs_candidates()) == {"micelia-core", "idm-core"}, (
        f"el parser de docker-logs no halló los 2 candidatos; {_logs_candidates()!r}"
    )
    assert set(_referenced_profiles()) == {"full", "monitoring", "health"}, (
        f"el parser de perfiles del Makefile no halló los 3; {_referenced_profiles()!r}"
    )
    # El compose tiene al menos los servicios de infra y el gateway.
    assert {"postgres", "redis", "ollama", _GATEWAY_SERVICE} <= _service_names()


# --------------------------------------------------------------------------- #
# Los pins reales.
# --------------------------------------------------------------------------- #
def test_docker_infra_services_exist_in_default_profile():
    """
    Cada servicio que `make docker-infra` bombea (`up -d postgres redis ollama`) debe
    existir en el compose Y estar en el perfil DEFAULT (sin `profiles:`), porque el
    comando no pasa `--profile`.

    Mutación: renombrar `postgres:`→`db:` en el compose (o añadirle
    `profiles: [full]`) → este test falla. En real, `podman-compose up -d postgres`
    daría "no such service" / lo saltaría, y la infra local del dev nunca arrancaría.
    """
    services = _service_names()
    default = _default_profile_services()
    for svc in _infra_services():
        assert svc in services, (
            f"`make docker-infra` bombea el servicio '{svc}' pero NO existe en "
            f"docker-compose.yml (servicios: {sorted(services)}). `podman-compose up "
            f"-d {svc}` daría 'no such service' y la infra local no arrancaría. "
            f"Actualiza el Makefile y el compose en lockstep."
        )
        assert svc in default, (
            f"`make docker-infra` bombea '{svc}' sin `--profile`, pero en el compose "
            f"ese servicio está tras un perfil ({_compose()['services'][svc].get('profiles')}). "
            f"`docker-infra` lo saltaría en silencio. Quita el perfil o cambia el target."
        )


def test_docker_logs_resolves_to_the_gateway_service():
    """
    `make docker-logs` intenta `micelia-core` y cae a `idm-core`. Al menos uno debe ser
    un servicio real (si no, el target queda muerto); y el que resuelve HOY debe ser
    exactamente `_GATEWAY_SERVICE` (== el de test_deploy_contract_codex.py).

    Mutación: renombrar el servicio `idm-core:`→`micelia-gateway:` en el compose sin
    tocar el Makefile → ambos candidatos (`micelia-core`, `idm-core`) quedan muertos y
    este test falla. En real, `make docker-logs` no encontraría ningún servicio.
    """
    services = _service_names()
    candidates = _logs_candidates()
    resolving = [c for c in candidates if c in services]
    assert resolving, (
        f"`make docker-logs` nombra {candidates} pero NINGUNO existe como servicio en "
        f"el compose ({sorted(services)}). El target quedaría muerto. Actualiza el "
        f"fallback de docker-logs cuando renombres el servicio del gateway."
    )
    assert resolving == [_GATEWAY_SERVICE], (
        f"`make docker-logs` resuelve a {resolving}, pero se esperaba exactamente "
        f"['{_GATEWAY_SERVICE}'] (el servicio del gateway, en lockstep con "
        f"test_deploy_contract_codex.py). Si renombraste el gateway, actualiza ambos "
        f"ficheros y esta constante."
    )


def test_makefile_profiles_are_declared_in_compose():
    """
    Cada `--profile <X>` que un target del Makefile invoca (full, monitoring, health)
    debe estar declarado por al menos un servicio del compose.

    Mutación: quitar `"health"` de `profiles: ["full", "health"]` del servicio
    biohack-app → `make docker-health` dejaría de levantar el dominio salud y este
    test falla nombrando el perfil huérfano.
    """
    declared = _declared_profiles()
    for prof in _referenced_profiles():
        assert prof in declared, (
            f"`make` invoca `--profile {prof}` pero NINGÚN servicio del compose declara "
            f"ese perfil (declarados: {sorted(declared)}). El target arrancaría el set "
            f"default/vacío en silencio. Alinea el Makefile con el compose."
        )
