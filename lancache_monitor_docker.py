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
            ['status', 'method'],
            registry=self.registry
        )
        
        self.requests_by_cdn = Counter(
            'lancache_requests_by_cdn_total',
            'Total requests by CDN provider', 
            ['cdn'],
            registry=self.registry
        )
        
        self.bytes_total = Counter(
            'lancache_bytes_total',
            'Total bytes served by LanCache',
            ['cdn'],
            registry=self.registry
        )
        
        self.cache_hits = Counter(
            'lancache_cache_hits_total',
            'Total cache hits',
            registry=self.registry
        )
        
        self.cache_misses = Counter(
            'lancache_cache_misses_total', 
            'Total cache misses',
            registry=self.registry
        )
        
        self.hit_rate = Gauge(
            'lancache_hit_rate',
            'Cache hit rate (0-1)',
            registry=self.registry
        )
        
        self.response_time = Histogram(
            'lancache_response_time_seconds',
            'Response time distribution',
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
        
        # CDN-Detection
        self.known_cdns = {
            'steam': ['steampowered.com', 'steamcontent.com', 'steamusercontent.com'],
            'epic': ['epicgames.com', 'unrealengine.com'],
            'blizzard': ['blizzard.com', 'battle.net'],
            'riot': ['riotgames.com'],
            'origin': ['origin.com', 'ea.com'],
            'uplay': ['ubisoft.com'],
            'gog': ['gog.com'],
            'microsoft': ['xbox.com', 'microsoft.com'],
            'sony': ['playstation.com'],
            'nintendo': ['nintendo.com'],
            'generic': []
        }
        
        # Statistiken
        self.start_time = time.time()
        self.total_requests = 0
        self.total_hits = 0
        self.recent_requests = deque(maxlen=1000)
        
        # Setze initiale Werte
        self.hit_rate.set(0.0)
        self.active_connections.set(0)
        self.cache_size_bytes.set(0)
        
        logger.info(f"LanCache Monitor gestartet auf Port {self.port}")
        logger.info(f"Überwache Log: {self.log_path}")

    def identify_cdn(self, url: str) -> str:
        """Identifiziert CDN basierend auf URL"""
        url_lower = url.lower()
        
        for cdn, patterns in self.known_cdns.items():
            for pattern in patterns:
                if pattern in url_lower:
                    return cdn
        
        return 'generic'

    def parse_log_line(self, line: str):
        """Parst nginx Access-Log Zeile"""
        # Nginx Combined Log Format
        pattern = r'^(\S+) - - \[(.*?)\] "(\S+) (.*?) (\S+)" (\d+) (\d+) "(.*?)" "(.*?)"'
        match = re.match(pattern, line.strip())
        
        if not match:
            return None
            
        try:
            return {
                'ip': match.group(1),
                'timestamp': match.group(2),
                'method': match.group(3),
                'url': match.group(4),
                'protocol': match.group(5),
                'status': int(match.group(6)),
                'bytes': int(match.group(7)) if match.group(7).isdigit() else 0,
                'referrer': match.group(8),
                'user_agent': match.group(9)
            }
        except (ValueError, IndexError):
            return None

    def is_cache_hit(self, request) -> bool:
        """Bestimmt ob Request ein Cache-Hit war"""
        if not request:
            return False
            
        status = request['status']
        
        # HTTP 200 und 206 sind meist Cache-Hits
        if status in [200, 206]:
            return True
        
        # 304 Not Modified ist auch ein Hit
        if status == 304:
            return True
            
        return False

    def process_request(self, request):
        """Verarbeitet einen Request"""
        if not request:
            return
            
        self.total_requests += 1
        
        # Extrahiere Daten
        method = request.get('method', 'GET')
        status = str(request.get('status', 0))
        url = request.get('url', '')
        bytes_served = request.get('bytes', 0)
        
        # CDN identifizieren
        cdn = self.identify_cdn(url)
        
        # Metriken aktualisieren
        self.requests_total.labels(status=status, method=method).inc()
        self.requests_by_cdn.labels(cdn=cdn).inc()
        
        if bytes_served > 0:
            self.bytes_total.labels(cdn=cdn).inc(bytes_served)
        
        # Cache Hit/Miss Tracking
        if self.is_cache_hit(request):
            self.total_hits += 1
            self.cache_hits.inc()
        else:
            self.cache_misses.inc()
        
        # Hit Rate berechnen
        if self.total_requests > 0:
            hit_rate = self.total_hits / self.total_requests
            self.hit_rate.set(hit_rate)
        
        # Recent Requests für Aktivitäts-Tracking
        self.recent_requests.append({
            'timestamp': datetime.now(),
            'cdn': cdn,
            'bytes': bytes_served
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
                                request = self.parse_log_line(line)
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
                
                # Cache-Größe schätzen (basierend auf gesamten Bytes)
                total_bytes = sum(self.bytes_total._value._values.values())
                self.cache_size_bytes.set(total_bytes)
                
                logger.info(f"Stats - Requests: {self.total_requests}, "
                          f"Hits: {self.total_hits}, "
                          f"Hit Rate: {self.hit_rate._value.get()*100:.1f}%, "
                          f"Recent: {recent_count}")
                
            except Exception as e:
                logger.error(f"Fehler beim Aktualisieren der Statistiken: {e}")
            
            time.sleep(30)  # Update alle 30 Sekunden

    def create_http_handler(self):
        """Erstellt HTTP Handler für Metriken"""
        registry = self.registry
        
        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/metrics':
                    # Generiere Prometheus-Metriken
                    output = generate_latest(registry)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.send_header('Content-Length', str(len(output)))
                    self.end_headers()
                    self.wfile.write(output)
                    
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'OK')
                    
                else:
                    self.send_response(404)
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
            
            # HTTP Server ausführen
            httpd.serve_forever()
            
        except Exception as e:
            logger.error(f"Fehler beim Starten: {e}")
            raise

if __name__ == "__main__":
    monitor = LanCacheMonitor()
    monitor.run()
