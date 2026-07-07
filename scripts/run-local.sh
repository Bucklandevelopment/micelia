#!/usr/bin/env bash
# run-local.sh — arranque mínimo del gateway Micelia sin Docker.
# Uso: scripts/run-local.sh {start|stop|status|logs}
# Postgres/Redis/Ollama son opcionales: el gateway degrada con warning si faltan.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_DIR/.venv"
PORT="${GATEWAY_PORT:-8888}"
LOG_FILE="$REPO_DIR/logs/micelia-gateway.log"
PID_FILE="$REPO_DIR/logs/micelia-gateway.pid"

cd "$REPO_DIR"
mkdir -p logs

PY="$VENV/bin/python"
[ -x "$PY" ] || { echo "ERROR: no existe $PY (crea el venv con 'make setup')"; exit 1; }

start() {
  if status_quiet; then
    echo "Micelia ya está corriendo (PID $(cat "$PID_FILE")) en :$PORT"
    return 0
  fi
  echo "Arrancando Micelia gateway en http://127.0.0.1:$PORT ..."
  nohup "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
    >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  # Espera health hasta 30s
  for _ in $(seq 1 30); do
    sleep 1
    if curl -fsS "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1; then
      echo "OK — gateway vivo. Docs: http://127.0.0.1:$PORT/docs"
      return 0
    fi
  done
  echo "WARN: el gateway no respondió a /api/v1/health en 30s; revisa $LOG_FILE"
  return 1
}

stop() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")" && rm -f "$PID_FILE"
    echo "Micelia detenido."
  else
    pkill -f "uvicorn app.main:app" 2>/dev/null && echo "Micelia detenido (pkill)." || echo "No estaba corriendo."
    rm -f "$PID_FILE"
  fi
}

status_quiet() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

status() {
  if status_quiet; then
    echo "RUNNING (PID $(cat "$PID_FILE"))"
    curl -fsS "http://127.0.0.1:$PORT/api/v1/health" 2>/dev/null || true
    echo
  else
    echo "STOPPED"
  fi
}

case "${1:-start}" in
  start)  start ;;
  stop)   stop ;;
  status) status ;;
  logs)   tail -n 50 "$LOG_FILE" ;;
  *) echo "Uso: $0 {start|stop|status|logs}"; exit 2 ;;
esac
