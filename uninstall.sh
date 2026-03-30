#!/bin/bash
# =============================================================================
# LanCache Uninstaller
# Stoppt alle Container und entfernt die Installation.
# Cache-Daten bleiben standardmaessig erhalten.
# =============================================================================
set -euo pipefail

INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RESET='\033[0m'

echo -e "${RED}=== LanCache Deinstallation ===${RESET}"
echo ""
echo -e "${YELLOW}WARNUNG: Dies stoppt alle LanCache-Container und entfernt die Konfiguration.${RESET}"
echo -e "${YELLOW}Cache-Daten in ${INSTALL_DIR}/data bleiben ERHALTEN.${RESET}"
echo ""
read -rp "Fortfahren? [j/N] " confirm
if [[ "$confirm" != "j" && "$confirm" != "J" ]]; then
    echo "Abgebrochen."
    exit 0
fi

if [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
    cd "${INSTALL_DIR}"
    docker compose down -v
    echo -e "${GREEN}Container gestoppt und entfernt.${RESET}"
fi

# Volumes entfernen (Prometheus + Grafana Daten)
docker volume rm lancache-network 2>/dev/null || true

echo ""
read -rp "Auch Cache-Daten in ${INSTALL_DIR}/data loeschen? [j/N] " del_data
if [[ "$del_data" == "j" || "$del_data" == "J" ]]; then
    rm -rf "${INSTALL_DIR}/data"
    echo -e "${RED}Cache-Daten geloescht.${RESET}"
fi

echo -e "${GREEN}Deinstallation abgeschlossen.${RESET}"
