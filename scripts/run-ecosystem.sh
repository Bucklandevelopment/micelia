#!/usr/bin/env bash
# run-ecosystem.sh — arranque local-first NATIVO del ecosistema UTOP.IA (M1).
# Uso: scripts/run-ecosystem.sh {start|stop|status} [--with-codking-inference]
#
# Orquesta los comandos que YA existen en cada proyecto (no reinventa arranques) y
# deja Micelia + los frontends de dominio accesibles por URL. Cada servicio se
# backgroundea con log y PID propios; `stop` mata por PID y por puerto.
#
# HONESTIDAD: los 6 dominios nunca se han arrancado juntos. La PRIMERA pasada puede
# exigir instalar dependencias por proyecto (npm install / crear .venv). El script
# detecta las deps ausentes y reporta el comando de instalación en vez de fallar en
# silencio: instala lo que te pida y vuelve a lanzar `start`.
#
# Guardarraíl: local-first M1. Infra = como mucho `make docker-infra` (pg+redis+ollama)
# vía podman. NUNCA docker-full. El stack Podman de `deploy/` queda fuera (sin validar).

set -uo pipefail

MICELIA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECTS_DIR="$(cd "$MICELIA_DIR/.." && pwd)"
RUN_DIR="$MICELIA_DIR/logs/ecosystem"
mkdir -p "$RUN_DIR"

WITH_CODKING_INFERENCE=0
for arg in "$@"; do
  [ "$arg" = "--with-codking-inference" ] && WITH_CODKING_INFERENCE=1
done

# ---- helpers ---------------------------------------------------------------

port_in_use() { lsof -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1; }

kill_port() {
  local pids
  pids="$(lsof -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
}

wait_port() {  # wait_port PORT SECONDS
  local p="$1" secs="$2"
  for _ in $(seq 1 "$secs"); do
    port_in_use "$p" && return 0
    sleep 1
  done
  return 1
}

# venv_python_ok WORKDIR: 0 si el intérprete del .venv EJECUTA, !=0 si roto/ausente.
# Fuente única del check de venv-huérfano (C87): lo usan start_svc (para no arrancar un
# venv muerto) y el doctor (para diagnosticarlo). Un .venv puede existir con el dir intacto
# pero el python al que apunta desaparecido (brew sube 3.13→3.14) → aquí se caza.
venv_python_ok() { "$1/.venv/bin/python" -c '' >/dev/null 2>&1; }

# start_svc ID "Etiqueta" WORKDIR PORT DEPS_MARKER "COMANDO" "PISTA_INSTALL"
# DEPS_MARKER: ruta (relativa a WORKDIR) que debe existir, o "-" si no aplica.
start_svc() {
  local id="$1" label="$2" workdir="$3" port="$4" marker="$5" cmd="$6" hint="$7"
  local log="$RUN_DIR/$id.log" pidf="$RUN_DIR/$id.pid"

  if [ ! -d "$workdir" ]; then
    echo "  ✗ $label — no existe $workdir (omitido)"; return 0
  fi
  if port_in_use "$port"; then
    echo "  • $label — :$port ya en uso (se asume corriendo, omitido)"; return 0
  fi
  if [ "$marker" != "-" ] && [ ! -e "$workdir/$marker" ]; then
    echo "  ⚠ $label — faltan dependencias ($marker). Instala con:"
    echo "      $hint"
    return 0
  fi
  # Un `.venv` puede EXISTIR pero estar HUÉRFANO: si brew actualiza python (p.ej.
  # 3.13→3.14), el intérprete al que apunta el venv desaparece y `.venv/bin/uvicorn`
  # muere con "bad interpreter" — un log críptico, no la pista de instalación que este
  # script PROMETE dar ("detecta deps ausentes y reporta el comando en vez de fallar en
  # silencio"). El check `-e` de arriba no lo caza (el dir sigue ahí). Verificamos que
  # el intérprete EJECUTA, no solo que existe. (Real: canela, C87.)
  if [ "$marker" = ".venv" ] && ! venv_python_ok "$workdir"; then
    echo "  ⚠ $label — .venv existe pero su intérprete no arranca (¿brew actualizó python?). Recrea con:"
    echo "      $hint"
    return 0
  fi

  echo "  → $label — arrancando en :$port ..."
  ( cd "$workdir" && nohup bash -lc "$cmd" >> "$log" 2>&1 & echo $! > "$pidf" )
  if wait_port "$port" 40; then
    echo "  ✓ $label — vivo en http://localhost:$port"
  else
    echo "  ⚠ $label — no abrió :$port en 40s; revisa $log"
  fi
}

stop_svc() {  # stop_svc ID PORT
  local id="$1" port="$2" pidf="$RUN_DIR/$1.pid"
  if [ -f "$pidf" ]; then
    kill "$(cat "$pidf")" 2>/dev/null || true
    rm -f "$pidf"
  fi
  kill_port "$port"
}

# ---- catálogo (bash 3.2 de macOS: sin arrays asociativos) -------------------
# Cada línea: id|Etiqueta|workdir|puerto|deps_marker|comando|pista_install
# marker = ruta relativa a workdir que debe existir ("-" si no aplica).
# NOTA: canela `make run-all` e ideacursi `npm run dev` levantan API+FE juntos.
# FUENTE DE VERDAD del mapa de puertos: scripts/ecosystem-ports.json (DP-12). Si
# cambias un puerto aquí, cámbialo también en el JSON; test_ecosystem_ports_manifest
# lo verifica en `make verify`.

SERVICES="\
panel|Micelia panel|$MICELIA_DIR/frontend|3001|node_modules|npm run dev|cd micelia/frontend && npm install
biohack-fe|Biohack FE|$PROJECTS_DIR/biohack-app/frontend|5173|node_modules|npm run dev|cd biohack-app/frontend && npm install
biohack-be|Biohack API|$PROJECTS_DIR/biohack-app/backend|8080|.venv|.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080|cd biohack-app/backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt (+ pg/redis via docker-infra)
canela|Canela (API+UI)|$PROJECTS_DIR/canela-molida|8501|.venv|make run-all|cd canela-molida && make setup (crea .venv + deps)
ideacursi|Ideacursi (BE+FE)|$PROJECTS_DIR/ideacursi-tool|6060|node_modules|npm run dev|cd ideacursi-tool && npm install && npm run docker:deps
codking-vis|CodKing visualizer|$PROJECTS_DIR/codking/rlm_framework/visualizer|3009|node_modules|npx next dev -p 3009|cd codking/rlm_framework/visualizer && npm install
automation|Auto-mat-ion demo|$PROJECTS_DIR/auto-mat-ion|8891|node_modules|npm run demo|cd auto-mat-ion && npm install"

# cybertools (:8000) NO es un frontend — se arranca porque es el dominio `security`
# que el REGISTRY de Micelia sondea (config.py: security_service_url=:8000, health
# endpoint `/health`). Sin él, `security` queda unhealthy aunque el launcher haya
# levantado todo lo demás. Precedente: `biohack-be` ya está aquí por el mismo motivo
# (sirve el slot `health` en :8080), no por tener UI.
# COLISIÓN (DP-12, C76): codking-be comparte :8000 y el manifest declara "no correr
# ambos a la vez" → son EXCLUYENTES y se elige de forma explícita, no por carrera de
# `port_in_use`: con --with-codking-inference manda codking-be (es lo que el flag pide).
if [ "$WITH_CODKING_INFERENCE" = "1" ]; then
  echo "  ⚠ --with-codking-inference: codking-be toma :8000; cybertools NO se arranca"
  echo "    (comparten puerto, DP-12) → el slot 'security' del registry quedará unhealthy."
  SERVICES="$SERVICES
codking-be|CodKing inference|$PROJECTS_DIR/codking|8000|-|python3 -m codking.api.inference_server --port 8000|cd codking && pip install -r requirements.txt (+ checkpoint)"
else
  SERVICES="$SERVICES
cybertools|Cybertools API (security)|$PROJECTS_DIR/cybertools|8000|.venv|.venv/bin/uvicorn scanet.api:app --host 127.0.0.1 --port 8000|cd cybertools && python3 -m venv .venv && .venv/bin/pip install -e ."
fi

# ---- acciones --------------------------------------------------------------

do_start() {
  preflight

  echo "== Infra (podman: postgres+redis+ollama) =="
  if command -v podman-compose >/dev/null 2>&1 || command -v podman >/dev/null 2>&1; then
    make -C "$MICELIA_DIR" docker-infra || echo "  ⚠ docker-infra falló; los backends que necesiten pg/redis degradarán."
  else
    echo "  ⚠ podman no está; sin pg/redis los backends de biohack/ideacursi/canela degradan."
  fi

  echo "== Micelia gateway =="
  bash "$MICELIA_DIR/scripts/run-local.sh" start || echo "  ⚠ gateway no confirmó health; revisa logs/micelia-gateway.log"

  echo "== Frontends y backends de dominio =="
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    start_svc "$id" "$label" "$dir" "$port" "$marker" "$cmd" "$hint"
  done <<< "$SERVICES"

  echo
  echo "Listo. Hub de servicios: http://localhost:3001/servicios"
  echo "Para el estado:  scripts/run-ecosystem.sh status"
}

do_stop() {
  echo "== Parando dominios =="
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    stop_svc "$id" "$port"
    echo "  · $label detenido"
  done <<< "$SERVICES"
  # :8000 lo puede tener cybertools o codking-be según el flag con el que se arrancó
  # (son excluyentes). `stop` no sabe cuál fue: limpia el puerto en ambos casos.
  stop_svc codking-be 8000
  echo "== Parando gateway Micelia =="
  bash "$MICELIA_DIR/scripts/run-local.sh" stop || true
  echo "== Bajando infra =="
  make -C "$MICELIA_DIR" docker-down 2>/dev/null || echo "  (docker-down no disponible/omitido)"
  echo "Ecosistema detenido."
}

do_status() {
  printf "%-22s %-7s %s\n" "SERVICIO" "PUERTO" "ESTADO"
  printf "%-22s %-7s %s\n" "Micelia gateway" "8888" "$(port_in_use 8888 && echo '✓ up' || echo '✗ down')"
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    printf "%-22s %-7s %s\n" "$label" "$port" "$(port_in_use "$port" && echo '✓ up' || echo '✗ down')"
  done <<< "$SERVICES"
}

# check_venv LABEL WORKDIR HINT: imprime el estado del .venv de un servicio y devuelve
# 0 (sano) / 1 (problema). Read-only: NO arranca ni instala nada.
check_venv() {
  local label="$1" workdir="$2" hint="$3" ver
  if [ ! -d "$workdir" ]; then
    printf "  ✗ %-24s no existe %s\n" "$label" "$workdir"; return 1
  fi
  if [ ! -e "$workdir/.venv" ]; then
    printf "  ✗ %-24s .venv AUSENTE — deps sin instalar\n" "$label"
    printf "       crea: %s\n" "$hint"; return 1
  fi
  if ver="$("$workdir/.venv/bin/python" -c 'import platform;print(platform.python_version())' 2>/dev/null)"; then
    printf "  ✓ %-24s OK (python %s)\n" "$label" "$ver"; return 0
  fi
  printf "  ⚠ %-24s HUÉRFANO — el intérprete del .venv no arranca (¿brew subió python?)\n" "$label"
  printf "       recrea: %s\n" "$hint"; return 1
}

# check_node LABEL WORKDIR HINT: estado de node_modules de un servicio node. 0 (OK) /
# 1 (problema). Read-only. A diferencia de un venv (que puede quedar HUÉRFANO si el python
# desaparece), node_modules solo está presente-y-poblado o no: un dir vacío cuenta como
# ausente (npm interrumpido).
check_node() {
  local label="$1" workdir="$2" hint="$3"
  if [ ! -d "$workdir" ]; then
    printf "  ✗ %-24s no existe %s\n" "$label" "$workdir"; return 1
  fi
  if [ ! -d "$workdir/node_modules" ] || [ -z "$(ls -A "$workdir/node_modules" 2>/dev/null)" ]; then
    printf "  ✗ %-24s node_modules AUSENTE — deps sin instalar\n" "$label"
    printf "       instala: %s\n" "$hint"; return 1
  fi
  printf "  ✓ %-24s OK (node_modules presente)\n" "$label"; return 0
}

# doctor: diagnostica de UNA VEZ la arrancabilidad de TODO el ecosistema (venvs python +
# node_modules), sin arrancar ni instalar nada. Convierte DP-16 (venvs huérfanos por bumps
# de brew) y DP-17 (biohack sin venv), y las deps node ausentes, de sorpresa-al-arrancar en
# diagnóstico temprano. Agrupa por runtime para que el reporte se lea de un vistazo.
do_doctor() {
  echo "== Doctor de arrancabilidad del ecosistema (read-only) =="
  echo "  python del sistema: $(python3 --version 2>&1)"
  echo "  node del sistema:   $(node --version 2>&1)"
  local any_bad=0
  echo "  — servicios python (.venv) —"
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    [ "$marker" = ".venv" ] || continue
    check_venv "$label" "$dir" "$hint" || any_bad=1
  done <<< "$SERVICES"
  echo "  — servicios node (node_modules) —"
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    [ "$marker" = "node_modules" ] || continue
    check_node "$label" "$dir" "$hint" || any_bad=1
  done <<< "$SERVICES"
  echo
  if [ "$any_bad" = "1" ]; then
    echo "  → Hay deps que impedirían arrancar (venv DP-16/DP-17 o node_modules). Instálalas antes de 'start'."
    return 1
  fi
  echo "  ✓ Todo el ecosistema (python + node) tiene sus deps listas."
  return 0
}

# install_node LABEL WORKDIR: `npm install` en el workdir. Se corre SIEMPRE (no se salta un
# árbol "presente"): `npm install` ES idempotente y COMPLETA un node_modules incompleto —
# justo el caso de ideacursi (DP-19: presente pero le falta `reflect-metadata`), que un skip
# por "node_modules poblado" NO arreglaría. Sobre un árbol completo es un no-op rápido.
# 0 (ok) / 1 (fallo).
install_node() {
  local label="$1" workdir="$2"
  if [ ! -d "$workdir" ]; then
    printf "  ✗ %-24s no existe %s (omitido)\n" "$label" "$workdir"; return 1
  fi
  printf "  → %-24s npm install …\n" "$label"
  if ( cd "$workdir" && npm install ); then
    printf "  ✓ %-24s deps node OK\n" "$label"; return 0
  fi
  printf "  ✗ %-24s npm install FALLÓ (ver salida arriba)\n" "$label"; return 1
}

# install_venv LABEL WORKDIR: recrea el .venv (si falta o está huérfano) con el python del
# sistema e instala deps auto-detectando el modo (requirements.txt / pyproject|setup.py / -e).
# NO borra un venv sano. 0 (ok/ya-ok) / 1 (fallo). Idempotente.
install_venv() {
  local label="$1" workdir="$2"
  if [ ! -d "$workdir" ]; then
    printf "  ✗ %-24s no existe %s (omitido)\n" "$label" "$workdir"; return 1
  fi
  if venv_python_ok "$workdir"; then
    printf "  • %-24s .venv ya sano (omitido)\n" "$label"; return 0
  fi
  # venv ausente o HUÉRFANO (intérprete muerto): recrear desde cero.
  [ -e "$workdir/.venv" ] && rm -rf "$workdir/.venv"
  printf "  → %-24s creando .venv (%s) …\n" "$label" "$(python3 --version 2>&1)"
  if ! python3 -m venv "$workdir/.venv"; then
    printf "  ✗ %-24s no se pudo crear el .venv\n" "$label"; return 1
  fi
  local pip="$workdir/.venv/bin/pip"
  "$pip" install -q --upgrade pip >/dev/null 2>&1 || true
  local rc=0
  if [ -f "$workdir/requirements.txt" ]; then
    printf "  → %-24s pip install -r requirements.txt …\n" "$label"
    "$pip" install -q -r "$workdir/requirements.txt" || rc=1
  elif [ -f "$workdir/pyproject.toml" ] || [ -f "$workdir/setup.py" ]; then
    printf "  → %-24s pip install -e . …\n" "$label"
    "$pip" install -q -e "$workdir" || rc=1
  else
    printf "  ✗ %-24s no sé instalar deps (sin requirements.txt / pyproject / setup.py)\n" "$label"
    return 1
  fi
  if [ "$rc" = "0" ]; then
    printf "  ✓ %-24s deps python instaladas (python %s)\n" "$label" \
      "$("$workdir/.venv/bin/python" -c 'import platform;print(platform.python_version())' 2>/dev/null)"
    return 0
  fi
  # ROLLBACK: un pip que falla deja un .venv A MEDIAS cuyo intérprete SÍ arranca → el doctor
  # lo reportaría OK (falso, como el node_modules incompleto de DP-19). Borrarlo restaura el
  # estado honesto (doctor: AUSENTE) en vez de un venv engañoso. Atómico: todo o nada.
  rm -rf "$workdir/.venv"
  printf "  ✗ %-24s pip install FALLÓ (deps sin wheel para este python? ver arriba). .venv revertido.\n" "$label"
  return 1
}

# setup: instala/recrea las deps de cada dominio (node_modules + venvs) para desbloquear los
# arranques. Idempotente (solo toca lo que el doctor marcaría). Autorizado por Jessicache
# (C102) a instalar deps de repos hermanos — el ÚNICO punto de la rutina que los modifica, y
# solo su árbol de deps gitignored (node_modules/.venv), nunca su código ni su `.env`.
do_setup() {
  echo "== Setup de deps del ecosistema (instala lo que falte; idempotente) =="
  echo "  python del sistema: $(python3 --version 2>&1)"
  echo "  node del sistema:   $(node --version 2>&1)"
  local any_bad=0
  echo "  — servicios node (node_modules) —"
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    [ "$marker" = "node_modules" ] || continue
    install_node "$label" "$dir" || any_bad=1
  done <<< "$SERVICES"
  echo "  — servicios python (.venv) —"
  while IFS='|' read -r id label dir port marker cmd hint; do
    [ -z "$id" ] && continue
    [ "$marker" = ".venv" ] || continue
    install_venv "$label" "$dir" || any_bad=1
  done <<< "$SERVICES"
  echo
  if [ "$any_bad" = "1" ]; then
    echo "  → Algún dominio no quedó listo (ver ✗ arriba). Corre 'doctor' para el estado."
    return 1
  fi
  echo "  ✓ Deps de todos los dominios instaladas. 'doctor' debería estar todo en verde."
  return 0
}

# preflight: corre el doctor ANTES de arrancar y, si hay blockers, da el contexto propio
# del arranque (qué pasará y cómo abortar) — cierra el bucle diagnóstico→prevención de C97/98.
# NO aborta: `start_svc` ya OMITE con gracia cada servicio sin deps, así que el resto arranca;
# el preflight solo lo hace visible DE UNA VEZ arriba, en vez de servicio a servicio.
preflight() {
  echo "== Preflight de arrancabilidad =="
  if ! do_doctor; then
    echo
    echo "  ⚠ PREFLIGHT: los servicios sin deps (arriba) se OMITIRÁN; el resto arranca igual."
    echo "    Ctrl-C ahora si prefieres instalarlos primero (o corre 'doctor' para el detalle)."
  fi
}

# Solo despachar cuando se EJECUTA el script, no cuando se SOURCEA (los tests lo
# sourcean para ejercer `start_svc`/helpers en aislamiento; sin este guard, sourcear
# arrancaría el ecosistema entero por el default `start`). Idiom estándar de bash.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  case "${1:-start}" in
    start)  do_start ;;
    stop)   do_stop ;;
    status) do_status ;;
    doctor) do_doctor ;;
    setup)  do_setup ;;
    *) echo "Uso: $0 {start|stop|status|doctor|setup} [--with-codking-inference]"; exit 2 ;;
  esac
fi
