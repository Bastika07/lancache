# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A turnkey LanCache stack for LAN parties / home networks. It combines the upstream `lancachenet` Docker images (DNS + monolithic game cache) with custom monitoring: a Python Prometheus exporter that parses nginx access logs and resolves Steam depot IDs to game names, plus a static web dashboard. Custom images are built by GitHub Actions and published to GHCR (`ghcr.io/bastika07/lancache-*`) — end users never build locally; they run `install.sh` or `docker compose pull && docker compose up -d`.

User-facing docs and most code comments/log messages are in German. Keep that style when editing.

## Commands

There are no tests and no linter (only a cspell config). Development is: edit, optionally build/run locally, push to `master` — the `build-and-push.yml` workflow then rebuilds any image whose directory (`monitor/`, `web/`, `prometheus/`, `grafana/`) changed and tags it `latest` on GHCR.

```bash
# Build a custom image locally for testing
docker build -t lancache-monitor ./monitor
docker build -t lancache-web ./web

# Run the monitor directly (needs prometheus_client)
LOG_PATH=/path/to/access.log PROMETHEUS_PORT=9114 python3 monitor/lancache_monitor_docker.py

# Run the full stack (requires .env with LANCACHE_IP, DNS_BIND_IP, CACHE_ROOT set)
docker compose pull && docker compose up -d
```

Endpoints when running: web dashboard `:8080`, metrics `:9114/metrics`, game stats JSON `:9114/depots`, health `:9114/health`.

## Architecture

Data flows in one direction:

1. **`monolithic`** (upstream image) caches game downloads and writes an nginx access log to `${CACHE_ROOT}/logs/access.log`.
2. **`monitor/lancache_monitor_docker.py`** (single file, the core of this repo) tails that log read-only. `parse_lancache_log_line()` parses the lancache log format, `extract_game_info()` maps URLs to a game ID per CDN (Steam `/depot/{id}/`, Epic, Blizzard `/tpr/{code}/`, WSUS). It serves three HTTP endpoints from one `BaseHTTPRequestHandler`: `/metrics` (Prometheus), `/depots` (JSON game stats, Steam depots grouped by app), `/health`.
3. **`web/index.html`** fetches `/depots` from the monitor and renders the top-games table. All JS/CSS is inline in `index.html`; `web/entrypoint.sh` generates `web_config.js` at container start from `LANCACHE_IP`/`PROMETHEUS_PORT` so the browser knows where to reach the monitor (the browser talks to the monitor directly, so port 9114 must be bound to a reachable IP).

### Steam name resolution (the most intricate part of the monitor)

Depot IDs from log URLs are resolved to game names in background threads, never on the request path:

- `process_request()` enqueues unknown depot IDs; `resolve_names_worker()` drains the queue.
- Resolution order: disk cache (`steam_names.json`) → Steam AppList lookup (depot ID and the 10 preceding IDs, since depot IDs are usually app_id + small offset) → per-app `appdetails` store API fallback (rate-limited).
- The full AppList is only fetched if `STEAM_API_KEY` is set; it is refreshed every 2h (`STEAM_APPLIST_TTL`) by `applist_refresh_worker()`.
- Unresolvable depots are cached as `source: "unknown"` and retried after `RETRY_UNKNOWN_TTL`.
- Caches live in `CACHE_DIR` (default `/data/cache`) — persistence across container restarts requires that path to be a mounted volume.

Multiple depots resolving to the same app_id are merged into one entry in `get_games_list()`; WSUS requests are aggregated into a single "Windows Update (gesamt)" row plus per-file rows.

### Compose / installer split

- `docker-compose.yml` in the repo is the **slim** stack (dns, monolithic, log-monitor, web-stats — no Prometheus/Grafana). The `prometheus/` and `grafana/` directories exist to build the full-stack images and are still wired into CI, and `install.sh` still health-checks `prometheus`/`grafana` services. Keep these in sync when changing the service set.
- `install.sh` downloads `docker-compose.yml` and generates `.env` from the **raw GitHub URLs on `master`** — changes to those files are live for new installs immediately on push.
- The checked-in `.env` is the template users download; `LANCACHE_IP`/`DNS_BIND_IP` default to a placeholder (`10.0.39.1`) that users must change.

## Gotchas

- `FILE_OVERVIEW.md` is outdated (references files like `Dockerfile.monitor`, `setup_monitoring.sh` that no longer exist) — don't treat it as a source of truth; README.md is current.
- The README's claim that Steam names are cached in `/tmp/steam_names.json` is stale; the code uses `CACHE_DIR` (`/data/cache`).
- `web/style.css` is copied into the image but `index.html` uses only inline styles.
- Git history is mostly "Update <file>" commits made directly on `master`.
