#!/bin/bash
# One-liner migration from Docker Desktop/Colima to Podman for Micelia

echo "🚀 Iniciando migración a Podman..." && \
brew uninstall colima docker docker-compose --force && \
echo "✓ Vieja config removida" && \
brew install podman podman-compose && \
echo "✓ Podman instalado" && \
podman machine init && \
podman machine start && \
echo "✓ Máquina Podman iniciada" && \
sleep 5 && \
podman ps && \
podman-compose version && \
echo "✓ Podman verificado" && \
cd "$(dirname "$0")" && \
make docker-infra && \
echo "✓ Infra de Micelia arriba con Podman"
