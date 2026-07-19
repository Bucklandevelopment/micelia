"""
C87 — `run-ecosystem.sh` debe cazar un `.venv` HUÉRFANO, no solo uno ausente.

Hallazgo al ejercer el sistema real (C87, arrancando canela): el launcher promete en su
docstring *"detecta las deps ausentes y reporta el comando de instalación en vez de
fallar en silencio"*. Pero su check de marker era `[ -e "$workdir/.venv" ]` — solo mira
que el DIRECTORIO exista. Un `.venv` puede existir y estar **muerto**: cuando Homebrew
actualiza python (canela tenía un venv de python3.13; el sistema pasó a 3.14 y
`python@3.13` se desinstaló), el intérprete al que apunta el venv desaparece y
`.venv/bin/uvicorn` muere con `bad interpreter: .../python3.13: no such file or
directory`. El launcher, creyendo las deps presentes, intentaba arrancar y el usuario
solo veía `no abrió :3690 en 40s; revisa <log>` — la promesa incumplida.

Fix (C87): `start_svc` verifica que el intérprete del venv EJECUTA (`.venv/bin/python -c
''`), no solo que el dir existe; si no, reporta la recreación como "dep ausente".

Estos tests ejercen `start_svc` de VERDAD (sourcean el script — posible desde C87, que
guarda el dispatch con `[ "${BASH_SOURCE[0]}" = "$0" ]`) contra venvs de mentira en
`tmp_path`, sin arrancar ningún servicio real (las 3 ramas verificadas RETORNAN antes de
lanzar nada).
"""

import socket
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LAUNCHER = _REPO / "scripts" / "run-ecosystem.sh"


def _free_port() -> int:
    """Puerto libre: el check `port_in_use` de start_svc va ANTES del check de venv,
    así que el workdir de prueba necesita un puerto que no esté escuchando."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_start_svc(
    workdir: Path, marker: str, *, cmd="echo SHOULD_NOT_RUN", timeout=30
) -> str:
    """
    Sourcea el launcher y llama `start_svc` una vez; devuelve su stdout+stderr.

    Las 3 ramas de gate (marker ausente / venv huérfano / ok) que estos tests ejercen
    RETORNAN antes de arrancar. El único camino que NO retorna rápido es el de un venv
    sano que pasa el gate: ahí start_svc entra en `wait_port <port> 40`, que este test
    no quiere esperar. Por eso toleramos el timeout y devolvemos la salida PARCIAL —
    para entonces la línea "arrancando en :port" (pre-wait_port) ya se emitió.
    """
    port = _free_port()
    # RUN_DIR se fija DENTRO del workdir temporal para que el camino de arranque no
    # escriba logs/pids en el repo (logs/ecosystem/). pytest limpia tmp_path.
    script = (
        f'source "{_LAUNCHER}"; '
        f'RUN_DIR="{workdir}/.runtmp"; mkdir -p "$RUN_DIR"; '
        f"start_svc fake 'Fake Svc' '{workdir}' {port} '{marker}' '{cmd}' 'make setup'"
    )
    try:
        proc = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=timeout
        )
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or b""
        err = exc.stderr or b""
        return (out + err).decode(errors="replace")


def test_orphaned_venv_reports_recreate_hint_not_a_start(tmp_path):
    """
    `.venv` existe pero su python es un symlink roto (intérprete desaparecido) →
    start_svc reporta la recreación y NO intenta arrancar. Es EL caso de canela en C87.
    """
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to("/nonexistent/python3.13")  # huérfano, como canela

    out = _run_start_svc(tmp_path, ".venv")

    assert "intérprete no arranca" in out, out
    assert "make setup" in out  # el hint de recreación
    assert "arrancando" not in out, "no debe intentar arrancar con un venv muerto"
    assert "SHOULD_NOT_RUN" not in out


def test_missing_venv_reports_install_hint(tmp_path):
    """Sin `.venv` (ni siquiera el dir) → la rama clásica de 'faltan dependencias'."""
    out = _run_start_svc(tmp_path, ".venv")

    assert "faltan dependencias" in out, out
    assert "make setup" in out
    assert "arrancando" not in out


def test_working_venv_passes_the_marker_gate(tmp_path):
    """
    Control: un `.venv` con un python que SÍ ejecuta pasa el gate y llega a la fase de
    arranque (el guard nuevo no es un falso positivo). Se apunta el python del venv al
    del sistema y se usa un `cmd` inocuo; no se asserta el arranque real (dependería de
    abrir el puerto), solo que superó los gates de marker.
    """
    import sys

    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)

    # Un venv sano PASA el gate y entra en `wait_port 40`; no esperamos esos 40s —
    # timeout corto + salida parcial: la línea "arrancando" (pre-wait_port) basta.
    out = _run_start_svc(tmp_path, ".venv", cmd="true", timeout=6)

    assert "intérprete no arranca" not in out
    assert "faltan dependencias" not in out
    assert "arrancando" in out, out


def test_dispatch_is_guarded_so_sourcing_has_no_side_effects():
    """
    Sourcear el script NO debe disparar `do_start` (que arrancaría el ecosistema entero
    por el default `start`). El guard `[ "${BASH_SOURCE[0]}" = "$0" ]` (C87) lo impide;
    sin él, estos mismos tests habrían intentado levantar Micelia + dominios.
    """
    proc = subprocess.run(
        ["bash", "-c", f'source "{_LAUNCHER}"; echo SOURCED_OK'],
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined = proc.stdout + proc.stderr
    assert "SOURCED_OK" in combined
    # marcadores inequívocos de que do_start/do_status corrieron:
    assert "== Infra" not in combined
    assert "== Micelia gateway ==" not in combined
    assert "Hub de servicios" not in combined
