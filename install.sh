#!/bin/bash
# =============================================================================
# LanCache Turnkey Installer
# Quelle: https://github.com/Bastika07/lancache
#
# Verwendung:
#   curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | bash
#
# Optionen (Umgebungsvariablen vor dem Aufruf setzen):
#   LANCACHE_IP=10.0.0.1        Manuelle IP (sonst automatisch erkannt)
#   CACHE_ROOT=/opt/lancache    Installationspfad (Standard: /opt/lancache)
#   CACHE_DISK_SIZE=500g        Cache-Groesse (Standard: 500g)
#   GRAFANA_PASSWORD=secret     Grafana-Passwort (sonst zufaellig generiert)
# =============================================================================
set -euo pipefail

# ── Farben ───────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
log_section() { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════${RESET}"; echo -e "${BOLD}  $*${RESET}"; echo -e "${BOLD}${CYAN}══════════════════════════════════════${RESET}"; }

# ── Konfiguration ────────────────────────────────────────────────
REPO_RAW="https://raw.githubusercontent.com/Bastika07/lancache/master"
INSTALL_DIR="${CACHE_ROOT:-/opt/lancache}"
CACHE_DISK_SIZE="${CACHE_DISK_SIZE:-500g}"

# ── Root-Pruefung ────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    log_error "Dieses Script muss als root ausgefuehrt werden."
    log_error "Bitte mit 'sudo bash' oder als root ausfuehren."
    exit 1
fi

# ── Banner ───────────────────────────────────────────────────────
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

log_section "Schritt 1/6: Voraussetzungen pruefen"

# Docker pruefen / installieren
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    log_ok "Docker gefunden: v${DOCKER_VERSION}"
else
    log_warn "Docker nicht gefunden. Installiere Docker..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq ca-certificates curl gnupg
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable"             | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update -qq
        apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    elif command -v yum &>/dev/null; then
        yum install -y -q docker
        systemctl enable --now docker
    else
        log_error "Unbekannte Distribution. Bitte Docker manuell installieren: https://docs.docker.com/engine/install/"
        exit 1
    fi
    log_ok "Docker installiert."
fi

# Docker Compose pruefen
if docker compose version &>/dev/null; then
    log_ok "Docker Compose verfuegbar."
else
    log_error "Docker Compose (Plugin) nicht gefunden. Bitte aktuelles Docker installieren."
    exit 1
fi

# openssl fuer Passwort-Generierung
if ! command -v openssl &>/dev/null; then
    log_warn "openssl nicht gefunden – installiere..."
    apt-get install -y -qq openssl 2>/dev/null || yum install -y -q openssl 2>/dev/null || true
fi

log_section "Schritt 2/6: IP-Adresse ermitteln"

if [[ -n "${LANCACHE_IP:-}" ]]; then
    log_info "Verwende manuell gesetzte IP: ${LANCACHE_IP}"
else
    # Automatische IP-Erkennung (erste nicht-loopback IPv4)
    LANCACHE_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
    if [[ -z "$LANCACHE_IP" ]]; then
        LANCACHE_IP=$(hostname -I | awk '{print $1}')
    fi
    if [[ -z "$LANCACHE_IP" ]]; then
        log_error "Konnte IP-Adresse nicht automatisch ermitteln."
        log_error "Bitte manuell setzen: LANCACHE_IP=x.x.x.x bash install.sh"
        exit 1
    fi
    log_ok "IP automatisch erkannt: ${LANCACHE_IP}"
fi

log_section "Schritt 3/6: Installationsverzeichnis anlegen"

mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"
log_ok "Verzeichnis: ${INSTALL_DIR}"

log_section "Schritt 4/6: Konfigurationsdateien herunterladen"

curl -fsSL "${REPO_RAW}/docker-compose.yml" -o docker-compose.yml
log_ok "docker-compose.yml geladen"

# Zufaelliges Grafana-Passwort generieren falls nicht gesetzt
if [[ -z "${GRAFANA_PASSWORD:-}" ]]; then
    GRAFANA_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=')
    log_info "Grafana-Passwort zufaellig generiert."
fi

# .env schreiben
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

log_section "Schritt 5/6: Images pullen & Stack starten"

docker compose pull
docker compose up -d

log_section "Schritt 6/6: Dienste pruefen"

sleep 5

SERVICES=("dns" "monolithic" "log-monitor" "prometheus" "grafana" "web-stats")
ALL_OK=true
for svc in "${SERVICES[@]}"; do
    STATUS=$(docker compose ps --format json 2>/dev/null | python3 -c "
import sys, json
data = sys.stdin.read().strip()
for line in data.splitlines():
    try:
        obj = json.loads(line)
        if obj.get('Service') == '${svc}':
            print(obj.get('State','unknown'))
            break
    except: pass
" 2>/dev/null || echo "unknown")
    if [[ "$STATUS" == "running" ]]; then
        log_ok "${svc}: running"
    else
        log_warn "${svc}: ${STATUS}"
        ALL_OK=false
    fi
done

# ── Abschlusszusammenfassung ─────────────────────────────────────
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
echo -e "  ${BOLD}Cache-Daten:${RESET}      ${INSTALL_DIR}/data"
echo ""
echo -e "  ${BOLD}Update:${RESET}"
echo -e "    cd ${INSTALL_DIR} && docker compose pull && docker compose up -d"
echo ""

if [[ "$ALL_OK" == "false" ]]; then
    echo -e "${YELLOW}  Einige Dienste sind noch nicht bereit.${RESET}"
    echo -e "${YELLOW}  Bitte pruefen mit: docker compose -f ${INSTALL_DIR}/docker-compose.yml logs${RESET}"
    echo ""
fi

echo -e "${BOLD}${GREEN}════════════════════════════════════════${RESET}"
