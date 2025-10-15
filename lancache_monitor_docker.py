#!/usr/bin/env python3
import os
import time
import threading
import re
from collections import deque
from datetime import datetime
from prometheus_client import start_http_server, Counter, Gauge, Histogram, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LanCacheMonitor:
    def __init__(self):
        self.port = int(os.getenv('PROMETHEUS_PORT', '9114'))
        self.log_path = os.getenv('LOG_PATH', '/data/logs/access.log')
        
        # Erstelle eigene Registry für saubere Metriken
        self.registry = CollectorRegistry()
        
        # Definiere LanCache-spezifische Metriken mit korrekten Typen
        self.requests_total = Counter(
            'lancache_requests_total', 
            'Total number of requests processed by LanCache',
            ['status', 'method', 'cdn'],
            registry=self.registry
        )
        
        self.bytes_total = Counter(
            'lancache_bytes_total',
            'Total bytes served by LanCache',
            ['cdn', 'hit_status'],
            registry=self.registry
        )
        
        self.cache_hits = Counter(
            'lancache_cache_hits_total',
            'Total cache hits',
            ['cdn'],
            registry=self.registry
        )
        
        self.cache_misses = Counter(
            'lancache_cache_misses_total', 
            'Total cache misses',
            ['cdn'],
            registry=self.registry
        )
        
        self.hit_rate = Gauge(
            'lancache_hit_rate',
            'Cache hit rate (0-1)',
            registry=self.registry
        )
        
        self.hit_rate_by_cdn = Gauge(
            'lancache_hit_rate_by_cdn',
            'Cache hit rate by CDN (0-1)',
            ['cdn'],
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            'lancache_active_connections',
            'Current active connections',
            registry=self.registry
        )
        
        self.cache_size_bytes = Gauge(
            'lancache_cache_size_bytes',
            'Current cache size in bytes',
            registry=self.registry
        )
        
        self.uptime_seconds = Gauge(
            'lancache_uptime_seconds',
            'Monitor uptime in seconds',
            registry=self.registry
        )
        
        # Statistiken-Tracking
        self.start_time = time.time()
        self.total_requests = 0
        self.total_hits = 0
        self.total_bytes_served = 0
        self.recent_requests = deque(maxlen=1000)
        
        # CDN-spezifische Statistiken
        self.cdn_stats = {}
        
        # Setze initiale Werte
        self.hit_rate.set(0.0)
        self.active_connections.set(0)
        self.cache_size_bytes.set(0)
        
        logger.info(f"LanCache Monitor gestartet auf Port {self.port}")
        logger.info(f"Überwache Log: {self.log_path}")

    def parse_lancache_log_line(self, line: str):
        """Parst LanCache-spezifisches Log-Format"""
        # LanCache Format: [cdn] ip / - - - [timestamp] "method url protocol" status bytes "referrer" "user_agent" "hit_status" "upstream" "-"
        pattern = r'\[([^\]]+)\] (\S+) / - - - \[([^\]]+)\] "([^"]+)" (\d+) (\d+) "([^"]*)" "([^"]*)" "([^"]*)" "([^"]*)" "-"'
        
        match = re.match(pattern, line.strip())
        
        if not match:
            # Fallback für andere Formate
            logger.debug(f"Konnte Log-Zeile nicht parsen: {line[:100]}...")
            return None
            
        try:
            # Parse HTTP Request
            request_parts = match.group(4).split(' ')
            if len(request_parts) >= 3:
                method = request_parts[0]
                url = request_parts[1]
                protocol = request_parts[2]
            else:
                method = request_parts[0] if request_parts else 'GET'
                url = request_parts[1] if len(request_parts) > 1 else '/'
                protocol = 'HTTP/1.1'
            
            return {
                'cdn': match.group(1).lower(),  # [steam], [epic], etc.
                'ip': match.group(2),
                'timestamp': match.group(3),
                'method': method,
                'url': url,
                'protocol': protocol,
                'status': int(match.group(5)),
                'bytes': int(match.group(6)) if match.group(6).isdigit() else 0,
                'referrer': match.group(7),
                'user_agent': match.group(8),
                'hit_status': match.group(9),  # HIT, MISS, etc.
                'upstream': match.group(10)
            }
        except (ValueError, IndexError) as e:
            logger.debug(f"Fehler beim Parsen: {e}")
            return None

    def is_cache_hit(self, request) -> bool:
        """Bestimmt ob Request ein Cache-Hit war basierend auf hit_status"""
        if not request:
            return False
            
        hit_status = request.get('hit_status', '').upper()
        
        # Direkte Auswertung des hit_status Feldes
        if hit_status in ['HIT', 'STALE']:
            return True
        elif hit_status in ['MISS', 'BYPASS', 'EXPIRED']:
            return False
        
        # Fallback auf HTTP Status
        status = request.get('status', 0)
        if status in [200, 206, 304]:
            return True
            
        return False

    def process_request(self, request):
        """Verarbeitet einen Request"""
        if not request:
            return
            
        self.total_requests += 1
        
        # Extrahiere Daten
        cdn = request.get('cdn', 'unknown')
        method = request.get('method', 'GET')
        status = str(request.get('status', 0))
        bytes_served = request.get('bytes', 0)
        hit_status = request.get('hit_status', 'UNKNOWN')
        
        # CDN-Statistiken initialisieren falls nötig
        if cdn not in self.cdn_stats:
            self.cdn_stats[cdn] = {'requests': 0, 'hits': 0, 'bytes': 0}
        
        # Metriken aktualisieren
        self.requests_total.labels(status=status, method=method, cdn=cdn).inc()
        
        if bytes_served > 0:
            self.bytes_total.labels(cdn=cdn, hit_status=hit_status).inc(bytes_served)
            self.total_bytes_served += bytes_served
            self.cdn_stats[cdn]['bytes'] += bytes_served
        
        # Cache Hit/Miss Tracking
        self.cdn_stats[cdn]['requests'] += 1
        
        if self.is_cache_hit(request):
            self.total_hits += 1
            self.cdn_stats[cdn]['hits'] += 1
            self.cache_hits.labels(cdn=cdn).inc()
        else:
            self.cache_misses.labels(cdn=cdn).inc()
        
        # Hit Rate berechnen (global)
        if self.total_requests > 0:
            hit_rate = self.total_hits / self.total_requests
            self.hit_rate.set(hit_rate)
        
        # Hit Rate per CDN berechnen
        cdn_requests = self.cdn_stats[cdn]['requests']
        if cdn_requests > 0:
            cdn_hit_rate = self.cdn_stats[cdn]['hits'] / cdn_requests
            self.hit_rate_by_cdn.labels(cdn=cdn).set(cdn_hit_rate)
        
        # Recent Requests für Aktivitäts-Tracking
        self.recent_requests.append({
            'timestamp': datetime.now(),
            'cdn': cdn,
            'bytes': bytes_served,
            'hit_status': hit_status
        })

    def monitor_logs(self):
        """Überwacht Log-Datei kontinuierlich"""
        last_pos = 0
        
        while True:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r') as f:
                        f.seek(last_pos)
                        
                        for line in f:
                            if line.strip():
                                request = self.parse_lancache_log_line(line)
                                if request:
                                    self.process_request(request)
                        
                        last_pos = f.tell()
                else:
                    logger.warning(f"Log-Datei {self.log_path} nicht gefunden")
                    time.sleep(10)
                    
            except Exception as e:
                logger.error(f"Fehler beim Lesen der Log-Datei: {e}")
                time.sleep(5)
            
            time.sleep(1)  # Kurze Pause zwischen Checks

    def update_stats(self):
        """Aktualisiert periodische Statistiken"""
        while True:
            try:
                # Uptime aktualisieren
                uptime = time.time() - self.start_time
                self.uptime_seconds.set(uptime)
                
                # Aktive Verbindungen schätzen (Recent Requests in letzter Minute)
                cutoff = datetime.now()
                recent_count = sum(1 for r in self.recent_requests 
                                 if (cutoff - r['timestamp']).seconds < 60)
                self.active_connections.set(recent_count)
                
                # Cache-Größe setzen
                self.cache_size_bytes.set(self.total_bytes_served)
                
                logger.info(f"Stats - Requests: {self.total_requests}, "
                          f"Hits: {self.total_hits}, "
                          f"Hit Rate: {(self.total_hits/max(self.total_requests,1))*100:.1f}%, "
                          f"Recent: {recent_count}")
                
                # CDN-Statistiken loggen
                for cdn, stats in self.cdn_stats.items():
                    if stats['requests'] > 0:
                        cdn_hit_rate = (stats['hits'] / stats['requests']) * 100
                        logger.info(f"{cdn.upper()}: {stats['requests']} req, "
                                  f"{stats['hits']} hits ({cdn_hit_rate:.1f}%), "
                                  f"{stats['bytes']/(1024*1024):.1f} MB")
                
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren der Statistiken: {e}")
            
            time.sleep(30)  # Update alle 30 Sekunden

    def create_http_handler(self):
        """Erstellt HTTP Handler für Metriken"""
        registry = self.registry

    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/metrics':
                output = generate_latest(registry)
                self.send_response(200)
                self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                self.send_header('Content-Length', str(len(output)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(output)
            elif self.path == '/health':
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'OK')
            else:
                self.send_response(404)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Disable HTTP logging

    return MetricsHandler

    def run(self):
        """Hauptausführung"""
        try:
            # Starte HTTP Server für Metriken
            handler = self.create_http_handler()
            httpd = HTTPServer(('0.0.0.0', self.port), handler)
            
            # Starte Background Threads
            log_thread = threading.Thread(target=self.monitor_logs, daemon=True)
            stats_thread = threading.Thread(target=self.update_stats, daemon=True)
            
            log_thread.start()
            stats_thread.start()
            
            logger.info(f"HTTP Server gestartet auf Port {self.port}")
            logger.info("Monitoring Threads gestartet")
            logger.info("Warte auf LanCache Log-Daten...")
            
            # HTTP Server ausführen
            httpd.serve_forever()
            
        except Exception as e:
            logger.error(f"Fehler beim Starten: {e}")
            raise

if __name__ == "__main__":
    monitor = LanCacheMonitor()
    monitor.run()
