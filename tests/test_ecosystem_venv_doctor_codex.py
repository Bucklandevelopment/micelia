"""
C97 — `run-ecosystem.sh doctor`: diagnóstico temprano de la salud de los venvs del ecosistema.

DP-16 (venvs huérfanos cuando brew sube de python, C87) y DP-17 (biohack sin venv arrancable
en 3.14, C91) se descubrían solo AL intentar arrancar un servicio y ver el fallo. El
subcomando `doctor` (C97) los reporta de una vez, sin arrancar ni instalar nada: por cada
servicio python del ecosistema dice si su `.venv` está AUSENTE, HUÉRFANO (intérprete roto) u
OK (con la versión de python). Reusa el mismo predicado `venv_python_ok` que `start_svc` usa
para no arrancar un venv muerto (fuente única del check de C87).

Estos tests ejercen `check_venv` y `do_doctor` de VERDAD (sourceando el script — posible
desde C87) contra venvs de mentira en `tmp_path`, y contra un `SERVICES` inyectado, para no
depender del estado real de los venvs de la máquina (esa dependencia sería justo la
no-hermeticidad que C89 barrió). El `doctor` sobre el ecosistema REAL no se asserta aquí
(su salida depende de qué venvs existan) — solo su lógica, con entradas controladas.
"""

import subprocess
import sys
from pathlib import Path

_LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "run-ecosystem.sh"


def _bash(snippet: str) -> subprocess.CompletedProcess:
    """Sourcea el launcher (sin disparar el dispatch, guard de C87) y corre `snippet`."""
    return subprocess.run(
        ["bash", "-c", f'source "{_LAUNCHER}"\n{snippet}'],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _make_venv(dir_: Path, *, python_target: str | None) -> None:
    """Crea `dir_/.venv/bin/python` como symlink a `python_target` (None = no crear .venv)."""
    if python_target is None:
        dir_.mkdir(parents=True, exist_ok=True)
        return
    bin_ = dir_ / ".venv" / "bin"
    bin_.mkdir(parents=True)
    (bin_ / "python").symlink_to(python_target)


# =============================================================================
# check_venv — el diagnóstico de UN venv
# =============================================================================


def test_check_venv_healthy_reports_ok_with_version(tmp_path):
    _make_venv(tmp_path, python_target=sys.executable)  # intérprete que SÍ ejecuta
    r = _bash(f"check_venv 'Svc' '{tmp_path}' 'make setup'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "OK (python" in out, out
    assert "rc=0" in out, f"check_venv sano debe devolver 0: {out}"


def test_check_venv_absent_reports_ausente(tmp_path):
    _make_venv(tmp_path, python_target=None)  # dir existe, sin .venv
    r = _bash(f"check_venv 'Svc' '{tmp_path}' 'make setup'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "AUSENTE" in out, out
    assert "make setup" in out  # imprime la pista de creación
    assert "rc=1" in out


def test_check_venv_orphaned_reports_huerfano(tmp_path):
    _make_venv(tmp_path, python_target="/nonexistent/python3.13")  # intérprete muerto
    r = _bash(f"check_venv 'Svc' '{tmp_path}' 'make setup'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "HUÉRFANO" in out, out
    assert "make setup" in out
    assert "rc=1" in out


def test_check_venv_missing_workdir_reports_no_existe(tmp_path):
    missing = tmp_path / "nope"
    r = _bash(f"check_venv 'Svc' '{missing}' 'make setup'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "no existe" in out and "rc=1" in out, out


# =============================================================================
# do_doctor — agrega sobre SERVICES, filtra no-python, exit 1 si algo mal
# =============================================================================


def test_doctor_aggregates_and_flags_any_bad(tmp_path):
    """do_doctor recorre SERVICES, reporta cada venv python y sale 1 si alguno está mal.
    Se inyecta un SERVICES controlado (ok + ausente + un node que debe IGNORAR)."""
    ok_dir = tmp_path / "ok"
    _make_venv(ok_dir, python_target=sys.executable)
    absent_dir = tmp_path / "absent"
    absent_dir.mkdir()
    node_dir = tmp_path / "node"
    (node_dir / "node_modules").mkdir(parents=True)

    services = (
        f"svcok|Svc OK|{ok_dir}|8000|.venv|cmd|hintOK\n"
        f"svcabs|Svc Absent|{absent_dir}|8001|.venv|cmd|hintABS\n"
        f"svcnode|Svc Node|{node_dir}|8002|node_modules|cmd|hintNODE"
    )
    r = _bash(f"SERVICES='{services}'\ndo_doctor; echo rc=$?")
    out = r.stdout + r.stderr

    assert "Svc OK" in out and "OK (python" in out
    assert "Svc Absent" in out and "AUSENTE" in out
    # el servicio node (marker != .venv) NO se diagnostica como venv
    assert "Svc Node" not in out, f"do_doctor no debe chequear servicios no-python: {out}"
    assert "rc=1" in out, f"con un venv ausente, do_doctor debe salir 1: {out}"


def test_doctor_all_healthy_exits_zero(tmp_path):
    ok1 = tmp_path / "a"
    ok2 = tmp_path / "b"
    _make_venv(ok1, python_target=sys.executable)
    _make_venv(ok2, python_target=sys.executable)
    services = (
        f"a|Svc A|{ok1}|8000|.venv|cmd|hintA\n"
        f"b|Svc B|{ok2}|8001|.venv|cmd|hintB"
    )
    r = _bash(f"SERVICES='{services}'\ndo_doctor; echo rc=$?")
    out = r.stdout + r.stderr
    assert "rc=0" in out, out
    assert "sanos" in out


def test_doctor_subcommand_is_wired_in_dispatch():
    """El dispatch acepta `doctor` (anti-regresión de que el subcomando siga cableado)."""
    text = _LAUNCHER.read_text(encoding="utf-8")
    assert "doctor) do_doctor" in text, "el subcomando `doctor` no está cableado en el case"
    assert "start|stop|status|doctor" in text, "la ayuda de uso no menciona `doctor`"
