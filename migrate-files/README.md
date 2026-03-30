# LanCache – Turnkey Full-Stack Setup

[![Build & Push](https://github.com/Bastika07/lancache/actions/workflows/build-and-push.yml/badge.svg)](https://github.com/Bastika07/lancache/actions/workflows/build-and-push.yml)

Gaming CDN-Cache fuer LAN-Partys und Heimnetzwerke – mit Prometheus/Grafana Monitoring.

Fork von [lancachenet/docker-compose](https://github.com/lancachenet/docker-compose).

---

## Schnellinstallation (One-Liner)

```bash
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

Das Script erledigt automatisch:
- Docker installieren (falls nicht vorhanden, Debian/Ubuntu/RHEL)
- Server-IP automatisch erkennen
- Sicheres Grafana-Passwort generieren
- Alle Images von GHCR pullen und Stack starten

---

## Manuelle Installation

```bash
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/.env -o .env
nano .env   # LANCACHE_IP, GRAFANA_PASSWORD setzen
docker compose pull
docker compose up -d
```

---

## Erreichbare Dienste

| Dienst        | URL                           | Zugangsdaten             |
|---------------|-------------------------------|--------------------------|
| Grafana       | http://HOST:3000              | admin / GRAFANA_PASSWORD |
| Prometheus    | http://localhost:9090         | -                        |
| Metriken      | http://localhost:9114/metrics | -                        |
| Web-Dashboard | http://HOST:8080              | -                        |

---

## Docker Images (GHCR)

Werden automatisch bei jedem Push auf `master` gebaut:

| Image | Beschreibung |
|---|---|
| `ghcr.io/bastika07/lancache-monitor:latest`    | Prometheus Log-Exporter |
| `ghcr.io/bastika07/lancache-prometheus:latest` | Prometheus + Konfiguration |
| `ghcr.io/bastika07/lancache-grafana:latest`    | Grafana + Dashboard |
| `ghcr.io/bastika07/lancache-web:latest`        | Nginx Web-Dashboard |

---

## Update

```bash
sudo bash /opt/lancache/update.sh
```

## Deinstallation

```bash
sudo bash /opt/lancache/uninstall.sh
```

---

## Konfiguration (.env)

| Variable          | Standard           | Beschreibung                  |
|-------------------|--------------------|-------------------------------|
| `LANCACHE_IP`     | –                  | IP des Cache-Servers          |
| `DNS_BIND_IP`     | –                  | IP fuer DNS-Bindung           |
| `CACHE_DISK_SIZE` | `500g`             | Maximale Cache-Groesse        |
| `CACHE_ROOT`      | `/opt/lancache/data` | Speicherpfad               |
| `GRAFANA_PASSWORD`| zufaellig generiert | Grafana Admin-Passwort       |
| `TZ`              | `Europe/Berlin`    | Zeitzone                      |

---

## Lizenz

MIT – Fork von [lancachenet/docker-compose](https://github.com/lancachenet/docker-compose)
