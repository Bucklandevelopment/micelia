"""
Tripwire de coherencia del BUILD del frontend (dashboard) con el design-system.

Contexto (Ciclo 73, follow-up): al construir la imagen del dashboard por primera vez
con `podman build`, el build FALLA con:

    Failed to compile.
    ./src/app/globals.css
    Error: Cannot find module '../../design-system/tailwind.preset.cjs'

Causa raíz: desde el retheme del design-system (2026-06-20), el frontend depende del
design-system COMPARTIDO en `projects/design-system/` en BUILD-TIME por dos vías —
`frontend/tailwind.config.js` (`require('../../design-system/tailwind.preset.cjs')`)
y `frontend/src/app/globals.css` (`@import "../../../../design-system/tokens.css"`).
Ese directorio vive DOS niveles por encima de `micelia/frontend/`, así que un build
con `context: ./frontend` (el que tenía `docker-compose.yml → idm-dashboard`) NO lo
incluye → `next build` no resuelve el preset de Tailwind y revienta.

Fix (opción 2, elegida por el usuario): `idm-dashboard` se construye desde la RAÍZ de
projects (`context: ..`) con `micelia/frontend/Dockerfile.root`, que copia
`design-system` + `micelia/frontend` y mantiene el puerto 9000. Verificado: la imagen
construye OK por esta vía (arm64 nativo).

Este guard —que `make verify` ejecuta— caza la regresión sin necesidad de un build de
contenedor: si alguien vuelve a apuntar el build a un contexto que NO incluye el
design-system (p.ej. `./frontend`), o quita el `COPY design-system` del Dockerfile, o
el Dockerfile deja de existir, el pin rompe. Es un acoplamiento con lector VIVO: la
imagen del dashboard ejecuta este contrato de build.

Solo lee ficheros del repo (config del frontend + compose + Dockerfile, cero
secretos). Test-only; no toca `app/`, infra ni repos hermanos.
"""

import re
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parent.parent          # .../micelia
_PROJECTS_ROOT = _REPO.parent                            # .../projects
_TAILWIND = _REPO / "frontend" / "tailwind.config.js"
_GLOBALS = _REPO / "frontend" / "src" / "app" / "globals.css"
_COMPOSE = _REPO / "docker-compose.yml"
_DASHBOARD_SERVICE = "idm-dashboard"


def _design_system_dep_from_tailwind() -> Path:
    """
    Resuelve la ruta ABSOLUTA del design-system del que depende tailwind.config.js.

    `require('../../design-system/...')` es relativo al fichero (micelia/frontend/),
    así que se resuelve contra ese directorio.
    """
    text = _TAILWIND.read_text(encoding="utf-8")
    m = re.search(r"""require\(\s*['"]([^'"]*design-system[^'"]*)['"]\s*\)""", text)
    assert m, (
        "no se encontró un `require('...design-system...')` en tailwind.config.js; "
        "¿desapareció la dependencia del design-system compartido?"
    )
    return (_TAILWIND.parent / m.group(1)).resolve()


def _dashboard_build() -> dict[str, Path]:
    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    build = data["services"][_DASHBOARD_SERVICE]["build"]
    # Contexto y dockerfile son relativos al directorio del compose (micelia/).
    context = (_COMPOSE.parent / build["context"]).resolve()
    dockerfile = (context / build["dockerfile"]).resolve()
    return {"context": context, "dockerfile": dockerfile}


def test_deploy_frontend_files_exist():
    for p in (_TAILWIND, _GLOBALS, _COMPOSE):
        assert p.is_file(), f"falta un fichero del contrato de build del frontend: {p}"


def test_frontend_really_depends_on_shared_design_system():
    """
    Anti-vacío: si el frontend dejara de importar el design-system compartido, todo
    este guard sería moot. Fija que la dependencia build-time SIGUE existiendo por sus
    dos vías (tailwind preset + @import de tokens en globals.css).
    """
    dep = _design_system_dep_from_tailwind()
    assert dep.is_file(), (
        f"tailwind.config.js requiere '{dep}' pero no existe; ¿se movió el "
        f"design-system compartido?"
    )
    assert dep.is_relative_to(_PROJECTS_ROOT / "design-system"), (
        f"la dependencia de tailwind ({dep}) debería vivir bajo "
        f"{_PROJECTS_ROOT / 'design-system'}"
    )
    globals_text = _GLOBALS.read_text(encoding="utf-8")
    assert "design-system" in globals_text, (
        "globals.css ya no importa el design-system; revisa si este guard sigue "
        "teniendo sentido."
    )


def test_dashboard_build_context_includes_design_system():
    """
    El contexto de build de `idm-dashboard` DEBE contener el design-system del que
    depende el frontend en build-time. `./frontend` no lo hace; la raíz de projects sí.

    Mutación: vuelve a poner `context: ./frontend` en docker-compose.yml → este test
    falla. El build real daría "Cannot find module '../../design-system/...'".
    """
    dep = _design_system_dep_from_tailwind()
    build = _dashboard_build()
    context = build["context"]
    assert dep.is_relative_to(context), (
        f"DRIFT de contexto de build: el design-system que el frontend necesita "
        f"({dep}) NO está dentro del contexto de build de '{_DASHBOARD_SERVICE}' "
        f"({context}). `next build` fallaría con 'Cannot find module "
        f"..design-system..'. Usa `context: ..` (raíz de projects) en "
        f"docker-compose.yml, como en micelia/frontend/Dockerfile.root."
    )


def test_dashboard_dockerfile_copies_design_system():
    """
    Tener el design-system en el contexto no basta: el Dockerfile debe COPIARLO al
    build stage para que los imports `../../design-system` resuelvan.

    Mutación: quita `COPY design-system` de Dockerfile.root → falla. El build tendría
    el design-system en el contexto pero no en la imagen, y `next build` reventaría.
    """
    build = _dashboard_build()
    dockerfile = build["dockerfile"]
    assert dockerfile.is_file(), (
        f"el Dockerfile de '{_DASHBOARD_SERVICE}' no existe: {dockerfile}"
    )
    text = dockerfile.read_text(encoding="utf-8")
    assert re.search(r"^\s*COPY\s+design-system\b", text, re.MULTILINE), (
        f"{dockerfile.name} no copia `design-system` al build; los imports "
        f"`../../design-system` del frontend no resolverían. Añade "
        f"`COPY design-system ./design-system` antes del `npm run build`."
    )


def test_dashboard_exposes_expected_port():
    """
    La opción 2 (fix in-place) mantiene el puerto 9000: el Dockerfile debe EXPONER y
    servir 9000, coherente con el mapeo de puertos y el healthcheck del compose.
    """
    build = _dashboard_build()
    text = build["dockerfile"].read_text(encoding="utf-8")
    assert re.search(r"^\s*EXPOSE\s+9000\b", text, re.MULTILINE), (
        f"{build['dockerfile'].name} debería EXPONER 9000 (opción 2 mantiene el puerto "
        f"del dashboard); revisa la coherencia con los ports/healthcheck del compose."
    )

    data = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    svc = data["services"][_DASHBOARD_SERVICE]
    _, container = svc["ports"][0].split(":")
    assert container == "9000", (
        f"el puerto de contenedor de '{_DASHBOARD_SERVICE}' en compose es {container}, "
        f"pero el Dockerfile sirve 9000; actualízalos en lockstep."
    )
