#!/bin/bash
# =============================================================================
# LanCache Update Script
# Aktualisiert alle Container auf die neuesten Images von GHCR.
# =============================================================================
set -euo pipefail

INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo -e "${BOLD}${CYAN}=== LanCache Update ===${RESET}"

if [[ ! -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
    echo "Fehler: ${INSTALL_DIR}/docker-compose.yml nicht gefunden."
    echo "Bitte zuerst install.sh ausfuehren."
    exit 1
fi

cd "${INSTALL_DIR}"

echo -e "${CYAN}[1/3]${RESET} Neueste Images pullen..."
docker compose pull

echo -e "${CYAN}[2/3]${RESET} Stack neu starten (zero-downtime rolling update)..."
docker compose up -d --remove-orphans

echo -e "${CYAN}[3/3]${RESET} Alte Images aufraumen..."
docker image prune -f

echo -e "${GREEN}Update abgeschlossen!${RESET}"
docker compose ps
