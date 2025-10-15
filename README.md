# LanCache Monitoring Setup

Diese Dateien erweitern Ihr bestehendes lancachenet Setup um umfassendes Monitoring.

## Installation

1. **Backup Ihrer aktuellen Dateien:**
   ```bash
   cp docker-compose.yml docker-compose.yml.backup
   cp .env .env.backup
   ```

2. **Neue Dateien kopieren:**
   ```bash
   # Ersetzen Sie Ihre docker-compose.yml
   cp docker-compose-extended.yml docker-compose.yml
   
   # Passen Sie Ihre .env an (oder verwenden Sie .env.example als Basis)
   ```

3. **Monitoring-Verzeichnisse erstellen:**
   ```bash
   chmod +x setup_monitoring.sh
   ./setup_monitoring.sh
   ```

4. **Konfiguration anpassen:**
   - Bearbeiten Sie `.env` und setzen Sie Ihre IP-Adressen
   - Passen Sie `CACHE_ROOT` an Ihren gewünschten Speicherort an
   - Setzen Sie `CACHE_DISK_SIZE` entsprechend Ihrem verfügbaren Speicher

5. **System starten:**
   ```bash
   docker-compose up -d
   ```

## Zugriff auf Monitoring

- **Grafana Dashboard:** http://localhost:3000
  - Benutzername: `admin`
  - Passwort: Wert aus `GRAFANA_PASSWORD` in `.env`

- **Prometheus:** http://localhost:9090

- **Raw Metriken:** http://localhost:9114/metrics

- **Einfache Stats:** http://localhost:8080

## Konfiguration der .env Datei

### Erforderliche Einstellungen:
- `LANCACHE_IP`: IP-Adresse Ihres Cache-Servers
- `DNS_BIND_IP`: IP für DNS (normalerweise gleich LANCACHE_IP)
- `CACHE_ROOT`: Pfad für Cache-Daten (z.B. `/opt/lancache`)
- `CACHE_DISK_SIZE`: Max. Festplattenspeicher (z.B. `500g`)

### Optionale Einstellungen:
- `UPSTREAM_DNS`: DNS-Server für nicht-gecachte Domains
- `CACHE_MAX_AGE`: Wie lange Cache-Daten aufbewahrt werden
- `TZ`: Zeitzone für Log-Timestamps

## Monitoring Features

### Cache-Statistiken:
- Hit Rate (Prozent der aus dem Cache bedienten Anfragen)
- Bandbreiten-Einsparung
- Traffic pro CDN (Steam, Epic, Blizzard, etc.)
- Response-Zeit Vergleiche

### CDN-Unterstützung:
Das System erkennt automatisch Traffic von:
- Steam (alle Steam-Dienste)
- Epic Games Store
- Battle.net (Blizzard)
- Origin (EA)
- Uplay (Ubisoft)
- Windows Updates
- Riot Games
- GOG Galaxy
- Twitch

### Alerts und Benachrichtigungen:
- Niedrige Hit Rate Warnungen
- Festplattenspeicher-Monitoring
- Service-Verfügbarkeit

## Fehlerbehebung

### Container starten nicht:
```bash
# Logs prüfen
docker-compose logs -f

# Einzelne Services prüfen
docker-compose logs lancache
docker-compose logs log-monitor
```

### Monitoring-Daten fehlen:
```bash
# Prüfen ob Log-Datei existiert
ls -la ${CACHE_ROOT}/logs/access.log

# Monitoring-Script Status
docker-compose exec log-monitor ps aux
```

### Grafana Dashboard ist leer:
1. Prüfen Sie ob Prometheus läuft: http://localhost:9090
2. Prüfen Sie ob Metriken verfügbar sind: http://localhost:9114/metrics
3. Warten Sie einige Minuten für erste Daten

## Performance-Optimierung

### Für hohen Traffic:
- Erhöhen Sie `CACHE_INDEX_SIZE` (mehr RAM für Cache-Index)
- Verwenden Sie SSD-Speicher für `CACHE_ROOT`
- Monitoren Sie Festplatten-I/O in Grafana

### Für niedrigen Speicher:
- Reduzieren Sie `CACHE_DISK_SIZE`
- Verkürzen Sie `CACHE_MAX_AGE`
- Reduzieren Sie `CACHE_INDEX_SIZE`

## Wartung

### Regelmäßige Aufgaben:
```bash
# Container aktualisieren
docker-compose pull
docker-compose up -d

# Logs rotieren (automatisch durch Docker)
docker system prune -f

# Cache-Statistiken exportieren
docker-compose exec log-monitor python -c "import json; print(json.dumps(metrics.metrics, indent=2))"
```

### Backup:
```bash
# Konfiguration sichern
tar -czf lancache-config-$(date +%Y%m%d).tar.gz .env docker-compose.yml monitoring/

# Cache-Daten sind im CACHE_ROOT Verzeichnis
```
