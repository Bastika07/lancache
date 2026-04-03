# LanCache Turnkey Full-Stack

![GitHub Actions](https://img.shields.io/github/actions/workflow/status/Bastika07/lancache/build-and-push.yml?branch=master&label=Build)
![GHCR](https://img.shields.io/badge/GHCR-ghcr.io%2Fbastika07-blue)

A self-hosted, full-stack game cache for LAN parties and home networks — including monitoring, a live web dashboard and automatic Steam game name resolution.

All custom images are built and published automatically via GitHub Actions to GHCR. No local `docker build` required.

This docker-compose is meant to run out of the box with minimal changes to the environment variables for your local IP address and disk settings.

# Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

Or manually:

```bash
mkdir -p /opt/lancache && cd /opt/lancache
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/.env -o .env
nano .env
mkdir -p data/cache data/logs
docker compose pull && docker compose up -d
```

# Services

| Service | Image | Port | Description |
|---|---|---|---|
| `dns` | `lancachenet/lancache-dns` | 53 UDP+TCP | DNS server for cache routing |
| `monolithic` | `lancachenet/monolithic` | 80, 443 | The actual game cache |
| `log-monitor` | `ghcr.io/bastika07/lancache-monitor` | 9114 | Prometheus exporter + Steam depot tracker |
| `web-stats` | `ghcr.io/bastika07/lancache-web` | 8080 | Web dashboard with top games list |

After installation the following URLs are available:

| URL | Description |
|---|---|
| `http://LANCACHE_IP:8080` | Web dashboard (top games, statistics) |
| `http://LANCACHE_IP:9114/metrics` | Prometheus raw metrics |
| `http://LANCACHE_IP:9114/depots` | JSON: Steam depot statistics grouped by game |
| `http://LANCACHE_IP:9114/health` | Health check endpoint |

# Settings

> You **MUST** set at least `LANCACHE_IP` and `DNS_BIND_IP`. It is highly recommended that you set `CACHE_ROOT` to a folder of your choosing and configure `CACHE_DISK_SIZE` to match your available storage.

## `LANCACHE_IP`

This provides the IP address of the cache server. The DNS service will advertise all cached services (Steam, Epic, Battle.net, etc.) on this IP.

If your cache host has exactly one IP address (e.g. `192.168.0.10`), specify that here.

> **Note:** unless your cache host is at `10.0.39.1`, you will want to change this value.

## `DNS_BIND_IP`

Sets the IP address that the DNS service listens on. In most setups this is the same as `LANCACHE_IP`.

There are two ways to make your network use the cache:

1. Advertise the IP given in `DNS_BIND_IP` via DHCP to your network as a nameserver. All clients using this DNS will automatically be routed through the cache.
2. Use the configuration generators from [UKLANs' cache-domains](https://github.com/uklans/cache-domains) to load entries into your existing DNS infrastructure.

> **Note:** unless your cache host is at `10.0.39.1`, you will want to change this value.

## `UPSTREAM_DNS`

Upstream DNS resolver used for all requests that are not matched by `lancache-dns` (e.g. regular websites, local hostnames).

### Example resolvers

- Google DNS: `8.8.8.8` / `8.8.4.4`
- Cloudflare: `1.1.1.1`
- OpenDNS: `208.67.222.222`

## `CACHE_ROOT`

Base directory for cached data (`CACHE_ROOT/cache`) and access logs (`CACHE_ROOT/logs`).

Ideally this should be on a dedicated storage device separate from your system root.

> **Note:** defaults to `/opt/lancache/data`. You almost certainly want to change this.

## `CACHE_DISK_SIZE`

Upper limit for cached data. When the total stored amount approaches this limit, the cache server will automatically prune the least recently used content.

> **Note:** must be given in gigabytes with `g` suffix (e.g. `500g`) or terabytes with `t` suffix (e.g. `2t`).

## `MIN_FREE_DISK`

Minimum free disk space that must be kept at all times. Prevents the disk from becoming completely full. When free space drops below this value, the cache server prunes least recently used content.

> **Note:** defaults to `10g`.

## `CACHE_INDEX_SIZE`

Memory allocated for the nginx cache index. Increase this if you have a large cache.

> **Note:** we recommend 250m per 1 TB of `CACHE_DISK_SIZE`. Defaults to `500m`.

## `CACHE_MAX_AGE`

Maximum age of cached data before it is considered expired. In most cases `CACHE_DISK_SIZE` will be the limiting factor before this is reached.

> **Note:** must be given as a number of days with `d` suffix (e.g. `3650d`).

## `GRAFANA_PASSWORD`

Admin password for Grafana (only relevant when using the full stack with Prometheus and Grafana). The installer generates a random password automatically if not set.

> **Note:** defaults to `changeme`. Change this before exposing Grafana to your network.

## `TZ`

Timezone used by all containers. Affects log timestamps.

For a full list of valid timezone names see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

> **Note:** defaults to `Europe/Berlin`.

## `PROMETHEUS_PORT`

Port on which the `log-monitor` exposes metrics and the `/depots` endpoint.

> **Note:** defaults to `9114`.

## `LOG_RETENTION_DAYS`

Number of days access logs are kept.

> **Note:** defaults to `30`.

# Steam Game Tracking

The `log-monitor` service automatically detects Steam downloads by matching the URL pattern `/depot/{ID}/chunk/...` in the nginx access logs.

- Depot IDs are resolved to game names in the background via the Steam API (rate-limited, cached in `/tmp/steam_names.json` inside the container)
- Multiple depots belonging to the same game (base game, DLCs, language packs) are automatically grouped together
- The web dashboard at `:8080` shows a top games table sorted by bytes served from cache
- The raw data is available as JSON at `http://LANCACHE_IP:9114/depots`

Example response from `/depots`:

```json
[
  {
    "app_id": 570,
    "name": "Dota 2",
    "depots": [373301, 373302, 373303],
    "depot_count": 3,
    "bytes_hit": 10737418240,
    "bytes_miss": 1073741824,
    "bytes_total": 11811160064,
    "hits": 1420,
    "misses": 142,
    "hit_rate": 90.9
  }
]
```

# Update

```bash
cd /opt/lancache && bash update.sh
```

Or manually:

```bash
docker compose pull && docker compose up -d
```

# Uninstall

```bash
cd /opt/lancache && bash uninstall.sh
```

> **Warning:** this will remove all containers and volumes. Cache data will be deleted if you confirm during the script.

# Synology NAS

Install via SSH — do not use the Container Manager GUI, as it may attempt to build images locally.

Enable SSH under: **Control Panel → Terminal & SNMP → Enable SSH service**

```bash
ssh admin@SYNOLOGY-IP

CACHE_ROOT=/volume1/docker/lancache \
CACHE_DISK_SIZE=2000g \
curl -fsSL https://raw.githubusercontent.com/Bastika07/lancache/master/install.sh | sudo bash
```

# TrueNAS

Use the slim `docker-compose.yml` without Prometheus and Grafana. Specify absolute paths for all volumes, for example:

```
/mnt/SSD/docker/lancache/cache:/data/cache
/mnt/SSD/docker/lancache/logs:/data/logs
```

Create the directories before starting the stack:

```bash
mkdir -p /mnt/SSD/docker/lancache/cache
mkdir -p /mnt/SSD/docker/lancache/logs
```

# Troubleshooting

| Problem | Solution |
|---|---|
| `unable to evaluate symlinks in Dockerfile path` | Old `docker-compose.yml` with `build:` section — download the current file from the repo |
| `bind mount failed: path does not exist` | Create `$CACHE_ROOT/cache` and `$CACHE_ROOT/logs` manually before starting |
| Web dashboard shows "Monitor not reachable" | Bind port 9114 to `0.0.0.0` instead of `127.0.0.1` in `docker-compose.yml` |
| Steam game names not resolved | The `log-monitor` container requires internet access to reach the Steam API |
| Grafana empty after start | Wait a few minutes — provisioning runs on the first startup |

# More Information

The LanCache docker stack uses the upstream [lancachenet](https://github.com/lancachenet) images for DNS and caching, and adds custom monitoring, Steam depot tracking and a turnkey installer on top.

For general LanCache documentation and FAQ see https://lancache.net/docs/faq/
