#!/bin/bash
set -e

echo "🚀 LanCache Monitoring Setup wird gestartet..."

# Prüfe Voraussetzungen
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ist nicht installiert!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose ist nicht installiert!"
    exit 1
fi

# Prüfe ob .env existiert
if [ ! -f .env ]; then
    echo "⚠️  .env Datei nicht gefunden!"
    echo "📋 Kopiere .env.example zu .env:"
    cp .env.example .env
    echo "✅ .env Datei erstellt - bitte anpassen vor dem Start!"
fi

# Erstelle Monitoring-Verzeichnisse
echo "📁 Erstelle Monitoring-Verzeichnisse..."
mkdir -p monitoring/{prometheus/rules,grafana/provisioning/{datasources,dashboards},web}

# Kopiere Konfigurationsdateien
echo "📋 Kopiere Konfigurationsdateien..."

# Prometheus Konfiguration
cp prometheus.yml monitoring/prometheus/prometheus.yml

# Alert Rules
cp lancache_alert_rules.yml monitoring/prometheus/rules/

# Grafana Datasource
cp grafana_datasource.yml monitoring/grafana/provisioning/datasources/prometheus.yml

# Grafana Dashboard Provisioning Config
cat > monitoring/grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'LanCache'
    orgId: 1
    folder: 'LanCache'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Kopiere Grafana Dashboard
cp lancache_grafana_dashboard.json monitoring/grafana/provisioning/dashboards/

# Erstelle korrigierte Web-Stats Seite
cp web_index.html monitoring/web/index.html 

# Erstelle erweiterte CSS
cp web_style.css monitoring/web/style.css 

echo "📝 Generating config.js directly..."
source .env
cat > web_config.js << EOF
const CONFIG = {
    metricsUrl: '/metrics',
    fallbackUrl: 'http://$LANCACHE_IP:9114/metrics',
    updateInterval: 10000,
    maxDataPoints: 50,
    lancacheIP: '$LANCACHE_IP'
};

console.log('Dashboard configured for LanCache IP:', CONFIG.lancacheIP);
EOF

echo "✅ Config generated successfully!"

# 4. Validation
echo ""
echo "📋 VALIDATION:"
if [ -f web_config.js ]; then
    echo "✅ config.js exists"
    echo "Content:"
    cat web_config.js
    echo ""
    
    if grep -q "http://$LANCACHE_IP:9114" web_config.js; then
        echo "✅ IP correctly inserted: $LANCACHE_IP"
    else
        echo "❌ Something went wrong"
    fi
else
    echo "❌ config.js not generated"
fi
mv web_config.js monitoring/web/web_config.js

# Setze korrekte Berechtigungen
echo "🔐 Setze Berechtigungen..."
find monitoring/ -type f -exec chmod 644 {} \;
find monitoring/ -type d -exec chmod 755 {} \;
chmod +x lancache_monitor_docker.py

echo ""
echo "✅ LanCache Monitoring Setup abgeschlossen!"

# Teste Docker-Compose Konfiguration
echo "🧪 Teste Docker-Compose Konfiguration..."
if docker compose config > /dev/null 2>&1; then
    echo "✅ Docker-Compose Konfiguration ist gültig"
else
    echo "❌ Docker-Compose Konfiguration hat Fehler!"
    echo "💡 Führen Sie 'docker-compose config' aus für Details"
    exit 1
fi

echo ""
echo "🔧 Web-Stats API-Problem behoben:"
echo "• Direkter Aufruf von log-monitor:9114/metrics"
echo "• Keine nginx API-Routen mehr nötig"
echo "• Bessere Fehlerbehandlung und Status-Anzeige"
echo ""
echo "📋 Nächste Schritte:"
echo "1. Überprüfen Sie die .env Datei falls nötig"
echo "2. Starten Sie das System: docker-compose up -d"
echo "3. Warten Sie 1-2 Minuten bis alle Services bereit sind"
echo ""
echo "🌐 Services werden verfügbar sein:"
echo "• Grafana: http://localhost:3000 (admin/admin123)"
echo "• Prometheus: http://localhost:9090"
echo "• Web Stats: http://localhost:8080 (jetzt ohne API-Fehler!)"
echo "• Metriken: http://localhost:9114/metrics"
