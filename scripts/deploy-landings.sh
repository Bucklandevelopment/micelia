#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Micelia Landing Pages Deploy Script
# Sube las landing pages a IONOS via SFTP
#
# Uso:
#   ./deploy-landings.sh              # Deploy manual (todos los archivos)
#   ./deploy-landings.sh --watch      # Watch mode (auto-deploy al guardar)
#   ./deploy-landings.sh --status     # Verificar conexión SFTP
#   ./deploy-landings.sh --dry-run    # Simular sin subir nada
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ─── CONFIG ──────────────────────────────────────────────────
# Carga credenciales desde .env.deploy si existe, si no usa variables de entorno
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env.deploy"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

# Estas variables deben estar configuradas en .env.deploy o como env vars
SFTP_HOST="${SFTP_HOST:?ERROR: SFTP_HOST no configurado. Crea .env.deploy o exporta la variable.}"
SFTP_USER="${SFTP_USER:?ERROR: SFTP_USER no configurado.}"
SFTP_PORT="${SFTP_PORT:-22}"
# SFTP_KEY_PATH es opcional (si usas autenticación por clave SSH)
SFTP_KEY_PATH="${SFTP_KEY_PATH:-}"

# Directorios locales y remotos
LOCAL_DIR="$PROJECT_ROOT/frontend/landing-pages"
REMOTE_BASE="${REMOTE_BASE:-/}"

# Mapeo: archivo local → directorio remoto
declare -A DEPLOY_MAP=(
    ["index.html"]="$REMOTE_BASE"
    ["blog.html"]="$REMOTE_BASE/blog"
    ["lab.html"]="$REMOTE_BASE/lab"
    ["playground.html"]="$REMOTE_BASE/playground"
)

# ─── COLORES ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

# ─── FUNCIONES ───────────────────────────────────────────────
log_info()  { echo -e "${CYAN}[IDM]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[IDM]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[IDM]${NC} $1"; }
log_error() { echo -e "${RED}[IDM]${NC} $1"; }
log_dim()   { echo -e "${DIM}[IDM]${NC} ${DIM}$1${NC}"; }

build_sftp_opts() {
    local opts="-oPort=$SFTP_PORT -oBatchMode=no -oStrictHostKeyChecking=accept-new"
    if [ -n "$SFTP_KEY_PATH" ]; then
        opts="$opts -oIdentityFile=$SFTP_KEY_PATH"
    fi
    echo "$opts"
}

check_dependencies() {
    local missing=()
    command -v sftp &>/dev/null || missing+=("sftp (openssh-client)")
    command -v sshpass &>/dev/null || true  # Opcional

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Dependencias faltantes: ${missing[*]}"
        log_info "Instala con: brew install ${missing[*]} (macOS) o apt install ${missing[*]} (Linux)"
        exit 1
    fi
}

verify_connection() {
    log_info "Verificando conexión SFTP a ${BOLD}$SFTP_HOST${NC}..."

    local sftp_opts
    sftp_opts=$(build_sftp_opts)

    if echo "ls" | sftp $sftp_opts "$SFTP_USER@$SFTP_HOST" &>/dev/null; then
        log_ok "Conexión exitosa"
        return 0
    else
        log_error "No se pudo conectar. Verifica credenciales en .env.deploy"
        return 1
    fi
}

upload_file() {
    local local_file="$1"
    local remote_dir="$2"
    local remote_name="${3:-index.html}"
    local dry_run="${4:-false}"

    local filename
    filename=$(basename "$local_file")
    local filesize
    filesize=$(wc -c < "$local_file" | tr -d ' ')
    local human_size
    human_size=$(numfmt --to=iec "$filesize" 2>/dev/null || echo "${filesize}B")

    if [ "$dry_run" = true ]; then
        log_dim "  DRY-RUN: $filename → $remote_dir/$remote_name ($human_size)"
        return 0
    fi

    log_info "  Subiendo ${BOLD}$filename${NC} → ${CYAN}$remote_dir/$remote_name${NC} ($human_size)"

    local sftp_opts
    sftp_opts=$(build_sftp_opts)

    # Crear directorio remoto si no existe y subir archivo
    sftp $sftp_opts "$SFTP_USER@$SFTP_HOST" <<SFTP_CMDS 2>/dev/null
-mkdir $remote_dir
cd $remote_dir
put $local_file $remote_name
SFTP_CMDS

    if [ $? -eq 0 ]; then
        log_ok "  ✓ $filename desplegado"
        return 0
    else
        log_error "  ✗ Error subiendo $filename"
        return 1
    fi
}

deploy_all() {
    local dry_run="${1:-false}"
    local start_time
    start_time=$(date +%s)

    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║     MICELIA — DEPLOY LANDING PAGES      ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    if [ "$dry_run" = true ]; then
        log_warn "MODO DRY-RUN: No se subirá nada"
        echo ""
    fi

    local success=0
    local failed=0

    for file in "${!DEPLOY_MAP[@]}"; do
        local local_path="$LOCAL_DIR/$file"
        local remote_dir="${DEPLOY_MAP[$file]}"

        if [ ! -f "$local_path" ]; then
            log_warn "  Archivo no encontrado: $file (saltando)"
            ((failed++))
            continue
        fi

        if upload_file "$local_path" "$remote_dir" "index.html" "$dry_run"; then
            ((success++))
        else
            ((failed++))
        fi
    done

    local end_time
    end_time=$(date +%s)
    local elapsed=$((end_time - start_time))

    echo ""
    echo -e "${DIM}──────────────────────────────────────────${NC}"
    log_ok "Deploy completado en ${elapsed}s: ${GREEN}$success OK${NC}, ${RED}$failed errores${NC}"
    echo -e "${DIM}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo ""
}

deploy_single() {
    local filepath="$1"
    local filename
    filename=$(basename "$filepath")

    if [[ -v "DEPLOY_MAP[$filename]" ]]; then
        local remote_dir="${DEPLOY_MAP[$filename]}"
        log_info "Cambio detectado: ${BOLD}$filename${NC}"
        upload_file "$filepath" "$remote_dir" "index.html" false
    else
        log_dim "Archivo $filename no está en el deploy map, ignorando"
    fi
}

watch_mode() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║     MICELIA — WATCH MODE ACTIVO         ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Vigilando cambios en: ${BOLD}$LOCAL_DIR${NC}"
    log_info "Presiona ${BOLD}Ctrl+C${NC} para detener"
    echo ""

    # Deploy inicial
    deploy_all false

    # Verificar si fswatch está disponible (macOS), si no usar polling
    if command -v fswatch &>/dev/null; then
        log_info "Usando fswatch para detectar cambios..."
        fswatch -0 -e ".*" -i "\\.html$" "$LOCAL_DIR" | while IFS= read -r -d '' filepath; do
            deploy_single "$filepath"
        done
    else
        log_warn "fswatch no encontrado. Usando polling cada 2s..."
        log_dim "Para mejor rendimiento: brew install fswatch (macOS) o apt install inotify-tools (Linux)"
        echo ""

        # Guardar checksums iniciales
        declare -A checksums
        for file in "${!DEPLOY_MAP[@]}"; do
            local fpath="$LOCAL_DIR/$file"
            if [ -f "$fpath" ]; then
                checksums["$file"]=$(md5sum "$fpath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$fpath" 2>/dev/null || echo "")
            fi
        done

        while true; do
            sleep 2
            for file in "${!DEPLOY_MAP[@]}"; do
                local fpath="$LOCAL_DIR/$file"
                if [ -f "$fpath" ]; then
                    local current_hash
                    current_hash=$(md5sum "$fpath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$fpath" 2>/dev/null || echo "")
                    if [ "${checksums[$file]:-}" != "$current_hash" ]; then
                        checksums["$file"]="$current_hash"
                        deploy_single "$fpath"
                    fi
                fi
            done
        done
    fi
}

show_help() {
    echo ""
    echo -e "${BOLD}Micelia Deploy Script${NC}"
    echo ""
    echo "Uso:"
    echo "  ./deploy-landings.sh              Deploy todos los archivos"
    echo "  ./deploy-landings.sh --watch      Watch mode (auto-deploy al guardar)"
    echo "  ./deploy-landings.sh --status     Verificar conexión SFTP"
    echo "  ./deploy-landings.sh --dry-run    Simular sin subir nada"
    echo "  ./deploy-landings.sh --help       Mostrar esta ayuda"
    echo ""
    echo "Configuración (.env.deploy):"
    echo "  SFTP_HOST=access123456789.webspace-data.io"
    echo "  SFTP_USER=u12345678"
    echo "  SFTP_PORT=22"
    echo "  SFTP_KEY_PATH=~/.ssh/ionos_key    # Opcional"
    echo "  REMOTE_BASE=/                       # Directorio raíz del webspace"
    echo ""
    echo "Archivos desplegados:"
    for file in "${!DEPLOY_MAP[@]}"; do
        echo "  $file → ${DEPLOY_MAP[$file]}/index.html"
    done
    echo ""
}

# ─── MAIN ────────────────────────────────────────────────────
check_dependencies

case "${1:-deploy}" in
    --watch|-w)
        verify_connection
        watch_mode
        ;;
    --status|-s)
        verify_connection
        ;;
    --dry-run|-d)
        deploy_all true
        ;;
    --help|-h)
        show_help
        ;;
    deploy|"")
        verify_connection
        deploy_all false
        ;;
    *)
        log_error "Opción desconocida: $1"
        show_help
        exit 1
        ;;
esac
