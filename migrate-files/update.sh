#!/bin/bash
set -euo pipefail
INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"
CYAN='\033[0;36m'; GREEN='\033[0;32m'; BOLD='\033[1m'; RESET='\033[0m'

echo -e "${BOLD}${CYAN}=== LanCache Update ===${RESET}"
[[ ! -f "${INSTALL_DIR}/docker-compose.yml" ]] && echo "Fehler: Nicht installiert." && exit 1

cd "${INSTALL_DIR}"
echo -e "${CYAN}[1/3]${RESET} Neueste Images pullen..."
docker compose pull
echo -e "${CYAN}[2/3]${RESET} Stack neu starten..."
docker compose up -d --remove-orphans
echo -e "${CYAN}[3/3]${RESET} Alte Images aufraumen..."
docker image prune -f
echo -e "${GREEN}Update abgeschlossen.${RESET}"
docker compose ps
