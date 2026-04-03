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

STEAM_CACHE_FILE   = "/tmp/steam_names.json"
STEAM_APPLIST_FILE = "/tmp/steam_applist.json"
STEAM_APPLIST_TTL  = 86400        # AppList alle 24h neu laden
RETRY_UNKNOWN_TTL  = 86400        # "Depot XXXXX"-Eintraege nach 24h nochmal versuchen

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


# ── Steam Name-Cache (disk) ───────────────────────────────────────────────────
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


# ── Steam AppList (RAM-Cache) ─────────────────────────────────────────────────
# Globales dict: str(app_id) -> name  (sehr schneller O(1)-Lookup)
_applist: dict = {}
_applist_lock   = threading.Lock()


def get_applist() -> dict:
    with _applist_lock:
        return _applist


def load_applist_from_disk():
    """Laedt gecachte AppList vom Disk. Gibt {} zurueck wenn abgelaufen."""
    try:
        with open(STEAM_APPLIST_FILE) as f:
            data = json.load(f)
        if time.time() - data.get("_fetched", 0) < STEAM_APPLIST_TTL:
            apps = data.get("apps", {})
            logger.info(f"AppList vom Disk geladen: {len(apps)} Apps")
            return apps
    except Exception:
        pass
    return {}


def fetch_applist_from_api():
    """
    Laedt AppList von IStoreService/GetAppList/v1 (benoetigt STEAM_API_KEY).
    Ohne Key: gibt {} zurueck.
    """
    api_key = os.getenv("STEAM_API_KEY", "").strip()
    if not api_key:
        logger.info("Kein STEAM_API_KEY gesetzt – AppList-Fetch uebersprungen")
        return {}

    apps = {}
    last_appid = 0
    page = 0
    try:
        while True:
            page += 1
            url = (
                f"https://api.steampowered.com/IStoreService/GetAppList/v1/"
                f"?key={api_key}&include_games=true&include_dlc=true"
                f"&include_software=false&include_videos=false&include_hardware=false"
                f"&max_results=50000&last_appid={last_appid}"
            )
            with urlopen(url, timeout=20) as r:
                data = json.loads(r.read())
            resp     = data.get("response", {})
            apps_raw = resp.get("apps", [])
            for a in apps_raw:
                if a.get("name"):
                    apps[str(a["appid"])] = a["name"]
            logger.info(f"AppList Seite {page}: {len(apps_raw)} Eintraege (+{len(apps)} gesamt)")
            if resp.get("have_more_results") and apps_raw:
                last_appid = apps_raw[-1]["appid"]
            else:
                break
        # Auf Disk speichern
        with open(STEAM_APPLIST_FILE, "w") as f:
            json.dump({"_fetched": time.time(), "apps": apps}, f)
        logger.info(f"Steam AppList gecacht: {len(apps)} Apps gesamt")
        return apps
    except Exception as e:
        logger.warning(f"AppList-Abruf fehlgeschlagen: {e}")
        return {}


def applist_refresh_worker():
    """Background-Thread: AppList beim Start laden + taeglich erneuern."""
    global _applist
    # Zuerst Disk-Cache versuchen (sofort verfuegbar)
    cached = load_applist_from_disk()
    with _applist_lock:
        _applist = cached
    # Wenn Disk-Cache leer/abgelaufen → API holen
    if not cached:
        fresh = fetch_applist_from_api()
        if fresh:
            with _applist_lock:
                _applist = fresh
    # Danach taeglich erneuern
    while True:
        time.sleep(STEAM_APPLIST_TTL)
        fresh = fetch_applist_from_api()
        if fresh:
            with _applist_lock:
                _applist = fresh


# ── Steam Depot → App-Name Resolver ──────────────────────────────────────────
def resolve_steam_app(depot_id, cache):
    """
    Loest einen Steam Depot auf einen App-Namen auf.

    Reihenfolge:
      1. Disk-Cache  (sofort, kein Netz)
         - Bei bekannten "Depot XXXXX"-Eintraegen: nach RETRY_UNKNOWN_TTL nochmal versuchen
      2. AppList     (RAM-Lookup, O(1), kein Netz)
      3. appdetails  (Steam-API, langsam, Fallback)

    Cache-Eintrag-Format:
      {"app_id": int, "name": str, "source": "applist|appdetails|unknown",
       "_fetched": float, "_retry_after": float (nur bei source=unknown)}
    """
    key = f"depot_{depot_id}"
    now = time.time()

    # 1a. Cache-Hit: bekannter Name → sofort zurueck
    if key in cache:
        entry = cache[key]
        # Retry-Logik: war unbekannt + TTL abgelaufen → nochmal suchen
        if entry.get("source") == "unknown":
            retry_after = entry.get("_retry_after", 0)
            if now < retry_after:
                return entry.get("app_id", depot_id), entry.get("name", f"Depot {depot_id}")
            # TTL abgelaufen → Cache-Eintrag entfernen und neu suchen
            logger.info(f"Depot {depot_id}: Retry nach {RETRY_UNKNOWN_TTL/3600:.0f}h")
            del cache[key]
        else:
            return entry.get("app_id", depot_id), entry.get("name", f"Depot {depot_id}")

    candidates = [depot_id] + list(range(depot_id - 1, depot_id - 11, -1))

    # 2. AppList-Lookup (O(1) pro Kandidat, kein API-Call!)
    applist = get_applist()
    if applist:
        for app_id in candidates:
            if app_id <= 0:
                continue
            name = applist.get(str(app_id))
            if name:
                cache[key] = {
                    "app_id": app_id, "name": name,
                    "source": "applist", "_fetched": now,
                }
                save_steam_cache(cache)
                logger.info(f"Steam Depot {depot_id} → App {app_id}: {name} [AppList]")
                return app_id, name

    # 3. Fallback: appdetails-API (langsam, aber vollstaendiger)
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
                    cache[key] = {
                        "app_id": app_id, "name": name,
                        "source": "appdetails", "_fetched": now,
                    }
                    save_steam_cache(cache)
                    logger.info(f"Steam Depot {depot_id} → App {app_id}: {name} [appdetails]")
                    return app_id, name
        except Exception:
            pass
        time.sleep(0.3)

    # Nicht gefunden → als "unknown" cachen, nach RETRY_UNKNOWN_TTL nochmal
    cache[key] = {
        "app_id": depot_id, "name": f"Depot {depot_id}",
        "source": "unknown", "_fetched": now,
        "_retry_after": now + RETRY_UNKNOWN_TTL,
    }
    save_steam_cache(cache)
    logger.warning(f"Steam Depot {depot_id}: nicht aufloesbar, retry in {RETRY_UNKNOWN_TTL/3600:.0f}h")
    return depot_id, f"Depot {depot_id}"


# ── URL-Parser je CDN ─────────────────────────────────────────────────────────
def extract_game_info(r):
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
        m = re.search(r"/filestreamingservice/files/([0-9a-f-]{36})", url, re.IGNORECASE)
        if m:
            return "wsus", m.group(1).lower(), None
        m = re.search(r"/(?:msdownload|v11|update)/.*?/([^/?]+\.(?:cab|exe|msu|msp|psf))", url, re.IGNORECASE)
        if m:
            return "wsus", m.group(1).lower(), None
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
        self.hit_rate           = Gauge("lancache_hit_rate",             "Hit rate (0-1)",                                 registry=self.registry)
        self.hit_rate_by_cdn    = Gauge("lancache_hit_rate_by_cdn",      "Hit rate by CDN",    ["cdn"],                    registry=self.registry)
        self.active_connections = Gauge("lancache_active_connections",   "Active connections",                             registry=self.registry)
        self.cache_size_bytes   = Gauge("lancache_cache_size_bytes",     "Cache size bytes",                               registry=self.registry)
        self.bytes_served_total = Gauge("lancache_bytes_served_total",   "Total bytes served",                             registry=self.registry)
        self.uptime_seconds     = Gauge("lancache_uptime_seconds",       "Uptime seconds",                                 registry=self.registry)

        self.start_time      = time.time()
        self.total_requests  = self.total_hits = self.total_bytes_served = 0
        self.recent_requests = deque(maxlen=1000)
        self.cdn_stats       = {}

        self.game_stats         = defaultdict(lambda: {"bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0})
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
                if cdn_key == "steam":
                    cache_key = f"depot_{game_id}"
                    entry = self.steam_cache.get(cache_key, {})
                    # In Queue wenn: noch nie gesehen ODER unknown-Retry faellig
                    if cache_key not in self.steam_cache or (
                        entry.get("source") == "unknown" and
                        time.time() >= entry.get("_retry_after", 0)
                    ):
                        self.name_resolve_queue.add(game_id)

    # ── Name-Aufloesung ───────────────────────────────────────────────────────

    def resolve_name(self, cdn, game_id):
        """Gibt (app_id, name, source) zurueck."""
        if cdn == "steam":
            key   = f"depot_{game_id}"
            entry = self.steam_cache.get(key, {})
            return (
                entry.get("app_id", game_id),
                entry.get("name", f"Depot {game_id}"),
                entry.get("source", "unknown"),
            )

        elif cdn == "blizzard":
            name = BLIZZARD_GAMES.get(str(game_id), f"Blizzard: {game_id}")
            src  = "builtin" if str(game_id) in BLIZZARD_GAMES else "unknown"
            return game_id, name, src

        elif cdn == "epicgames":
            short = str(game_id)[:14] if len(str(game_id)) > 14 else str(game_id)
            key   = f"epic_{game_id}"
            entry = self.steam_cache.get(key, {})
            return game_id, entry.get("name", f"Epic: {short}"), entry.get("source", "unknown")

        elif cdn == "wsus":
            if game_id == "__wsus__":
                return game_id, "Windows Update", "builtin"
            short = str(game_id)[:8]
            return game_id, f"Windows Update ({short}...)", "builtin"

        return game_id, str(game_id), "unknown"

    def resolve_names_worker(self):
        """
        Verarbeitet die name_resolve_queue.
        - AppList-Lookup ist O(1) → Batch-Groesse 20
        - appdetails-Fallback ist langsam → weiterhin 5 pro Runde wenn kein AppList
        """
        while True:
            try:
                applist_available = len(get_applist()) > 0
                batch_size = 20 if applist_available else 5

                with self.lock:
                    queue = list(self.name_resolve_queue)[:batch_size]

                for depot_id in queue:
                    resolve_steam_app(depot_id, self.steam_cache)
                    with self.lock:
                        self.name_resolve_queue.discard(depot_id)
                    # AppList: kein Delay noetig; appdetails: kurze Pause
                    if not applist_available:
                        time.sleep(1)
            except Exception as e:
                logger.error(f"Name-Resolver Fehler: {e}")
            time.sleep(5)

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
            steam_groups = {}
            wsus_total   = {"cdn": "wsus", "app_id": "__wsus_total__", "name": "Windows Update (gesamt)",
                            "depots": [], "bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0,
                            "source": "builtin"}
            wsus_files   = []
            other_games  = []

            for (cdn, game_id), stats in self.game_stats.items():
                if cdn_filter and cdn != cdn_filter:
                    continue

                if cdn == "steam":
                    app_id, name, source = self.resolve_name(cdn, game_id)
                    if app_id not in steam_groups:
                        steam_groups[app_id] = {
                            "cdn": "steam", "app_id": app_id, "name": name,
                            "source": source,
                            "depots": [], "bytes_hit": 0, "bytes_miss": 0, "hits": 0, "misses": 0,
                        }
                    steam_groups[app_id]["depots"].append(game_id)
                    steam_groups[app_id]["bytes_hit"]  += stats["bytes_hit"]
                    steam_groups[app_id]["bytes_miss"] += stats["bytes_miss"]
                    steam_groups[app_id]["hits"]       += stats["hits"]
                    steam_groups[app_id]["misses"]     += stats["misses"]

                elif cdn == "wsus":
                    wsus_total["bytes_hit"]  += stats["bytes_hit"]
                    wsus_total["bytes_miss"] += stats["bytes_miss"]
                    wsus_total["hits"]       += stats["hits"]
                    wsus_total["misses"]     += stats["misses"]
                    if game_id != "__wsus__":
                        _, name, source = self.resolve_name(cdn, game_id)
                        wsus_files.append({
                            "cdn": "wsus", "app_id": game_id, "name": name,
                            "source": source,
                            "depots": [], "bytes_hit": stats["bytes_hit"],
                            "bytes_miss": stats["bytes_miss"],
                            "hits": stats["hits"], "misses": stats["misses"],
                        })
                else:
                    _, name, source = self.resolve_name(cdn, game_id)
                    other_games.append({
                        "cdn": cdn, "app_id": str(game_id), "name": name,
                        "source": source,
                        "depots": [], "bytes_hit": stats["bytes_hit"],
                        "bytes_miss": stats["bytes_miss"],
                        "hits": stats["hits"], "misses": stats["misses"],
                    })

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
        for target in [self.monitor_logs, self.update_stats, self.resolve_names_worker, applist_refresh_worker]:
            threading.Thread(target=target, daemon=True).start()
        logger.info(f"HTTP Server gestartet auf Port {self.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    LanCacheMonitor().run()
