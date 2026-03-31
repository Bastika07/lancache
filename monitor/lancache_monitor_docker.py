#!/usr/bin/env python3
import os, time, threading, re, json
from collections import deque, defaultdict
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError
from prometheus_client import Counter, Gauge, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STEAM_CACHE_FILE = '/tmp/steam_names.json'

def load_steam_cache():
    try:
        with open(STEAM_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_steam_cache(cache):
    try:
        with open(STEAM_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

def resolve_steam_name(depot_id, cache):
    key = str(depot_id)
    if key in cache:
        return cache[key]
    # Versuche depot_id direkt als App-ID, dann depot_id-1 bis depot_id-5
    for app_id in [depot_id] + list(range(depot_id - 1, depot_id - 6, -1)):
        if app_id <= 0:
            continue
        try:
            url = f'https://store.steampowered.com/api/appdetails?appids={app_id}&filters=basic'
            with urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            info = data.get(str(app_id), {})
            if info.get('success') and info.get('data', {}).get('name'):
                name = info['data']['name']
                cache[key] = name
                save_steam_cache(cache)
                logger.info(f"Depot {depot_id} → App {app_id} → {name}")
                return name
        except Exception:
            pass
    name = f'Depot {depot_id}'
    cache[key] = name
    save_steam_cache(cache)
    return name


class LanCacheMonitor:
    def __init__(self):
        self.port = int(os.getenv('PROMETHEUS_PORT', '9114'))
        self.log_path = os.getenv('LOG_PATH', '/data/logs/access.log')
        self.registry = CollectorRegistry()

        self.requests_total     = Counter('lancache_requests_total',    'Total requests',         ['status', 'method', 'cdn'], registry=self.registry)
        self.bytes_total        = Counter('lancache_bytes_total',       'Total bytes served',     ['cdn', 'hit_status'],       registry=self.registry)
        self.cache_hits         = Counter('lancache_cache_hits_total',  'Total cache hits',       ['cdn'],                    registry=self.registry)
        self.cache_misses       = Counter('lancache_cache_misses_total','Total cache misses',     ['cdn'],                    registry=self.registry)
        self.hit_rate           = Gauge('lancache_hit_rate',            'Cache hit rate (0-1)',                               registry=self.registry)
        self.hit_rate_by_cdn    = Gauge('lancache_hit_rate_by_cdn',     'Hit rate by CDN (0-1)', ['cdn'],                    registry=self.registry)
        self.active_connections = Gauge('lancache_active_connections',  'Active connections',                                registry=self.registry)
        self.cache_size_bytes   = Gauge('lancache_cache_size_bytes',    'Cache size bytes',                                  registry=self.registry)
        self.bytes_served_total = Gauge('lancache_bytes_served_total',  'Total bytes served',                                registry=self.registry)
        self.uptime_seconds     = Gauge('lancache_uptime_seconds',      'Monitor uptime',                                    registry=self.registry)

        self.start_time = time.time()
        self.total_requests = self.total_hits = self.total_bytes_served = 0
        self.recent_requests = deque(maxlen=1000)
        self.cdn_stats = {}

        # Depot-Tracking
        self.depot_stats = defaultdict(lambda: {'bytes_hit': 0, 'bytes_miss': 0, 'hits': 0, 'misses': 0})
        self.steam_name_cache = load_steam_cache()
        self.name_resolve_queue = set()
        self.lock = threading.Lock()

        for g in [self.hit_rate, self.active_connections, self.cache_size_bytes, self.bytes_served_total]:
            g.set(0)

        logger.info(f"LanCache Monitor gestartet auf Port {self.port}")
        logger.info(f"Ueberwache Log: {self.log_path}")

    def parse_lancache_log_line(self, line):
        pattern = r'\[([^\]]+)\] (\S+) / - - - \[([^\]]+)\] "([^"]+)" (\d+) (\d+) "([^"]*)" "([^"]*)" "([^"]*)" "([^"]*)" "-"'
        m = re.match(pattern, line.strip())
        if not m:
            return None
        try:
            parts = m.group(4).split(' ')
            return {
                'cdn':        m.group(1).lower(),
                'ip':         m.group(2),
                'timestamp':  m.group(3),
                'method':     parts[0] if parts else 'GET',
                'url':        parts[1] if len(parts) > 1 else '/',
                'status':     int(m.group(5)),
                'bytes':      int(m.group(6)) if m.group(6).isdigit() else 0,
                'referrer':   m.group(7),
                'user_agent': m.group(8),
                'hit_status': m.group(9),
                'upstream':   m.group(10),
            }
        except (ValueError, IndexError):
            return None

    def extract_depot_id(self, r):
        """Extrahiert Steam Depot-ID aus URL: /depot/123456/chunk/..."""
        if r.get('cdn', '') != 'steam':
            return None
        url = r.get('url', '')
        m = re.search(r'/depot/(\d+)/', url)
        if m:
            return int(m.group(1))
        return None

    def is_cache_hit(self, r):
        s = r.get('hit_status', '').upper()
        if s in ['HIT', 'STALE']:                return True
        if s in ['MISS', 'BYPASS', 'EXPIRED']:   return False
        return r.get('status', 0) in [200, 206, 304]

    def process_request(self, r):
        if not r:
            return
        self.total_requests += 1
        cdn, method, status = r.get('cdn', 'unknown'), r.get('method', 'GET'), str(r.get('status', 0))
        b, hs = r.get('bytes', 0), r.get('hit_status', 'UNKNOWN')

        if cdn not in self.cdn_stats:
            self.cdn_stats[cdn] = {'requests': 0, 'hits': 0, 'bytes': 0}

        self.requests_total.labels(status=status, method=method, cdn=cdn).inc()
        if b > 0:
            self.bytes_total.labels(cdn=cdn, hit_status=hs).inc(b)
            self.total_bytes_served += b
            self.cdn_stats[cdn]['bytes'] += b

        self.cdn_stats[cdn]['requests'] += 1
        hit = self.is_cache_hit(r)
        if hit:
            self.total_hits += 1
            self.cdn_stats[cdn]['hits'] += 1
            self.cache_hits.labels(cdn=cdn).inc()
        else:
            self.cache_misses.labels(cdn=cdn).inc()

        if self.total_requests > 0:
            self.hit_rate.set(self.total_hits / self.total_requests)
        cr = self.cdn_stats[cdn]['requests']
        if cr > 0:
            self.hit_rate_by_cdn.labels(cdn=cdn).set(self.cdn_stats[cdn]['hits'] / cr)

        self.recent_requests.append({'timestamp': datetime.now(), 'cdn': cdn, 'bytes': b, 'hit_status': hs})

        # Depot tracking
        depot_id = self.extract_depot_id(r)
        if depot_id:
            with self.lock:
                if hit:
                    self.depot_stats[depot_id]['bytes_hit'] += b
                    self.depot_stats[depot_id]['hits'] += 1
                else:
                    self.depot_stats[depot_id]['bytes_miss'] += b
                    self.depot_stats[depot_id]['misses'] += 1
                if depot_id not in self.steam_name_cache:
                    self.name_resolve_queue.add(depot_id)

    def resolve_names_worker(self):
        """Löst Spielnamen im Hintergrund auf (ohne den Monitor zu blockieren)"""
        while True:
            try:
                with self.lock:
                    queue = list(self.name_resolve_queue)[:5]  # max 5 auf einmal
                for depot_id in queue:
                    resolve_steam_name(depot_id, self.steam_name_cache)
                    with self.lock:
                        self.name_resolve_queue.discard(depot_id)
                    time.sleep(1)  # Rate-Limiting
            except Exception as e:
                logger.error(f"Name-Resolver Fehler: {e}")
            time.sleep(10)

    def get_depot_top_list(self, limit=20):
        """Gibt Top-Spiele nach gecachten Bytes zurück"""
        with self.lock:
            depots = []
            for depot_id, stats in self.depot_stats.items():
                total = stats['bytes_hit'] + stats['bytes_miss']
                depots.append({
                    'depot_id':   depot_id,
                    'name':       self.steam_name_cache.get(str(depot_id), f'Depot {depot_id}'),
                    'bytes_hit':  stats['bytes_hit'],
                    'bytes_miss': stats['bytes_miss'],
                    'bytes_total': total,
                    'hits':       stats['hits'],
                    'misses':     stats['misses'],
                    'hit_rate':   round(stats['hits'] / max(stats['hits'] + stats['misses'], 1) * 100, 1),
                })
            depots.sort(key=lambda x: x['bytes_hit'], reverse=True)
            return depots[:limit]

    def monitor_logs(self):
        last_pos = 0
        while True:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r') as f:
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
                recent = sum(1 for r in self.recent_requests if (cutoff - r['timestamp']).seconds < 60)
                self.active_connections.set(recent)
                tb = int(self.total_bytes_served)
                self.cache_size_bytes.set(tb)
                self.bytes_served_total.set(tb)
                gb = tb / (1024 ** 3)
                logger.info(
                    f"Stats - Requests: {self.total_requests}, Hits: {self.total_hits}, "
                    f"Hit Rate: {(self.total_hits / max(self.total_requests, 1)) * 100:.1f}%, "
                    f"Bytes: {gb:.1f} GB, Recent: {recent}"
                )
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren: {e}")
            time.sleep(30)

    def create_http_handler(self):
        registry = self.registry
        monitor = self

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/metrics':
                    out = generate_latest(registry)
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.send_header('Content-Length', str(len(out)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(out)

                elif self.path.startswith('/depots'):
                    limit = 20
                    if '?limit=' in self.path:
                        try:
                            limit = int(self.path.split('?limit=')[1])
                        except Exception:
                            pass
                    data = monitor.get_depot_top_list(limit)
                    out = json.dumps(data, ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)

                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'OK')

                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a):
                pass

        return MetricsHandler

    def run(self):
        handler = self.create_http_handler()
        httpd = HTTPServer(('0.0.0.0', self.port), handler)
        for target in [self.monitor_logs, self.update_stats, self.resolve_names_worker]:
            threading.Thread(target=target, daemon=True).start()
        logger.info(f"HTTP Server gestartet auf Port {self.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    LanCacheMonitor().run()
