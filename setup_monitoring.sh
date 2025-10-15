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

# Erstelle korrigierte Web-Stats Seite
cat > monitoring/web/index.html << 'HTML_END'
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
                // Direkte Anfrage an den log-monitor Service (Port 9114)
                const metricsUrl = window.location.protocol + '//' + window.location.hostname + ':9114/metrics';
                
                const response = await fetch(metricsUrl, {
                    method: 'GET',
                    mode: 'cors',
                    headers: {
                        'Accept': 'text/plain'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const text = await response.text();
                console.log('Received metrics:', text.substring(0, 200) + '...');
                
                // Parse Prometheus metrics
                const hitRateMatch = text.match(/lancache_hit_rate ([0-9.]+)/);
                const totalRequestsMatch = text.match(/lancache_requests_total ([0-9]+)/);
                const totalBytesMatch = text.match(/lancache_bytes_total ([0-9]+)/);
                
                // Update Hit Rate
                if (hitRateMatch) {
                    const hitRate = (parseFloat(hitRateMatch[1]) * 100).toFixed(1);
                    document.getElementById('hit-rate').textContent = hitRate + '%';
                    document.getElementById('hit-rate').className = 'stat-value';
                } else {
                    document.getElementById('hit-rate').textContent = 'N/A';
                    document.getElementById('hit-rate').className = 'stat-value error';
                }
                
                // Update Total Requests
                if (totalRequestsMatch) {
                    const requests = parseInt(totalRequestsMatch[1]).toLocaleString();
                    document.getElementById('total-requests').textContent = requests;
                    document.getElementById('total-requests').className = 'stat-value';
                } else {
                    document.getElementById('total-requests').textContent = 'N/A';
                    document.getElementById('total-requests').className = 'stat-value error';
                }
                
                // Update Cache Size
                if (totalBytesMatch) {
                    const bytes = parseInt(totalBytesMatch[1]);
                    const gb = bytes / (1024 * 1024 * 1024);
                    document.getElementById('cache-size').textContent = gb.toFixed(2) + ' GB';
                    document.getElementById('cache-size').className = 'stat-value';
                } else {
                    document.getElementById('cache-size').textContent = 'N/A';
                    document.getElementById('cache-size').className = 'stat-value error';
                }
                
                // Update timestamp
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                document.getElementById('connection-status').textContent = 'Connected';
                document.getElementById('connection-status').className = 'status connected';
                
            } catch (error) {
                console.error('Error fetching stats:', error);
                
                // Show error state
                document.getElementById('hit-rate').textContent = 'Error';
                document.getElementById('hit-rate').className = 'stat-value error';
                document.getElementById('total-requests').textContent = 'Error';
                document.getElementById('total-requests').className = 'stat-value error';
                document.getElementById('cache-size').textContent = 'Error';  
                document.getElementById('cache-size').className = 'stat-value error';
                document.getElementById('last-update').textContent = 'Connection failed';
                document.getElementById('connection-status').textContent = 'Disconnected';
                document.getElementById('connection-status').className = 'status disconnected';
            }
        }
        
        // Auto-refresh every 30 seconds
        window.onload = function() {
            refreshStats(); // Initial load
            setInterval(refreshStats, 30000);
        };
        
        // Manual refresh button
        function manualRefresh() {
            refreshStats();
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 LanCache Quick Stats</h1>
            <div class="status-bar">
                <span class="status-label">Status: </span>
                <span id="connection-status" class="status">Connecting...</span>
                <button onclick="manualRefresh()" class="refresh-btn">🔄 Refresh</button>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Cache Hit Rate</h3>
                <div class="stat-value" id="hit-rate">Loading...</div>
                <div class="stat-description">Percentage of requests served from cache</div>
            </div>
            
            <div class="stat-card">
                <h3>Total Requests</h3>
                <div class="stat-value" id="total-requests">Loading...</div>
                <div class="stat-description">All requests processed by cache</div>
            </div>
            
            <div class="stat-card">
                <h3>Cache Size</h3>
                <div class="stat-value" id="cache-size">Loading...</div>
                <div class="stat-description">Total data cached</div>
            </div>
        </div>
        
        <div class="links">
            <a href="http://${window.location.hostname}:3000" target="_blank">📊 Grafana Dashboard</a>
            <a href="http://${window.location.hostname}:9090" target="_blank">🔍 Prometheus</a>
            <a href="http://${window.location.hostname}:9114/metrics" target="_blank">📈 Raw Metrics</a>
        </div>
        
        <div class="footer">
            <p>LanCache Monitoring • Last Update: <span id="last-update">-</span></p>
            <p class="debug-info">Metrics URL: <span id="metrics-url">-</span></p>
        </div>
    </div>
    
    <script>
        // Show the metrics URL for debugging
        document.getElementById('metrics-url').textContent = 
            window.location.protocol + '//' + window.location.hostname + ':9114/metrics';
    </script>
</body>
</html>
HTML_END

# Erstelle erweiterte CSS
cat > monitoring/web/style.css << 'CSS_END'
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

.header {
    text-align: center;
    margin-bottom: 40px;
}

h1 {
    color: #333;
    font-size: 2.5rem;
    margin-bottom: 20px;
}

.status-bar {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 15px;
    margin-bottom: 20px;
}

.status-label {
    font-weight: 600;
    color: #666;
}

.status {
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
}

.status.connected {
    background: #4CAF50;
    color: white;
}

.status.disconnected {
    background: #f44336;
    color: white;
}

.refresh-btn {
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.3s ease;
}

.refresh-btn:hover {
    background: #1976D2;
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
    margin-bottom: 10px;
}

.stat-value.error {
    color: #ffcdd2;
    font-size: 1.8rem;
}

.stat-description {
    font-size: 0.9rem;
    opacity: 0.8;
    line-height: 1.4;
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

.debug-info {
    margin-top: 10px;
    font-size: 0.8rem;
    color: #999;
    font-family: monospace;
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
    
    .status-bar {
        flex-direction: column;
        gap: 10px;
    }
}
CSS_END

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
