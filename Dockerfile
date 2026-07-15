# =============================================================================
# Micelia: Dockerfile
# =============================================================================

FROM python:3.11-slim

# Metadatos
LABEL maintainer="UTOP.IA Team"
LABEL description="Micelia — Orquestador central del ecosistema UTOP.IA"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (cache de Docker)
COPY pyproject.toml README.md ./

# Instalar dependencias Python
RUN pip install --upgrade pip && \
    pip install .

# Copiar código fuente
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY configs/ ./configs/

# Hacer ejecutable el entrypoint
RUN chmod +x scripts/entrypoint.sh

# Crear directorios necesarios
RUN mkdir -p /app/data /app/logs /app/models

# Puerto
EXPOSE 8888

# Health check.
# NOTA (DP-13, cerrada Ciclo 75): bajo podman/OCI —el runtime que usan TODOS los
# targets del Makefile— este HEALTHCHECK se IGNORA ("HEALTHCHECK is not supported for
# OCI image format and will be ignored", observado al construir la imagen en C73). La
# sonda LOAD-BEARING que gobierna `depends_on: condition: service_healthy` es la del
# servicio en docker-compose.yml (idéntica a esta), NO esta. Esta línea solo actuaría
# en un `podman/docker run` bare del contenedor, que el flujo del ecosistema no usa.
# Se mantiene por si se construye con `--format docker` o se corre bare; ambas sondas
# quedan pineadas en lockstep por tests/test_deploy_contract_codex.py.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/v1/health || exit 1

# Entrypoint: espera PostgreSQL, ejecuta migraciones, inicia uvicorn
ENTRYPOINT ["bash", "scripts/entrypoint.sh"]
