# LanCache Monitoring - Dateiübersicht

Diese Sammlung enthält alle Dateien für ein vollständiges LanCache Monitoring-System.

## Hauptdateien (erforderlich):
1. **docker-compose.yml** - Erweiterte Docker-Compose Konfiguration
2. **.env.example** - Beispiel-Umgebungsvariablen (zu .env umbenennen)
3. **Dockerfile.monitor** - Docker-Image für Log-Monitoring
4. **lancache_monitor_docker.py** - Python-Script für Log-Analyse
5. **setup_monitoring.sh** - Automatisches Setup-Script

## Konfigurationsdateien:
6. **prometheus_updated.yml** - Prometheus Konfiguration
7. **grafana_datasource.yml** - Grafana Datenquelle
8. **lancache_grafana_dashboard.json** - Grafana Dashboard
9. **lancache_alert_rules.yml** - Prometheus Alert-Regeln

## Dokumentation:
10. **README.md** - Vollständige Installationsanleitung
11. **lancache_report.txt** - Beispiel-Report mit Statistiken

## Beispiele/Demo:
12. **lancache_monitor.py** - Standalone Monitoring-Script
13. **lancache_dashboard.png** - Screenshot des Dashboards
14. **docker-compose-extended.yml** - Alternative Docker-Compose
15. **docker-compose-monitoring.yml** - Nur Monitoring-Services

## Installation (Kurzfassung):
```bash
# 1. Alle Dateien in LanCache-Verzeichnis kopieren
# 2. .env.example zu .env umbenennen und anpassen
# 3. Setup ausführen:
chmod +x setup_monitoring.sh
./setup_monitoring.sh

# 4. System starten:
docker-compose up -d

# 5. Zugriff:
# - Grafana: http://localhost:3000 (admin/admin123)
# - Prometheus: http://localhost:9090
# - Quick Stats: http://localhost:8080
```

## Fehlerbehebung:
- Alle Logs: `docker-compose logs -f`
- Einzelne Services: `docker-compose logs <service-name>`
- Neustart: `docker-compose restart`
- Kompletter Neustart: `docker-compose down && docker-compose up -d`

## Support:
Prüfen Sie die README.md für detaillierte Installationsanweisungen und Fehlerbehebung.
