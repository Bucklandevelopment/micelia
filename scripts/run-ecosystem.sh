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

# codking inference (pesado: checkpoint + PyTorch) — opt-in.
if [ "$WITH_CODKING_INFERENCE" = "1" ]; then
  SERVICES="$SERVICES
codking-be|CodKing inference|$PROJECTS_DIR/codking|8000|-|python3 -m codking.api.inference_server --port 8000|cd codking && pip install -r requirements.txt (+ checkpoint)"
fi

# ---- acciones --------------------------------------------------------------

do_start() {
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
  # codking-be puede no estar en la tabla si no se arrancó con el flag: limpia su puerto igual.
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

case "${1:-start}" in
  start)  do_start ;;
  stop)   do_stop ;;
  status) do_status ;;
  *) echo "Uso: $0 {start|stop|status} [--with-codking-inference]"; exit 2 ;;
esac
