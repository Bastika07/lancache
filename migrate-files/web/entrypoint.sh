#!/bin/sh
set -e

LANCACHE_IP="${LANCACHE_IP:-127.0.0.1}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9114}"

echo "Generiere web_config.js fuer LANCACHE_IP=${LANCACHE_IP} ..."

cat > /usr/share/nginx/html/web_config.js << JSEOF
const CONFIG = {
  metricsUrl: 'http://${LANCACHE_IP}:${PROMETHEUS_PORT}/metrics',
  fallbackUrl: '/metrics',
  updateInterval: 10000,
  maxDataPoints: 50,
  lancacheIP: '${LANCACHE_IP}'
};
console.log('Dashboard configured for LanCache IP:', CONFIG.lancacheIP);
JSEOF

echo "web_config.js generiert."
exec nginx -g 'daemon off;'
