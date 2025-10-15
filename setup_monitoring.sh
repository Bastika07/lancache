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
cp prometheus_updated.yml monitoring/prometheus/prometheus.yml

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

# Erstelle Web-Stats Seite mit CORS-Support
cat > monitoring/web/index.html << 'EOF'
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LanCache Quick Stats</title>
    <link rel="stylesheet" href="style.css">
    <script>
        async function refreshStats() {
            try {
                // Verwende lokale Prometheus API
                const response = await fetch('/api/prometheus', {
                    method: 'GET',
                    headers: {
                        'Accept': 'text/plain'
                    }
                });
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                
                const text = await response.text();
                
                // Parse Prometheus metrics
                const hitRate = text.match(/lancache_hit_rate ([0-9.]+)/);
                const totalRequests = text.match(/lancache_requests_total ([0-9]+)/);
                const totalBytes = text.match(/lancache_bytes_total ([0-9]+)/);
                
                if (hitRate) {
                    document.getElementById('hit-rate').textContent = 
                        (parseFloat(hitRate[1]) * 100).toFixed(1) + '%';
                } else {
                    document.getElementById('hit-rate').textContent = '0.0%';
                }
                
                if (totalRequests) {
                    document.getElementById('total-requests').textContent = 
                        parseInt(totalRequests[1]).toLocaleString();
                } else {
                    document.getElementById('total-requests').textContent = '0';
                }
                
                if (totalBytes) {
                    const gb = parseInt(totalBytes[1]) / (1024 * 1024 * 1024);
                    document.getElementById('cache-size').textContent = 
                        gb.toFixed(2) + ' GB';
                } else {
                    document.getElementById('cache-size').textContent = '0.00 GB';
                }
                
                document.getElementById('last-update').textContent = 
                    new Date().toLocaleTimeString();
                    
            } catch (error) {
                console.error('Error fetching stats:', error);
                document.getElementById('hit-rate').textContent = 'N/A';
                document.getElementById('total-requests').textContent = 'N/A';
                document.getElementById('cache-size').textContent = 'N/A';
                document.getElementById('last-update').textContent = 'Error';
            }
        }
        
        // Initial load und dann alle 30 Sekunden
        window.onload = function() {
            refreshStats();
            setInterval(refreshStats, 30000);
        };
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
            <p>LanCache Monitoring • Letzte Aktualisierung: <span id="last-update">-</span></p>
        </div>
    </div>
</body>
</html>
EOF

# CSS Datei (unverändert aber sicherheitshalber)
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

# Setze korrekte Berechtigungen
echo "🔐 Setze Berechtigungen..."
find monitoring/ -type f -exec chmod 644 {} \;
find monitoring/ -type d -exec chmod 755 {} \;
chmod +x lancache_monitor_docker.py

echo ""
echo "✅ LanCache Monitoring Setup abgeschlossen!"

# Teste Docker-Compose Konfiguration
echo "🧪 Teste Docker-Compose Konfiguration..."
if docker-compose config > /dev/null 2>&1; then
    echo "✅ Docker-Compose Konfiguration ist gültig"
else
    echo "❌ Docker-Compose Konfiguration hat Fehler!"
    echo "💡 Führen Sie 'docker-compose config' aus für Details"
    exit 1
fi

echo ""
echo "📋 Nächste Schritte:"
echo "1. Überprüfen Sie die .env Datei:"
echo "   nano .env"
echo ""
echo "2. Starten Sie das System:"
echo "   docker-compose up -d"
echo ""
echo "3. Überwachen Sie die Logs:"
echo "   docker-compose logs -f"
echo ""
echo "🌐 Services werden verfügbar sein unter:"
echo "• Grafana: http://localhost:3000 (admin/admin123)"
echo "• Prometheus: http://localhost:9090"
echo "• Quick Stats: http://localhost:8080"
echo "• Metriken: http://localhost:9114/metrics"
