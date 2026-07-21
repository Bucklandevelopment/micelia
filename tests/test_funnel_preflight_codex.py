"""
C115 — scaffolding del deploy del funnel: `scripts/funnel-preflight.sh`.

DP-1..DP-4 (hosting/subdominios/secretos/postgres del funnel) ya están DECIDIDAS por Jessicache;
lo que queda son pasos de PANEL humanos (A-record IONOS, port-forward TP-Link, pmset) + su
verificación, que el runbook lista suelta (dig/curl/openssl). `funnel-preflight.sh` los agrupa en
un comando read-only que, tras los pasos humanos, dice por cada eslabón (DNS/puerto/TLS/health)
si está OK y qué sección del runbook mirar si no.

No se puede LIVE-verificar todavía (el A-record aún no apunta a casa — es paso humano). Lo que sí
se pinea es el **núcleo PURO de decisión** `evaluate_funnel HOST DNS_IP PORT_OK TLS_DAYS HEALTH`,
separado de la recolección I/O (dig/nc/openssl/curl no se unit-testean): se le inyectan valores
controlados y se comprueba el ✓/✗ y el exit-code por eslabón. Hermético (sin red), patrón del
doctor de venvs (C97).
"""

import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "funnel-preflight.sh"


def _eval(dns_ip, port_ok, tls_days, health):
    """Sourcea el script (sin disparar el dispatch) y corre evaluate_funnel con valores dados."""
    snippet = (
        f'source "{_SCRIPT}"\n'
        f'evaluate_funnel host "{dns_ip}" "{port_ok}" "{tls_days}" "{health}"; echo "rc=$?"'
    )
    return subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, timeout=15)


def test_all_links_ok_exits_zero():
    r = _eval("1.2.3.4", 1, 90, 200)
    out = r.stdout + r.stderr
    assert out.count("✓") == 5  # 4 pasos + el resumen final
    assert "rc=0" in out and "Funnel LIVE" in out


def test_missing_dns_flags_a_record_step():
    r = _eval("", 1, 90, 200)
    out = r.stdout + r.stderr
    assert "✗ DNS" in out and "A-record" in out and "rc=1" in out


def test_port_closed_flags_port_forward():
    r = _eval("1.2.3.4", 0, 90, 200)
    out = r.stdout + r.stderr
    assert ":443 alcanzable" in out and "port-forward" in out and "rc=1" in out


def test_no_tls_flags_caddy():
    r = _eval("1.2.3.4", 1, "", 200)
    out = r.stdout + r.stderr
    assert "✗ TLS" in out and "Caddy" in out and "rc=1" in out


def test_expired_tls_days_zero_is_invalid():
    """Un cert con 0 días (caducado) cuenta como inválido, no OK."""
    r = _eval("1.2.3.4", 1, 0, 200)
    out = r.stdout + r.stderr
    assert "✗ TLS" in out and "rc=1" in out


def test_health_non_200_flags_stack():
    r = _eval("1.2.3.4", 1, 90, 503)
    out = r.stdout + r.stderr
    assert "gateway /api/v1/health" in out and "stack" in out and "rc=1" in out


def test_partial_one_bad_still_exits_1():
    """Con 3 eslabones OK y 1 mal (health), el exit sigue siendo 1 (any_bad)."""
    r = _eval("1.2.3.4", 1, 90, 000)
    out = r.stdout + r.stderr
    assert "rc=1" in out
    assert out.count("✓") == 3  # DNS + puerto + TLS OK; health y resumen no


def test_script_is_readonly_no_state_mutation():
    """Guardarraíl: el script NO cambia estado — solo consultas (dig +short, nc -z, openssl
    s_client, curl GET). Se buscan VERBOS mutantes reales; se ignora el texto de las pistas
    (p.ej. 'podman logs' como consejo es read-only)."""
    text = _SCRIPT.read_text(encoding="utf-8")
    mutating = (
        "curl -X POST", "curl -X PUT", "curl -X DELETE", "--request POST",
        "rm -", "kill -", "podman rm", "podman stop", "podman start",
        "podman restart", "pkill", "dig +update",
    )
    for verb in mutating:
        assert verb not in text, f"funnel-preflight no debe mutar estado: contiene {verb!r}"
