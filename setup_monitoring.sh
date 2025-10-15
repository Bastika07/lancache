#!/bin/bash
set -e

echo "🚀 Setting up LanCache Monitoring..."

# Create monitoring directories
mkdir -p monitoring/{prometheus,grafana/{dashboards,datasources},web}

echo "📁 Created monitoring directories"

# Set permissions
chmod +x monitoring/lancache_monitor.py
chmod +x setup_monitoring.sh

echo "✅ LanCache Monitoring Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Copy your .env file and adjust CACHE_ROOT path"
echo "2. Run: docker-compose up -d"
echo "3. Access Grafana at http://localhost:3000 (admin/admin123)"
echo "4. Access Prometheus at http://localhost:9090"
echo "5. View basic stats at http://localhost:8080"
echo ""
echo "Monitoring endpoints:"
echo "- Prometheus Metrics: http://localhost:9114/metrics"
echo "- Health Check: http://localhost:9114/health"
