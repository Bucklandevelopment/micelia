#!/usr/bin/env bash
# funnel-preflight.sh — verifica de UNA VEZ la cadena de deploy del funnel
# (micelia.idmmortality.com) desde el lado de RED, tras los pasos ⏳HUMANO del runbook.
#
# NO decide nada ni cambia infra: es read-only. DP-1..DP-4 ya están DECIDIDAS por Jessicache
# (hosting local, host único micelia.idmmortality.com, secretos en deploy/.env, postgres del
# compose). Lo que queda son pasos de PANEL humanos (A-record IONOS, port-forward TP-Link 80/443,
# pmset) + su verificación manual (dig/curl/openssl), que el runbook lista suelta. Este script
# los agrupa: corre los 4 checks y dice, por cada uno, qué sección del runbook mirar si falla.
#
# Uso: scripts/funnel-preflight.sh [host]        (default: micelia.idmmortality.com)
# Guardarraíl: local-first, sin cambios de estado. Solo consulta DNS/puerto/TLS/health.

set -uo pipefail

HOST="${1:-micelia.idmmortality.com}"

# --- report ---------------------------------------------------------------
# report_step LABEL OK HINT: imprime ✓/✗ y, si falla, la pista (sección del runbook).
report_step() {
  local label="$1" ok="$2" hint="$3"
  if [ "$ok" = "1" ]; then
    printf "  ✓ %-34s\n" "$label"; return 0
  fi
  printf "  ✗ %-34s → %s\n" "$label" "$hint"; return 1
}

# evaluate_funnel HOST DNS_IP PORT_OK TLS_DAYS HEALTH_CODE
# Núcleo PURO (sin I/O): decide ✓/✗ por paso a partir de valores ya recogidos. Testeable en
# aislamiento. Devuelve 0 si TODO ok, 1 si algún paso falla.
evaluate_funnel() {
  local host="$1" dns_ip="$2" port_ok="$3" tls_days="$4" health_code="$5" any_bad=0
  echo "== Funnel preflight: $host (read-only) =="

  # 1. DNS: el A-record resuelve a una IP.
  [ -n "$dns_ip" ] && report_step "DNS resuelve ($dns_ip)" 1 "" \
    || { report_step "DNS resuelve" 0 "§2: A-record de $host → IP de casa (panel IONOS)"; any_bad=1; }

  # 2. Puerto 443 alcanzable desde fuera (port-forward hecho).
  [ "$port_ok" = "1" ] && report_step ":443 alcanzable" 1 "" \
    || { report_step ":443 alcanzable" 0 "§3: port-forward 80/443 en el TP-Link"; any_bad=1; }

  # 3. TLS: certificado válido y no caducado (Caddy auto-cert).
  if [ -n "$tls_days" ] && [ "$tls_days" -gt 0 ] 2>/dev/null; then
    report_step "TLS válido (${tls_days}d restantes)" 1 ""
  else
    report_step "TLS válido" 0 "§3: Caddy (idm-caddy) sirviendo el cert; podman logs idm-caddy"
    any_bad=1
  fi

  # 4. El gateway responde /api/v1/health por la URL pública (cadena completa).
  [ "$health_code" = "200" ] && report_step "gateway /api/v1/health (200)" 1 "" \
    || { report_step "gateway /api/v1/health" 0 "stack arriba: deploy/scripts/stack-up.sh; §3"; any_bad=1; }

  echo
  if [ "$any_bad" = "1" ]; then
    echo "  → Faltan pasos (ver ✗ arriba). El runbook (docs/FUNNEL_IDMMORTALITY_RUNBOOK.md) los detalla."
    return 1
  fi
  echo "  ✓ Funnel LIVE: $host sirve el gateway de Micelia por HTTPS."
  return 0
}

# --- recolección (I/O; no se unit-testea) ---------------------------------
_dns_ip()   { dig +short "$1" 2>/dev/null | grep -E '^[0-9]+\.' | head -1; }
_port_ok()  { nc -z -G 5 "$1" 443 >/dev/null 2>&1 && echo 1 || echo 0; }
_tls_days() {  # días hasta expiración del cert (vacío si no hay TLS)
  local host="$1" end secs
  end=$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  [ -z "$end" ] && return 0
  secs=$(( ( $(date -jf "%b %d %T %Y %Z" "$end" +%s 2>/dev/null || echo 0) - $(date +%s) ) ))
  [ "$secs" -gt 0 ] 2>/dev/null && echo $(( secs / 86400 )) || echo 0
}
_health()   { curl -sk -o /dev/null -w "%{http_code}" --max-time 8 "https://$1/api/v1/health" 2>/dev/null || echo 000; }

do_funnel_preflight() {
  evaluate_funnel "$HOST" "$(_dns_ip "$HOST")" "$(_port_ok "$HOST")" "$(_tls_days "$HOST")" "$(_health "$HOST")"
}

# Solo despachar al EJECUTAR (no al sourcear: los tests sourcean para ejercer evaluate_funnel).
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  do_funnel_preflight
fi
