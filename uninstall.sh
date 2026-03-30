#!/bin/bash
set -euo pipefail
INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RESET='\033[0m'

echo -e "${RED}=== LanCache Deinstallation ===${RESET}"
echo -e "${YELLOW}WARNUNG: Stoppt alle Container. Cache-Daten bleiben erhalten.${RESET}"
read -rp "Fortfahren? [j/N] " c
[[ "$c" != "j" && "$c" != "J" ]] && echo "Abgebrochen." && exit 0

[[ -f "${INSTALL_DIR}/docker-compose.yml" ]] && cd "${INSTALL_DIR}" && docker compose down -v
echo -e "${GREEN}Container gestoppt.${RESET}"

read -rp "Cache-Daten in ${INSTALL_DIR}/data loeschen? [j/N] " d
[[ "$d" == "j" || "$d" == "J" ]] && rm -rf "${INSTALL_DIR}/data" && echo -e "${RED}Cache-Daten geloescht.${RESET}"
echo -e "${GREEN}Deinstallation abgeschlossen.${RESET}"
