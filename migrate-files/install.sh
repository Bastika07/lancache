#!/bin/bash
# =============================================================================
# LanCache Turnkey Installer
# Verwendung:
#   curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
#
# Optionen (als Env-Variablen vor dem Aufruf):
#   LANCACHE_IP=10.0.0.1       Manuelle IP (sonst automatisch)
#   CACHE_ROOT=/opt/lancache   Installationspfad (Standard: /opt/lancache)
#   CACHE_DISK_SIZE=500g       Cache-Groesse
#   GRAFANA_PASSWORD=secret    Grafana-Passwort (sonst zufaellig)
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
log_section() {
    echo -e "\n${BOLD}${CYAN}══════════════════════════════════════${RESET}"
    echo -e "${BOLD}  $*${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════${RESET}"
}

REPO_RAW="https://raw.githubusercontent.com/Bastika07/lancache/master"
INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"
CACHE_DISK_SIZE="${CACHE_DISK_SIZE:-500g}"

[[ $EUID -ne 0 ]] && log_error "Bitte als root oder mit sudo ausfuehren."

echo -e "${BOLD}${GREEN}"
cat << 'BANNER'
  _                  ____           _
 | |    __ _ _ __  / ___|__ _  ___| |__   ___
 | |   / _` | '_ \| |   / _` |/ __| '_ \ / _ \
 | |__| (_| | | | | |__| (_| | (__| | | |  __/
 |_____\__,_|_| |_|\____\__,_|\___|_| |_|\___|
  Turnkey Installer
BANNER
echo -e "${RESET}"

log_section "1/6 Voraussetzungen pruefen"

if command -v docker &>/dev/null; then
    log_ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
else
    log_warn "Docker nicht gefunden – installiere..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq ca-certificates curl
        curl -fsSL https://get.docker.com | sh
    elif command -v yum &>/dev/null; then
        yum install -y -q docker && systemctl enable --now docker
    else
        log_error "Unbekannte Distribution. Docker manuell installieren: https://docs.docker.com/engine/install/"
    fi
    log_ok "Docker installiert."
fi

docker compose version &>/dev/null || log_error "Docker Compose Plugin nicht gefunden. Bitte aktuelles Docker installieren."
log_ok "Docker Compose verfuegbar"
command -v openssl &>/dev/null || (apt-get install -y -qq openssl 2>/dev/null || yum install -y -q openssl 2>/dev/null || true)

log_section "2/6 IP-Adresse ermitteln"

if [[ -z "${LANCACHE_IP:-}" ]]; then
    LANCACHE_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
    [[ -z "$LANCACHE_IP" ]] && LANCACHE_IP=$(hostname -I | awk '{print $1}')
    [[ -z "$LANCACHE_IP" ]] && log_error "IP nicht erkannt. Bitte manuell setzen: LANCACHE_IP=x.x.x.x bash install.sh"
    log_ok "IP automatisch erkannt: ${LANCACHE_IP}"
else
    log_info "Verwende gesetzte IP: ${LANCACHE_IP}"
fi

log_section "3/6 Installationsverzeichnis"

mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"
log_ok "Verzeichnis: ${INSTALL_DIR}"

log_section "4/6 Konfiguration herunterladen"

curl -fsSL "${REPO_RAW}/docker-compose.yml" -o docker-compose.yml
log_ok "docker-compose.yml geladen"

[[ -z "${GRAFANA_PASSWORD:-}" ]] && GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')

cat > .env << ENVEOF
USE_GENERIC_CACHE=true
LANCACHE_IP=${LANCACHE_IP}
DNS_BIND_IP=${LANCACHE_IP}
UPSTREAM_DNS=8.8.8.8
CACHE_ROOT=${INSTALL_DIR}/data
CACHE_DISK_SIZE=${CACHE_DISK_SIZE}
MIN_FREE_DISK=10g
CACHE_INDEX_SIZE=500m
CACHE_MAX_AGE=3650d
TZ=$(cat /etc/timezone 2>/dev/null || echo "Europe/Berlin")
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}
STATS_INTERVAL=30
PROMETHEUS_PORT=9114
LOG_RETENTION_DAYS=30
ENVEOF

log_ok ".env erstellt"

# Skripte fuer spaetere Verwaltung holen
curl -fsSL "${REPO_RAW}/update.sh"    -o update.sh    && chmod +x update.sh
curl -fsSL "${REPO_RAW}/uninstall.sh" -o uninstall.sh && chmod +x uninstall.sh
log_ok "update.sh und uninstall.sh geladen"

log_section "5/6 Images pullen und Stack starten"

docker compose pull
docker compose up -d

log_section "6/6 Dienste pruefen"

sleep 8
ALL_OK=true
for svc in dns monolithic log-monitor prometheus grafana web-stats; do
    STATUS=$(docker compose ps "$svc" --format "{{.State}}" 2>/dev/null || echo "unknown")
    if [[ "$STATUS" == "running" ]]; then
        log_ok "${svc}: running"
    else
        log_warn "${svc}: ${STATUS:-unknown}"
        ALL_OK=false
    fi
done

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo -e "${BOLD}  LanCache erfolgreich installiert!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Cache-Server IP:${RESET}  ${LANCACHE_IP}"
echo -e "  ${BOLD}DNS setzen auf:${RESET}   ${LANCACHE_IP}"
echo ""
echo -e "  ${BOLD}Grafana:${RESET}          http://${LANCACHE_IP}:3000"
echo -e "  ${BOLD}  Benutzer:${RESET}       admin"
echo -e "  ${BOLD}  Passwort:${RESET}       ${GRAFANA_PASSWORD}"
echo ""
echo -e "  ${BOLD}Prometheus:${RESET}       http://localhost:9090"
echo -e "  ${BOLD}Metriken:${RESET}         http://localhost:9114/metrics"
echo -e "  ${BOLD}Web-Dashboard:${RESET}    http://${LANCACHE_IP}:8080"
echo ""
echo -e "  ${BOLD}Konfiguration:${RESET}    ${INSTALL_DIR}/.env"
echo -e "  ${BOLD}Update:${RESET}           sudo bash ${INSTALL_DIR}/update.sh"
echo ""
[[ "$ALL_OK" == "false" ]] && echo -e "${YELLOW}  Einige Dienste noch nicht bereit. Pruefe: docker compose logs${RESET}\n"
echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
