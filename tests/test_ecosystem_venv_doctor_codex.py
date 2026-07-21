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

import re
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


def _make_node(dir_: Path, *, populated: bool | None) -> None:
    """node_modules del servicio: None=sin dir, False=dir vacío, True=poblado."""
    dir_.mkdir(parents=True, exist_ok=True)
    if populated is None:
        return
    nm = dir_ / "node_modules"
    nm.mkdir()
    if populated:
        (nm / "some-pkg").mkdir()


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
# check_node — el diagnóstico de UN servicio node
# =============================================================================


def test_check_node_populated_reports_ok(tmp_path):
    _make_node(tmp_path, populated=True)
    r = _bash(f"check_node 'Fe' '{tmp_path}' 'npm install'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "OK (node_modules presente)" in out, out
    assert "rc=0" in out


def test_check_node_absent_reports_ausente(tmp_path):
    _make_node(tmp_path, populated=None)  # workdir sí, node_modules no
    r = _bash(f"check_node 'Fe' '{tmp_path}' 'npm install'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "node_modules AUSENTE" in out and "npm install" in out and "rc=1" in out, out


def test_check_node_empty_dir_counts_as_absent(tmp_path):
    """Un node_modules vacío (npm interrumpido) cuenta como ausente, no como OK."""
    _make_node(tmp_path, populated=False)  # dir vacío
    r = _bash(f"check_node 'Fe' '{tmp_path}' 'npm install'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "AUSENTE" in out and "rc=1" in out, out


# =============================================================================
# do_doctor — agrega sobre SERVICES, filtra no-python, exit 1 si algo mal
# =============================================================================


def test_doctor_covers_both_python_and_node_and_flags_any_bad(tmp_path):
    """do_doctor diagnostica AMBOS runtimes (venv python + node_modules) en una pasada y
    sale 1 si alguno está mal. C98 amplía el doctor de C97 (que solo miraba venvs). Se
    inyecta un SERVICES con un venv sano, un venv ausente, un node sano y un node ausente."""
    venv_ok = tmp_path / "vok"
    _make_venv(venv_ok, python_target=sys.executable)
    venv_bad = tmp_path / "vbad"
    venv_bad.mkdir()  # sin .venv
    node_ok = tmp_path / "nok"
    _make_node(node_ok, populated=True)
    node_bad = tmp_path / "nbad"
    _make_node(node_bad, populated=None)  # sin node_modules

    services = (
        f"vok|Venv OK|{venv_ok}|8000|.venv|cmd|hintVOK\n"
        f"vbad|Venv Bad|{venv_bad}|8001|.venv|cmd|hintVBAD\n"
        f"nok|Node OK|{node_ok}|8002|node_modules|cmd|hintNOK\n"
        f"nbad|Node Bad|{node_bad}|8003|node_modules|cmd|hintNBAD"
    )
    r = _bash(f"SERVICES='{services}'\ndo_doctor; echo rc=$?")
    out = r.stdout + r.stderr

    assert "Venv OK" in out and "OK (python" in out
    assert "Venv Bad" in out and ".venv AUSENTE" in out
    # C98: los servicios node AHORA se diagnostican (antes se ignoraban).
    assert "Node OK" in out and "OK (node_modules presente)" in out
    assert "Node Bad" in out and "node_modules AUSENTE" in out
    assert "rc=1" in out, f"con deps ausentes, do_doctor debe salir 1: {out}"


def test_doctor_all_healthy_exits_zero(tmp_path):
    venv_ok = tmp_path / "v"
    _make_venv(venv_ok, python_target=sys.executable)
    node_ok = tmp_path / "n"
    _make_node(node_ok, populated=True)
    services = (
        f"v|Venv A|{venv_ok}|8000|.venv|cmd|hintA\n"
        f"n|Node B|{node_ok}|8001|node_modules|cmd|hintB"
    )
    r = _bash(f"SERVICES='{services}'\ndo_doctor; echo rc=$?")
    out = r.stdout + r.stderr
    assert "rc=0" in out, out
    assert "deps listas" in out  # "Todo el ecosistema (python + node) tiene sus deps listas."


def test_doctor_subcommand_is_wired_in_dispatch():
    """El dispatch acepta `doctor` (anti-regresión de que el subcomando siga cableado)."""
    text = _LAUNCHER.read_text(encoding="utf-8")
    assert "doctor) do_doctor" in text, "el subcomando `doctor` no está cableado en el case"
    assert "start|stop|status|doctor" in text, "la ayuda de uso no menciona `doctor`"


# =============================================================================
# setup — instala/recrea deps (C102). Se testea la lógica IDEMPOTENTE (skip) y el
# dispatch; el install real (npm/pip) se verifica en vivo, no en la suite.
# =============================================================================


def test_install_venv_skips_when_already_healthy(tmp_path):
    """install_venv NO recrea un venv sano (no borra deps buenas). Branch de skip, hermético
    (no invoca pip). El install real de un venv roto se verifica en vivo, no en la suite."""
    _make_venv(tmp_path, python_target=sys.executable)
    r = _bash(f"install_venv 'Svc' '{tmp_path}'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "ya sano" in out and "rc=0" in out, out


def test_install_node_missing_workdir_fails(tmp_path):
    """install_node falla limpio si el workdir no existe (sin invocar npm)."""
    missing = tmp_path / "nope"
    r = _bash(f"install_node 'Fe' '{missing}'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "no existe" in out and "rc=1" in out, out


def test_install_venv_without_manifest_fails_without_leaving_broken_venv(tmp_path):
    """install_venv en un workdir sin requirements.txt/pyproject/setup.py falla (no sabe
    instalar) y NO deja un .venv a medias — el mismo principio de rollback que aplica cuando
    pip falla (verificado en vivo con biohack en 3.14). Hermético: no hay deps que instalar."""
    r = _bash(f"install_venv 'Svc' '{tmp_path}'; echo rc=$?")
    out = r.stdout + r.stderr
    assert "rc=1" in out and "no sé instalar" in out, out


def test_setup_venv_side_is_idempotent_when_healthy(tmp_path):
    """do_setup sobre venvs sanos no recrea nada y sale 0 (idempotente). Se inyectan SOLO
    servicios venv (los node harían `npm install` REAL, fuera del alcance hermético)."""
    venv_a = tmp_path / "a"
    venv_b = tmp_path / "b"
    _make_venv(venv_a, python_target=sys.executable)
    _make_venv(venv_b, python_target=sys.executable)
    services = (
        f"a|Venv A|{venv_a}|8000|.venv|cmd|hintA\n"
        f"b|Venv B|{venv_b}|8001|.venv|cmd|hintB"
    )
    r = _bash(f"SERVICES='{services}'\ndo_setup; echo rc=$?")
    out = r.stdout + r.stderr
    assert out.count("ya sano") == 2
    assert "rc=0" in out and "Deps de todos los dominios instaladas" in out


def test_setup_subcommand_is_wired_in_dispatch():
    text = _LAUNCHER.read_text(encoding="utf-8")
    assert "setup)  do_setup" in text, "el subcomando `setup` no está cableado en el case"
    assert "start|stop|status|doctor|setup" in text, "la ayuda de uso no menciona `setup`"


# =============================================================================
# kill_tree (C107) — `stop` debe matar el árbol, no solo el wrapper (dominios BE+FE)
# =============================================================================


def test_kill_tree_kills_whole_process_tree():
    """kill_tree mata la raíz Y sus descendientes. Regresión del bug de C107: los dominios
    multi-proceso (canela `make run-all`, ideacursi `npm run dev`) arrancan un wrapper cuyos
    HIJOS viven en otros puertos; `stop` mataba solo el wrapper → huérfanos comiendo RAM. Se
    levanta un árbol de `sleep`s con una duración única (para no tocar otros procesos), se
    kill_tree la raíz y se comprueba que NINGÚN sleep sobrevive (el `kill` plano del wrapper
    los habría dejado vivos)."""
    uniq = "29471837"  # duración única → aísla los procesos de este test
    # Árbol de 2 niveles: root → bash intermedio → 2 sleeps. Los sleeps son NIETOS del root,
    # así se prueba que kill_tree RECURRE en profundidad (el caso real: npm→node→nodemon→node).
    snippet = f"""
pkill -f 'sleep {uniq}' 2>/dev/null || true  # clean slate (aísla de corridas previas)
bash -c "bash -c 'sleep {uniq} & sleep {uniq} & wait' & wait" &
root=$!
sleep 1
echo "before=$(pgrep -f 'sleep {uniq}' | wc -l | tr -d ' ')"
kill_tree $root
sleep 1
echo "after=$(pgrep -f 'sleep {uniq}' | wc -l | tr -d ' ')"
pkill -f 'sleep {uniq}' 2>/dev/null || true
"""
    r = _bash(snippet)
    out = r.stdout + r.stderr
    before = re.search(r"before=(\d+)", out)
    after = re.search(r"after=(\d+)", out)
    assert before and int(before.group(1)) >= 2, f"el árbol de prueba no se levantó: {out}"
    assert after and int(after.group(1)) == 0, (
        f"kill_tree dejó descendientes vivos (nietos incluidos) → `stop` seguiría dejando "
        f"huérfanos (C107): {out}"
    )


def test_stop_svc_uses_kill_tree():
    """`stop_svc` mata el árbol (kill_tree), no solo el PID guardado — anti-regresión del fix
    de C107 (si vuelve a `kill "$(cat ...)"` a secas, los dominios BE+FE dejan huérfanos)."""
    text = _LAUNCHER.read_text(encoding="utf-8")
    m = re.search(r"stop_svc\(\)\s*\{(.*?)\n\}", text, re.DOTALL)
    assert m, "no se encontró stop_svc"
    assert "kill_tree" in m.group(1), (
        "stop_svc dejó de usar kill_tree; volvería a dejar huérfanos los dominios multi-proceso."
    )


# =============================================================================
# preflight — el doctor integrado en `start` (C99): avisa, no aborta
# =============================================================================


def test_preflight_warns_on_blockers_but_does_not_abort(tmp_path):
    """Con un blocker, el preflight muestra el reporte del doctor Y la guía propia del
    arranque (se omitirán / Ctrl-C), pero devuelve 0 → `start` sigue arrancando el resto."""
    venv_bad = tmp_path / "vbad"
    venv_bad.mkdir()  # sin .venv
    services = f"vbad|Venv Bad|{venv_bad}|8001|.venv|cmd|hintVBAD"
    r = _bash(f"SERVICES='{services}'\npreflight; echo rc=$?")
    out = r.stdout + r.stderr
    assert "PREFLIGHT" in out and "OMITIRÁN" in out, out
    assert "Ctrl-C" in out
    assert "rc=0" in out, f"el preflight NO debe abortar el arranque: {out}"


def test_preflight_no_warning_when_all_healthy(tmp_path):
    """Sin blockers, el preflight no añade el aviso de omisión — solo el visto bueno del
    doctor. (Anti-ruido: no asusta cuando todo está listo.)"""
    venv_ok = tmp_path / "v"
    _make_venv(venv_ok, python_target=sys.executable)
    services = f"v|Venv A|{venv_ok}|8000|.venv|cmd|hintA"
    r = _bash(f"SERVICES='{services}'\npreflight; echo rc=$?")
    out = r.stdout + r.stderr
    assert "deps listas" in out
    assert "PREFLIGHT" not in out, f"no debe avisar de omisión si todo está sano: {out}"
    assert "rc=0" in out


def test_start_runs_preflight_before_infra():
    """`do_start` corre el preflight, y ANTES de levantar infra/gateway — para que el
    diagnóstico salga primero, no intercalado con los arranques."""
    text = _LAUNCHER.read_text(encoding="utf-8")
    m = re.search(r"do_start\(\)\s*\{(.*?)\n\}", text, re.DOTALL)
    assert m, "no se encontró do_start()"
    body = m.group(1)
    assert "preflight" in body, "do_start ya no corre el preflight"
    assert body.index("preflight") < body.index("== Infra"), (
        "el preflight debe ejecutarse ANTES de la sección de infra"
    )
