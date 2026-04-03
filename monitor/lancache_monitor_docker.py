#!/usr/bin/env python3
import os, time, threading, re, json
from collections import deque, defaultdict
from datetime import datetime
from urllib.request import urlopen
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Counter, Gauge, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STEAM_CACHE_FILE = "/tmp/steam_names.json"

# ── Blizzard Game-Code → Name ─────────────────────────────────────────────────
BLIZZARD_GAMES = {
    "hs":          "Hearthstone",
    "hsb":         "Hearthstone",
    "wow":         "World of Warcraft",
    "wow_classic": "WoW Classic",
    "wowt":        "WoW (PTR)",
    "d3":          "Diablo III",
    "d4":          "Diablo IV",
    "s1":          "StarCraft",
    "s2":          "StarCraft II",
    "pro":         "Overwatch",
    "ow":          "Overwatch 2",
    "bna":         "Battle.net App",
    "agent":       "Battle.net Agent",
    "viper":       "Call of Duty: Black Ops 4",
    "odin":        "Call of Duty: Modern Warfare",
    "lazarus":     "Call of Duty: Modern Warfare II",
    "forerunner":  "Call of Duty: Warzone",
    "wlby":        "Crash Bandicoot 4",
    "zeus":        "Call of Duty: Black Ops Cold War",
    "rtro":        "Blizzard Arcade Collection",
}


# ── Steam Name-Resolver ───────────────────────────────────────────────────────
def load_steam_cache():
    try:
        with open(STEAM_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_steam_cache(cache):
    try:
        with open(STEAM_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


def resolve_steam_app(depot_id, cache):
    key = f"depot_{depot_id}"
    if key in cache:
        entry = cache[key]
        return entry.get("app_id", depot_id), entry.get("name", f"Depot {depot_id}")
    candidates = [depot_id] + list(range(depot_id - 1, depot_id - 11, -1))
    for app_id in candidates:
        if app_id <= 0:
            continue
        try:
            url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&filters=basic"
            with urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            info = data.get(str(app_id), {})
            if info.get("success") and info.get("data", {}).get("name"):
                name = info["data"]["name"]
                if info["data"].get("type", "game") in ("game", "dlc", "application", "demo"):
                    cache[key] = {"app_id": app_id, "name": name}
                    save_steam_cache(cache)
                    logger.info(f"Steam Depot {depot_id} -> App {app_id}: {name}")
                    return app_id, name
        except Exception:
            pass
        time.sleep(0.3)
    cache[key] = {"app_id": depot_id, "name": f"Depot {depot_id}"}
    save_steam_cache(cache)
    return depot_id, f"Depot {depot_id}"


# ── URL-Parser je CDN ─────────────────────────────────────────────────────────
def extract_game_info(r):
    """
    Gibt (cdn, game_id, display_hint) zurueck oder None.

    Steam:      /depot/{depot_id}/chunk/...
    Epic:       /Builds/Org/{org_id}/{manifest_id}/...
    Blizzard:   /tpr/{game_code}/data/...
    WSUS:       /filestreamingservice/files/{uuid}
                /msdownload/update/...
                /v11/...
    """
    cdn = r.get("cdn", "")
    url = r.get("url", "")

    if cdn == "steam":
        m = re.search(r"/depot/(\d+)/", url)
        if m:
            return "steam", int(m.group(1)), None

    elif cdn == "epicgames":
        m = re.search(r"/Builds/Org/([^/]+)/([^/]+)/", url)
        if m:
            return "epicgames", m.group(1), m.group(2)

    elif cdn == "blizzard":
        m = re.search(r"/tpr/([^/]+)/", url)
        if m:
            return "blizzard", m.group(1).lower(), None

    elif cdn == "wsus":
        # Variante 1: /filestreamingservice/files/{uuid}
        m = re.search(r"/filestreamingservice/files/([0-9a-f-]{36})", url, re.IGNORECASE)
        if m:
            return "wsus", m.group(1).lower(), None
        # Variante 2: /msdownload/update/software/.../{filename}
        m = re.search(r"/(?:msdownload|v11|update)/.*?/([^/?]+\.(?:cab|exe|msu|msp|psf))", url, re.IGNORECASE)
        if m:
            return "wsus", m.group(1).lower(), None
        # Fallback: gesamten WSUS-Traffic als eine Gruppe
        return "wsus", "__wsus__", None

    return None


class LanCacheMonitor:
    def __init__(self):
        self.port     = int(os.getenv("PROMETHEUS_PORT", "9114"))
        self.log_path = os.getenv("LOG_PATH", "/data/logs/access.log")
        self.registry = CollectorRegistry()

        self.requests_total     = Counter("lancache_requests_total",    "Total requests",     ["status", "method", "cdn"], registry=self.registry)
        self.bytes_total        = Counter("lancache_bytes_total",        "Total bytes",        ["cdn", "hit_status"],       registry=self.registry)
        self.cache_hits         = Counter("lancache_cache_hits_total",   "Cache hits",         ["cdn"],                    registry=self.registry)
        self.cache_misses       = Counter("lancache_cache_misses_total", "Cache misses",       ["cdn"],                    registry=self.registry)
        self.hit_rate           = Gauge("lancache_hit_rate",             "Hit rate (0-1)",                                registry=self.registry)
        self.hit_rate_by_cdn    = Gauge("lancache_hit_rate_by_cdn",      "Hit rate by CDN",   ["cdn"],                    registry=self.registry)
        self.active_connections = Gauge("lancache_active_connections",   "Active connections",                            registry=self.registry)
        self.cache_size_bytes   = Gauge("lancache_cache_size_bytes",     "Cache size bytes",                              registry=self.registry)
        self.bytes_served_total = Gauge("lancache_bytes_served_total",   "Total bytes served",                            registry=self.registry)
        self.uptime_seconds     = Gauge("lancache_uptime_seconds",       "Uptime seconds",                               registry=self.registry)

        self.start_time      = time.time()
        self.total_requests  = self.total_hits = self.total_bytes_served = 0
        self.recent_requests = deque(maxlen=1000)
        self.cdn_stats       = {}

        # game_stats[(cdn, game_id)] = {bytes_hit, bytes_miss, hits, misses}
        self.game_stats = defaultdict(lambda: {"bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0})

        self.steam_cache        = load_steam_cache()
        self.name_resolve_queue = set()
        self.lock               = threading.Lock()

        for g in [self.hit_rate, self.active_connections, self.cache_size_bytes, self.bytes_served_total]:
            g.set(0)

        logger.info(f"LanCache Monitor gestartet auf Port {self.port}")
        logger.info(f"Ueberwache Log: {self.log_path}")

    # ── Log-Parsing ───────────────────────────────────────────────────────────

    def parse_lancache_log_line(self, line):
        pattern = (
            r'\[([^\]]+)\] (\S+) / - - - \[([^\]]+)\] '
            r'"([^"]+)" (\d+) (\d+) '
            r'"([^"]*)" "([^"]*)" "([^"]*)" "([^"]*)" "([^"]*)"'
        )
        m = re.match(pattern, line.strip())
        if not m:
            return None
        try:
            parts = m.group(4).split(" ")
            return {
                "cdn":        m.group(1).lower(),
                "ip":         m.group(2),
                "method":     parts[0] if parts else "GET",
                "url":        parts[1] if len(parts) > 1 else "/",
                "status":     int(m.group(5)),
                "bytes":      int(m.group(6)) if m.group(6).isdigit() else 0,
                "hit_status": m.group(9),
            }
        except (ValueError, IndexError):
            return None

    def is_cache_hit(self, r):
        s = r.get("hit_status", "").upper()
        if s in ("HIT", "STALE"):              return True
        if s in ("MISS", "BYPASS", "EXPIRED"): return False
        return r.get("status", 0) in (200, 206, 304)

    # ── Request verarbeiten ───────────────────────────────────────────────────

    def process_request(self, r):
        if not r:
            return
        self.total_requests += 1
        cdn, method, status = r.get("cdn", "unknown"), r.get("method", "GET"), str(r.get("status", 0))
        b, hs = r.get("bytes", 0), r.get("hit_status", "UNKNOWN")

        if cdn not in self.cdn_stats:
            self.cdn_stats[cdn] = {"requests": 0, "hits": 0, "bytes": 0}

        self.requests_total.labels(status=status, method=method, cdn=cdn).inc()
        if b > 0:
            self.bytes_total.labels(cdn=cdn, hit_status=hs).inc(b)
            self.total_bytes_served += b
            self.cdn_stats[cdn]["bytes"] += b

        self.cdn_stats[cdn]["requests"] += 1
        hit = self.is_cache_hit(r)
        if hit:
            self.total_hits += 1
            self.cdn_stats[cdn]["hits"] += 1
            self.cache_hits.labels(cdn=cdn).inc()
        else:
            self.cache_misses.labels(cdn=cdn).inc()

        if self.total_requests > 0:
            self.hit_rate.set(self.total_hits / self.total_requests)
        cr = self.cdn_stats[cdn]["requests"]
        if cr > 0:
            self.hit_rate_by_cdn.labels(cdn=cdn).set(self.cdn_stats[cdn]["hits"] / cr)

        self.recent_requests.append({"timestamp": datetime.now(), "cdn": cdn, "bytes": b, "hit_status": hs})

        info = extract_game_info(r)
        if info:
            cdn_key, game_id, _ = info
            key = (cdn_key, game_id)
            with self.lock:
                if hit:
                    self.game_stats[key]["bytes_hit"]  += b
                    self.game_stats[key]["hits"]        += 1
                else:
                    self.game_stats[key]["bytes_miss"] += b
                    self.game_stats[key]["misses"]     += 1
                if cdn_key == "steam" and f"depot_{game_id}" not in self.steam_cache:
                    self.name_resolve_queue.add(game_id)

    # ── Name-Aufloesung ───────────────────────────────────────────────────────

    def resolve_name(self, cdn, game_id):
        if cdn == "steam":
            key   = f"depot_{game_id}"
            entry = self.steam_cache.get(key, {})
            return entry.get("app_id", game_id), entry.get("name", f"Depot {game_id}")

        elif cdn == "blizzard":
            return game_id, BLIZZARD_GAMES.get(str(game_id), f"Blizzard: {game_id}")

        elif cdn == "epicgames":
            short = str(game_id)[:14] if len(str(game_id)) > 14 else str(game_id)
            key   = f"epic_{game_id}"
            name  = self.steam_cache.get(key, {}).get("name", f"Epic: {short}")
            return game_id, name

        elif cdn == "wsus":
            if game_id == "__wsus__":
                return game_id, "Windows Update"
            # UUID kuerzen: ab8250bc-8011-... -> ab8250bc
            short = str(game_id)[:8]
            return game_id, f"Windows Update ({short}...)"

        return game_id, str(game_id)

    def resolve_names_worker(self):
        while True:
            try:
                with self.lock:
                    queue = list(self.name_resolve_queue)[:5]
                for depot_id in queue:
                    resolve_steam_app(depot_id, self.steam_cache)
                    with self.lock:
                        self.name_resolve_queue.discard(depot_id)
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Name-Resolver Fehler: {e}")
            time.sleep(10)

    # ── Log-Monitor & Stats ───────────────────────────────────────────────────

    def monitor_logs(self):
        last_pos = 0
        while True:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, "r") as f:
                        f.seek(last_pos)
                        for line in f:
                            if line.strip():
                                self.process_request(self.parse_lancache_log_line(line))
                        last_pos = f.tell()
                else:
                    logger.warning(f"Log-Datei {self.log_path} nicht gefunden")
                    time.sleep(10)
            except Exception as e:
                logger.error(f"Fehler beim Lesen der Log-Datei: {e}")
                time.sleep(5)
            time.sleep(1)

    def update_stats(self):
        while True:
            try:
                self.uptime_seconds.set(time.time() - self.start_time)
                cutoff = datetime.now()
                recent = sum(1 for r in self.recent_requests if (cutoff - r["timestamp"]).seconds < 60)
                self.active_connections.set(recent)
                tb = int(self.total_bytes_served)
                self.cache_size_bytes.set(tb)
                self.bytes_served_total.set(tb)
                logger.info(
                    f"Stats - Requests: {self.total_requests}, Hits: {self.total_hits}, "
                    f"Hit Rate: {(self.total_hits / max(self.total_requests, 1)) * 100:.1f}%, "
                    f"Bytes: {tb / (1024**3):.1f} GB"
                )
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren: {e}")
            time.sleep(30)

    # ── Spiele-Liste ──────────────────────────────────────────────────────────

    def get_games_list(self, cdn_filter=None, limit=1000):
        with self.lock:
            # Steam: Depots nach App-ID gruppieren
            steam_groups = {}
            # WSUS: alle Dateien zu einer Zeile zusammenfassen (optional)
            wsus_total   = {"cdn": "wsus", "app_id": "__wsus_total__", "name": "Windows Update (gesamt)",
                            "depots": [], "bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0}
            wsus_files   = []
            other_games  = []

            for (cdn, game_id), stats in self.game_stats.items():
                if cdn_filter and cdn != cdn_filter:
                    continue

                if cdn == "steam":
                    app_id, name = self.resolve_name(cdn, game_id)
                    if app_id not in steam_groups:
                        steam_groups[app_id] = {
                            "cdn": "steam", "app_id": app_id, "name": name,
                            "depots": [], "bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0,
                        }
                    steam_groups[app_id]["depots"].append(game_id)
                    steam_groups[app_id]["bytes_hit"]  += stats["bytes_hit"]
                    steam_groups[app_id]["bytes_miss"] += stats["bytes_miss"]
                    steam_groups[app_id]["hits"]       += stats["hits"]
                    steam_groups[app_id]["misses"]     += stats["misses"]

                elif cdn == "wsus":
                    # Gesamtsumme
                    wsus_total["bytes_hit"]  += stats["bytes_hit"]
                    wsus_total["bytes_miss"] += stats["bytes_miss"]
                    wsus_total["hits"]       += stats["hits"]
                    wsus_total["misses"]     += stats["misses"]
                    # Einzelne Datei (UUID / Dateiname)
                    if game_id != "__wsus__":
                        _, name = self.resolve_name(cdn, game_id)
                        wsus_files.append({
                            "cdn": "wsus", "app_id": game_id, "name": name,
                            "depots": [], "bytes_hit": stats["bytes_hit"],
                            "bytes_miss": stats["bytes_miss"],
                            "hits": stats["hits"], "misses": stats["misses"],
                        })

                else:
                    _, name = self.resolve_name(cdn, game_id)
                    other_games.append({
                        "cdn": cdn, "app_id": str(game_id), "name": name,
                        "depots": [], "bytes_hit": stats["bytes_hit"],
                        "bytes_miss": stats["bytes_miss"],
                        "hits": stats["hits"], "misses": stats["misses"],
                    })

            # WSUS-Gesamtzeile nur wenn tatsaechlich Daten vorhanden
            wsus_entries = []
            if wsus_total["bytes_hit"] + wsus_total["bytes_miss"] > 0:
                wsus_entries = [wsus_total] + sorted(wsus_files, key=lambda x: x["bytes_hit"], reverse=True)

            result = list(steam_groups.values()) + other_games + wsus_entries

            for g in result:
                total = g["hits"] + g["misses"]
                g["bytes_total"] = g["bytes_hit"] + g["bytes_miss"]
                g["hit_rate"]    = round(g["hits"] / max(total, 1) * 100, 1)
                g["depot_count"] = len(g["depots"])
                g["depots"]      = sorted(g["depots"]) if g["depots"] else []

            result.sort(key=lambda x: x["bytes_hit"], reverse=True)
            return result[:limit]

    # ── HTTP Handler ──────────────────────────────────────────────────────────

    def create_http_handler(self):
        registry = self.registry
        monitor  = self

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                path   = self.path.split("?")[0]
                params = {}
                if "?" in self.path:
                    for p in self.path.split("?")[1].split("&"):
                        if "=" in p:
                            k, v = p.split("=", 1)
                            params[k] = v

                if path == "/metrics":
                    out = generate_latest(registry)
                    self.send_response(200)
                    self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                    self.send_header("Content-Length", str(len(out)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(out)

                elif path == "/depots":
                    limit = int(params.get("limit", 1000))
                    cdn_f = params.get("cdn", None)
                    data  = monitor.get_games_list(cdn_filter=cdn_f, limit=limit)
                    out   = json.dumps(data, ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)

                elif path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(b"OK")

                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a):
                pass

        return MetricsHandler

    def run(self):
        handler = self.create_http_handler()
        httpd   = HTTPServer(("0.0.0.0", self.port), handler)
        for target in [self.monitor_logs, self.update_stats, self.resolve_names_worker]:
            threading.Thread(target=target, daemon=True).start()
        logger.info(f"HTTP Server gestartet auf Port {self.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    LanCacheMonitor().run()
