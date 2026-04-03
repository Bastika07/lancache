# 🎮 LanCache – Turnkey Full-Stack

Ein vollständiger, selbst gehosteter Game-Cache für LAN-Partys und Heimnetzwerke.  
Alle Images werden automatisch via GitHub Actions gebaut und über GHCR bereitgestellt – kein lokaler Build nötig.

---

## 📁 Projektstruktur

```
lancache/
├── docker-compose.yml              # Stack-Definition (nur GHCR-Images, kein build:)
├── .env                            # Konfiguration (IP, Pfade, Passwörter)
├── install.sh                      # Turnkey-Installer (ein Befehl)
├── update.sh                       # Update auf neueste Images
├── uninstall.sh                    # Vollständige Deinstallation
├── monitor/
│   ├── Dockerfile                  # Python-Exporter Image
│   └── lancache_monitor_docker.py  # Log-Monitor, Prometheus-Exporter & Steam-Tracker
├── prometheus/
│   ├── Dockerfile                  # Prometheus Image (Config eingebaut)
│   ├── prometheus.yml              # Scrape-Konfiguration
│   └── rules/
│       └── lancache_alert_rules.yml
├── grafana/
│   ├── Dockerfile                  # Grafana Image (Provisioning eingebaut)
│   └── provisioning/
│       ├── datasources/prometheus.yml
│       └── dashboards/
│           ├── dashboard.yml
│           └── lancache_grafana_dashboard.json
└── web/
    ├── Dockerfile                  # Nginx + Entrypoint
    ├── entrypoint.sh               # Generiert web_config.js aus Env-Vars
    ├── nginx.conf
    └── index.html                  # Web-Dashboard (Top-Spiele, Statistiken)
```

---

## 🚀 Schnellstart

### Einzeiler-Installation (Linux / Synology SSH)

```bash
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

Der Installer erledigt automatisch:

1. Docker-Verfügbarkeit prüfen
2. IP-Adresse automatisch erkennen
3. Installationsverzeichnis + Datenordner anlegen (`data/cache`, `data/logs`)
4. `docker-compose.yml` und `.env` herunterladen
5. Zufälliges Grafana-Passwort generieren
6. Alle Images pullen und Stack starten
7. Status aller Services prüfen

### Optionale Parameter

```bash
LANCACHE_IP=10.0.0.1 \
CACHE_ROOT=/volume1/docker/lancache \
CACHE_DISK_SIZE=1000g \
GRAFANA_PASSWORD=meinPasswort \
bash install.sh
```

### Manuelle Installation

```bash
mkdir -p /opt/lancache && cd /opt/lancache
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/.env -o .env
nano .env                        # LANCACHE_IP und GRAFANA_PASSWORD anpassen
mkdir -p data/cache data/logs    # Bind-Mount-Verzeichnisse anlegen
docker compose pull
docker compose up -d
```

---

## 🌐 Services & Ports

| Service | Image | Port | Beschreibung |
|---|---|---|---|
| `dns` | `lancachenet/lancache-dns` | 53 UDP+TCP | DNS-Server für Cache-Routing |
| `monolithic` | `lancachenet/monolithic` | 80, 443 | Eigentlicher Game-Cache |
| `log-monitor` | `ghcr.io/bastika07/lancache-monitor` | 9114 | Prometheus-Exporter + Steam-Depot-Tracker |
| `prometheus` | `ghcr.io/bastika07/lancache-prometheus` | 9090 | Metriken-Datenbank |
| `grafana` | `ghcr.io/bastika07/lancache-grafana` | 3000 | Grafana-Dashboard |
| `web-stats` | `ghcr.io/bastika07/lancache-web` | 8080 | Web-Dashboard mit Top-Spiele-Liste |

### URLs nach der Installation

| URL | Beschreibung |
|---|---|
| `http://LANCACHE_IP:8080` | Web-Dashboard (Top-Spiele, Statistiken) |
| `http://LANCACHE_IP:3000` | Grafana (User: `admin`) |
| `http://LANCACHE_IP:9114/metrics` | Prometheus Raw Metrics |
| `http://LANCACHE_IP:9114/depots` | JSON: Steam-Depot-Statistiken |
| `http://LANCACHE_IP:9114/health` | Health-Check Endpoint |
| `http://LANCACHE_IP:9090` | Prometheus UI |

---

## ⚙️ Konfiguration (.env)

| Variable | Standard | Beschreibung |
|---|---|---|
| `LANCACHE_IP` | – | IP des Cache-Servers (**Pflichtfeld**) |
| `DNS_BIND_IP` | = `LANCACHE_IP` | IP für DNS-Binding |
| `UPSTREAM_DNS` | `8.8.8.8` | Fallback-DNS |
| `CACHE_ROOT` | `/opt/lancache/data` | Speicherort für Cache und Logs |
| `CACHE_DISK_SIZE` | `500g` | Maximale Cache-Größe |
| `MIN_FREE_DISK` | `10g` | Mindest-Freispeicher |
| `CACHE_INDEX_SIZE` | `500m` | Nginx Cache-Index RAM |
| `CACHE_MAX_AGE` | `3650d` | Maximales Alter gecachter Dateien |
| `GRAFANA_PASSWORD` | `changeme` | Grafana Admin-Passwort |
| `TZ` | `Europe/Berlin` | Zeitzone |
| `LOG_RETENTION_DAYS` | `30` | Log-Aufbewahrungsdauer |
| `PROMETHEUS_PORT` | `9114` | Port des Log-Monitors |

---

## 🎮 Steam Depot-Tracking

Der `log-monitor` erkennt automatisch Steam-Downloads anhand des URL-Musters `/depot/{ID}/chunk/...` in den Nginx-Access-Logs.

**Features:**
- **Automatische Namensauflösung** – Depot-IDs werden im Hintergrund via Steam API zu echten Spielnamen aufgelöst (Rate-limited, gecacht in `/tmp/steam_names.json`)
- **Statistiken pro Spiel** – Bytes vom Cache, Bytes heruntergeladen, Hit Rate, Anzahl Treffer
- **Top-Spiele-Tabelle** im Web-Dashboard unter Port 8080, sortiert nach gecachten Bytes

### `/depots` Endpoint

```
GET http://LANCACHE_IP:9114/depots?limit=50
```

Beispiel-Antwort:

```json
[
  {
    "depot_id": 228980,
    "name": "Steamworks Common Redistributables",
    "bytes_hit": 10737418240,
    "bytes_miss": 1073741824,
    "bytes_total": 11811160064,
    "hits": 1420,
    "misses": 142,
    "hit_rate": 90.9
  }
]
```

---

## 🔄 Update

```bash
cd /opt/lancache
bash update.sh
```

Oder manuell:

```bash
docker compose pull
docker compose up -d
```

---

## 🗑️ Deinstallation

```bash
cd /opt/lancache
bash uninstall.sh
```

> ⚠️ Löscht alle Container, Volumes und optional die Cache-Daten.

---

## 🏗️ CI/CD (GitHub Actions)

### `build-and-push.yml`

Wird bei jedem Push auf `master` ausgelöst, wenn Dateien in `monitor/`, `prometheus/`, `grafana/` oder `web/` geändert wurden. Manueller Trigger jederzeit möglich.

Baut und pusht 4 Images nach GHCR:
- `ghcr.io/bastika07/lancache-monitor`
- `ghcr.io/bastika07/lancache-prometheus`
- `ghcr.io/bastika07/lancache-grafana`
- `ghcr.io/bastika07/lancache-web`

Tags: `latest`, `sha-XXXXXXX`, Branch-Name

### `release.yml`

Erstellt bei Git-Tags (`v*`) automatisch ein GitHub Release.

---

## 🖥️ Synology NAS

Empfehlung: Installation via SSH, nicht über den Container Manager.

SSH aktivieren: **Systemsteuerung → Terminal & SNMP → SSH-Dienst aktivieren**

```bash
ssh admin@SYNOLOGY-IP

CACHE_ROOT=/volume1/docker/lancache \
CACHE_DISK_SIZE=2000g \
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

> **Hinweis:** Der Container Manager versucht Images lokal zu bauen wenn er `build:` Sektionen findet. Immer die aktuelle `docker-compose.yml` aus dem Repo verwenden – diese enthält ausschließlich `image:` Direktiven.

---

## 🏛️ Architektur

```
Clients im Netz
    │
    ▼  DNS → LANCACHE_IP
  lancache-dns  (Port 53)
    │
    ▼  HTTP/HTTPS
  monolithic  (Port 80/443)
    │  schreibt Access-Logs
    ▼
  log-monitor  (Port 9114)
    ├── /metrics  → Prometheus scrapt alle 15s
    ├── /depots   → Steam-Depot-Statistiken (JSON)
    └── /health   → Health-Check
         │
         ▼
  prometheus  (Port 9090)
         │
         ▼
  grafana  (Port 3000)

  web-stats  (Port 8080) ──── fragt /depots ab ──→ log-monitor
```

---

## 🛠️ Troubleshooting

| Problem | Lösung |
|---|---|
| `unable to evaluate symlinks in Dockerfile path` | Alte `docker-compose.yml` mit `build:` – aktuelle Datei vom Repo laden |
| `bind mount failed: ... does not exist` | `mkdir -p $CACHE_ROOT/cache $CACHE_ROOT/logs` manuell anlegen |
| Web-Dashboard zeigt „Monitor nicht erreichbar" | Port 9114 auf `0.0.0.0` binden statt `127.0.0.1` in `docker-compose.yml` |
| Steam-Spielnamen werden nicht aufgelöst | Monitor-Container benötigt Internetzugang (Steam API) |
| Grafana leer nach Start | Einige Minuten warten – Provisioning läuft beim ersten Start |
| Container Manager GUI zeigt Fehler | Stack immer per SSH mit `docker compose` starten |

---

> Basiert auf [lancachenet](https://github.com/lancachenet) – erweitert um Monitoring, Steam-Depot-Tracking und Turnkey-Installer.
