#!/bin/bash
set -e

echo "🚀 LanCache Monitoring Setup wird gestartet..."

# Prüfe ob Docker und Docker Compose verfügbar sind
if ! command -v docker &> /dev/null; then
    echo "❌ Docker ist nicht installiert!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose ist nicht installiert!"
    exit 1
fi

# Erstelle Monitoring-Verzeichnisse
echo "📁 Erstelle Monitoring-Verzeichnisse..."
mkdir -p monitoring/{prometheus/rules,grafana/provisioning/{datasources,dashboards},web}

# Kopiere Konfigurationsdateien
echo "📋 Kopiere Konfigurationsdateien..."

# Prometheus Konfiguration
cp prometheus_updated.yml monitoring/prometheus/prometheus.yml

# Grafana Datasource
cp grafana_datasource.yml monitoring/grafana/provisioning/datasources/prometheus.yml

# Grafana Dashboard Provisioning
cat > monitoring/grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Kopiere Grafana Dashboard
cp lancache_grafana_dashboard.json monitoring/grafana/provisioning/dashboards/

# Erstelle einfache Web-Stats Seite
cat > monitoring/web/index.html << 'EOF'
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LanCache Quick Stats</title>
    <link rel="stylesheet" href="style.css">
    <script>
        function refreshStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('hit-rate').textContent = data.hit_rate + '%';
                    document.getElementById('total-requests').textContent = data.total_requests;
                    document.getElementById('cache-size').textContent = data.cache_size;
                })
                .catch(error => console.error('Error:', error));
        }
        
        setInterval(refreshStats, 30000); // Refresh every 30 seconds
        window.onload = refreshStats;
    </script>
</head>
<body>
    <div class="container">
        <h1>🎮 LanCache Quick Stats</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Cache Hit Rate</h3>
                <div class="stat-value" id="hit-rate">Loading...</div>
            </div>
            
            <div class="stat-card">
                <h3>Total Requests</h3>
                <div class="stat-value" id="total-requests">Loading...</div>
            </div>
            
            <div class="stat-card">
                <h3>Cache Size</h3>
                <div class="stat-value" id="cache-size">Loading...</div>
            </div>
        </div>
        
        <div class="links">
            <a href="http://localhost:3000" target="_blank">📊 Grafana Dashboard</a>
            <a href="http://localhost:9090" target="_blank">🔍 Prometheus</a>
            <a href="http://localhost:9114/metrics" target="_blank">📈 Raw Metrics</a>
        </div>
        
        <div class="footer">
            <p>LanCache Monitoring • Aktualisiert alle 30 Sekunden</p>
        </div>
    </div>
</body>
</html>
EOF

cat > monitoring/web/style.css << 'EOF'
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 40px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}

h1 {
    text-align: center;
    color: #333;
    margin-bottom: 40px;
    font-size: 2.5rem;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 30px;
    margin-bottom: 40px;
}

.stat-card {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 30px;
    border-radius: 15px;
    text-align: center;
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
    transition: transform 0.3s ease;
}

.stat-card:hover {
    transform: translateY(-5px);
}

.stat-card h3 {
    font-size: 1.2rem;
    margin-bottom: 15px;
    opacity: 0.9;
}

.stat-value {
    font-size: 2.5rem;
    font-weight: bold;
}

.links {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-bottom: 30px;
    flex-wrap: wrap;
}

.links a {
    padding: 12px 24px;
    background: #4CAF50;
    color: white;
    text-decoration: none;
    border-radius: 25px;
    transition: all 0.3s ease;
    font-weight: 500;
}

.links a:hover {
    background: #45a049;
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.footer {
    text-align: center;
    color: #666;
    font-size: 0.9rem;
}

@media (max-width: 768px) {
    .container {
        padding: 20px;
    }
    
    h1 {
        font-size: 2rem;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .links {
        flex-direction: column;
        align-items: center;
    }
}
EOF

# Setze Berechtigungen
echo "🔐 Setze Berechtigungen..."
chmod +x lancache_monitor_docker.py
chmod 755 monitoring/web/

# Erstelle Grafana Datenverzeichnis mit korrekten Berechtigungen
echo "📊 Bereite Grafana vor..."
mkdir -p grafana-data
sudo chown -R 472:472 grafana-data 2>/dev/null || echo "⚠️  Kann Grafana-Berechtigungen nicht setzen - läuft möglicherweise trotzdem"

echo ""
echo "✅ LanCache Monitoring Setup abgeschlossen!"
echo ""
echo "📋 Nächste Schritte:"
echo "1. Bearbeiten Sie die .env Datei mit Ihren Einstellungen"
echo "2. Starten Sie das System: docker-compose up -d"
echo "3. Warten Sie 2-3 Minuten bis alle Services bereit sind"
echo ""
echo "🌐 Zugriff auf die Services:"
echo "• Grafana Dashboard: http://localhost:3000"
echo "• Prometheus: http://localhost:9090"
echo "• Quick Stats: http://localhost:8080"
echo "• Raw Metrics: http://localhost:9114/metrics"
echo ""
echo "🔐 Standard-Anmeldung für Grafana:"
echo "• Benutzername: admin"
echo "• Passwort: siehe GRAFANA_PASSWORD in .env"
echo ""
echo "🔧 Fehlerbehebung:"
echo "• Logs anzeigen: docker-compose logs -f"
echo "• Services neustarten: docker-compose restart"
echo "• Vollständiger Neustart: docker-compose down && docker-compose up -d"
