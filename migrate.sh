#!/bin/bash
# =============================================================================
# LanCache Repo Migration Script
# Fuehre dieses Script im Root deines geklonten Repos aus:
#   git clone https://github.com/Bastika07/lancache.git
#   cd lancache
#   bash migrate.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
log_section() { echo -e "\n${BOLD}${CYAN}──────────────────────────────────────${RESET}"; echo -e "${BOLD}  $*${RESET}"; echo -e "${BOLD}${CYAN}──────────────────────────────────────${RESET}"; }

# Sicherstellen dass wir im richtigen Verzeichnis sind
if [[ ! -f "docker-compose.yml" ]]; then
    log_error "docker-compose.yml nicht gefunden. Bitte im Repo-Root ausfuehren."
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_section "Schritt 1/5: Verzeichnisstruktur anlegen"

mkdir -p monitor
mkdir -p prometheus/rules
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards
mkdir -p web
mkdir -p .github/workflows

log_ok "Verzeichnisse angelegt"

log_section "Schritt 2/5: Bestehende Dateien verschieben"

# monitor/
if [[ -f "Dockerfile.monitor" ]]; then
    cp Dockerfile.monitor monitor/Dockerfile
    log_ok "Dockerfile.monitor  →  monitor/Dockerfile"
fi
if [[ -f "lancache_monitor_docker.py" ]]; then
    cp lancache_monitor_docker.py monitor/lancache_monitor_docker.py
    log_ok "lancache_monitor_docker.py  →  monitor/"
fi

# prometheus/
if [[ -f "prometheus.yml" ]]; then
    cp prometheus.yml prometheus/prometheus.yml
    log_ok "prometheus.yml  →  prometheus/"
fi
if [[ -f "lancache_alert_rules.yml" ]]; then
    cp lancache_alert_rules.yml prometheus/rules/lancache_alert_rules.yml
    log_ok "lancache_alert_rules.yml  →  prometheus/rules/"
fi

# grafana/
if [[ -f "grafana_datasource.yml" ]]; then
    cp grafana_datasource.yml grafana/provisioning/datasources/prometheus.yml
    log_ok "grafana_datasource.yml  →  grafana/provisioning/datasources/prometheus.yml"
fi
if [[ -f "lancache_grafana_dashboard.json" ]]; then
    cp lancache_grafana_dashboard.json grafana/provisioning/dashboards/lancache_grafana_dashboard.json
    log_ok "lancache_grafana_dashboard.json  →  grafana/provisioning/dashboards/"
fi

# web/
if [[ -f "web_index.html" ]]; then
    cp web_index.html web/index.html
    log_ok "web_index.html  →  web/index.html"
fi
if [[ -f "web_style.css" ]]; then
    cp web_style.css web/style.css
    log_ok "web_style.css  →  web/style.css"
fi

log_section "Schritt 3/5: Neue Dateien aus migrate-files/ einspielen"

MIGRATE_DIR="$(dirname "$0")/migrate-files"
if [[ ! -d "$MIGRATE_DIR" ]]; then
    log_error "migrate-files/ Verzeichnis nicht gefunden. Bitte das komplette ZIP entpacken."
fi

# Dockerfiles
cp "$MIGRATE_DIR/monitor/Dockerfile.new"          monitor/Dockerfile
cp "$MIGRATE_DIR/prometheus/Dockerfile"           prometheus/Dockerfile
cp "$MIGRATE_DIR/grafana/Dockerfile"              grafana/Dockerfile
cp "$MIGRATE_DIR/web/Dockerfile"                  web/Dockerfile
cp "$MIGRATE_DIR/web/entrypoint.sh"               web/entrypoint.sh
cp "$MIGRATE_DIR/web/nginx.conf"                  web/nginx.conf
chmod +x web/entrypoint.sh

# Grafana Dashboard Provisioning
cp "$MIGRATE_DIR/grafana/provisioning/dashboards/dashboard.yml" \
   grafana/provisioning/dashboards/dashboard.yml

# GitHub Actions Workflows
cp "$MIGRATE_DIR/.github/workflows/build-and-push.yml" .github/workflows/build-and-push.yml
cp "$MIGRATE_DIR/.github/workflows/release.yml"        .github/workflows/release.yml

# Root Scripts
cp "$MIGRATE_DIR/install.sh"     install.sh
cp "$MIGRATE_DIR/update.sh"      update.sh
cp "$MIGRATE_DIR/uninstall.sh"   uninstall.sh
cp "$MIGRATE_DIR/.gitignore"     .gitignore
cp "$MIGRATE_DIR/README.md"      README.md
chmod +x install.sh update.sh uninstall.sh

log_ok "Alle neuen Dateien eingespielt"

log_section "Schritt 4/5: Strukturpruefung"

MISSING=0
REQUIRED=(
    "monitor/Dockerfile"
    "monitor/lancache_monitor_docker.py"
    "prometheus/Dockerfile"
    "prometheus/prometheus.yml"
    "prometheus/rules/lancache_alert_rules.yml"
    "grafana/Dockerfile"
    "grafana/provisioning/datasources/prometheus.yml"
    "grafana/provisioning/dashboards/dashboard.yml"
    "grafana/provisioning/dashboards/lancache_grafana_dashboard.json"
    "web/Dockerfile"
    "web/entrypoint.sh"
    "web/nginx.conf"
    "web/index.html"
    "web/style.css"
    "docker-compose.yml"
    "install.sh"
    "update.sh"
    "uninstall.sh"
    ".github/workflows/build-and-push.yml"
    ".github/workflows/release.yml"
)

for f in "${REQUIRED[@]}"; do
    if [[ -f "$f" ]]; then
        log_ok "$f"
    else
        echo -e "${RED}[FEHLT]${RESET} $f"
        MISSING=$((MISSING + 1))
    fi
done

if [[ $MISSING -gt 0 ]]; then
    echo ""
    log_error "$MISSING Datei(en) fehlen. Migration unvollstaendig."
fi

log_section "Schritt 5/5: Git Commit vorbereiten"

echo ""
echo -e "${BOLD}Alle Dateien sind vorhanden. Bereit zum Committen.${RESET}"
echo ""
echo "Fuehre jetzt aus:"
echo ""
echo -e "  ${CYAN}git add .${RESET}"
echo -e "  ${CYAN}git commit -m \"refactor: restructure into subdirectories with CI/CD and turnkey installer\"${RESET}"
echo -e "  ${CYAN}git push origin master${RESET}"
echo ""
echo -e "${YELLOW}Danach startet GitHub Actions automatisch und baut alle 4 Images.${RESET}"
echo ""
echo -e "${BOLD}Anschliessend Package-Sichtbarkeit auf Public setzen:${RESET}"
echo "  GitHub → Packages → lancache-* → Package Settings → Change visibility → Public"
echo ""
