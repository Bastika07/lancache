# LanCache – Turnkey Full-Stack Setup

[![Build & Push](https://github.com/Bastika07/lancache/actions/workflows/build-and-push.yml/badge.svg)](https://github.com/Bastika07/lancache/actions/workflows/build-and-push.yml)

Gaming CDN-Cache fuer LAN-Partys und Heimnetzwerke – mit vollstaendigem Monitoring.

Fork von [lancachenet/docker-compose](https://github.com/lancachenet/docker-compose).

---

## Schnellinstallation (One-Liner)

```bash
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

Das Script:
- Prueft und installiert Docker automatisch (Debian/Ubuntu/RHEL)
- Erkennt die Server-IP automatisch
- Generiert ein sicheres Grafana-Passwort
- Zieht alle Images von GHCR und startet den Stack

---

## Manuelle Installation

```bash
# 1. docker-compose.yml holen
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/docker-compose.yml -o docker-compose.yml

# 2. .env anpassen
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/.env -o .env
nano .env   # LANCACHE_IP, DNS_BIND_IP, GRAFANA_PASSWORD setzen

# 3. Starten (kein Build erforderlich – Images kommen von GHCR)
docker compose pull
docker compose up -d
```

---

## Erreichbare Dienste

| Dienst         | URL                           | Zugangsdaten             |
|----------------|-------------------------------|--------------------------|
| Grafana        | http://HOST:3000              | admin / GRAFANA_PASSWORD |
| Prometheus     | http://localhost:9090         | –                        |
| Metriken       | http://localhost:9114/metrics | –                        |
| Web-Dashboard  | http://HOST:8080              | –                        |

---

## Update

```bash
sudo bash /opt/lancache/update.sh
# oder manuell:
cd /opt/lancache && docker compose pull && docker compose up -d
```

---

## Docker Images (GHCR)

| Image | Beschreibung |
|---|---|
| `ghcr.io/bastika07/lancache-monitor:latest` | Prometheus Exporter (Log-Parser) |
| `ghcr.io/bastika07/lancache-prometheus:latest` | Prometheus mit eingebauter Konfiguration |
| `ghcr.io/bastika07/lancache-grafana:latest` | Grafana mit vorinstalliertem Dashboard |
| `ghcr.io/bastika07/lancache-web:latest` | Nginx Webdashboard |

Images werden automatisch bei jedem Commit auf `master` gebaut und gepusht.

---

## Konfiguration

Alle Einstellungen in `/opt/lancache/.env`:

| Variable | Standard | Beschreibung |
|---|---|---|
| `LANCACHE_IP` | – | IP des Cache-Servers (DNS-Ziel) |
| `DNS_BIND_IP` | – | IP fuer DNS-Bindung |
| `CACHE_DISK_SIZE` | `500g` | Maximale Cache-Groesse |
| `CACHE_ROOT` | `/opt/lancache/data` | Speicherpfad |
| `GRAFANA_PASSWORD` | zufaellig | Grafana Admin-Passwort |
| `TZ` | `Europe/Berlin` | Zeitzone |

---

## Deinstallation

```bash
sudo bash /opt/lancache/uninstall.sh
```

---

## Lizenz

MIT – Fork von [lancachenet/docker-compose](https://github.com/lancachenet/docker-compose)
