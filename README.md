# LanCache Depot Update

Dieses Paket enthält zwei geänderte Dateien:

## Was neu ist
- `monitor/lancache_monitor_docker.py` – Erkennt Steam Depot-IDs aus den Access-Logs und löst Spielnamen via Steam API auf. Neuer `/depots` Endpoint.
- `web/index.html` – Neues Dashboard mit Top-Spiele-Tabelle (Spielname, Depot-ID, Cache-Bytes, Hit Rate).

## Deployment

### Variante A: Docker Image neu bauen (lokal)
```bash
cp monitor/lancache_monitor_docker.py /pfad/zu/lancache/monitor/
cp web/index.html /pfad/zu/lancache/web/
docker compose build log-monitor web-stats
docker compose up -d log-monitor web-stats
```

### Variante B: GitHub Actions (empfohlen)
Dateien ins Repo committen → GitHub Actions baut und pusht automatisch neue GHCR-Images → `docker compose pull && docker compose up -d`

## Neuer Endpoint
`http://SYNOLOGY-IP:9114/depots` – JSON-Liste aller gecachten Steam-Spiele
