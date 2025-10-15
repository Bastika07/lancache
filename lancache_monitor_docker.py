#!/usr/bin/env python3
"""
LanCache Monitoring Script für Docker-Compose Setup
Überwacht LanCache Logs und exportiert Metriken für Prometheus
"""

import re
import time
import json
import os
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class PrometheusMetrics:
    def __init__(self):
        self.metrics = {
            'cache_requests_total': 0,
            'cache_hits_total': 0,
            'cache_misses_total': 0,
            'cache_bytes_total': 0,
            'cache_response_time_sum': 0.0,
            'cache_response_time_count': 0,
            'cdn_requests': defaultdict(int),
            'cdn_hits': defaultdict(int),
            'cdn_bytes': defaultdict(int),
            'client_requests': defaultdict(int),
            'client_bytes': defaultdict(int),
            'status_codes': defaultdict(int)
        }
        self.lock = threading.Lock()
    
    def update(self, entry):
        """Aktualisiert Metriken thread-safe"""
        with self.lock:
            self.metrics['cache_requests_total'] += 1
            self.metrics['cache_bytes_total'] += entry['bytes']
            self.metrics['cache_response_time_sum'] += entry['response_time']
            self.metrics['cache_response_time_count'] += 1
            self.metrics['status_codes'][entry['status']] += 1
            
            if entry['cache_status'] == 'HIT':
                self.metrics['cache_hits_total'] += 1
            else:
                self.metrics['cache_misses_total'] += 1
            
            # CDN detection
            cdn = self.detect_cdn(entry['url'])
            self.metrics['cdn_requests'][cdn] += 1
            self.metrics['cdn_bytes'][cdn] += entry['bytes']
            if entry['cache_status'] == 'HIT':
                self.metrics['cdn_hits'][cdn] += 1
            
            # Client stats
            self.metrics['client_requests'][entry['ip']] += 1
            self.metrics['client_bytes'][entry['ip']] += entry['bytes']
    
    def detect_cdn(self, url):
        """Erkennt CDN aus URL"""
        url_lower = url.lower()
        if any(x in url_lower for x in ['steam', 'steamcontent', 'steamstore']):
            return 'steam'
        elif any(x in url_lower for x in ['epic', 'epicgames']):
            return 'epic'
        elif any(x in url_lower for x in ['blizzard', 'battle.net', 'battlenet']):
            return 'blizzard'
        elif any(x in url_lower for x in ['origin', 'ea.com', 'eaplay']):
            return 'origin'
        elif any(x in url_lower for x in ['uplay', 'ubi.com', 'ubisoft']):
            return 'uplay'
        elif any(x in url_lower for x in ['windows', 'microsoft', 'windowsupdate']):
            return 'windows'
        elif any(x in url_lower for x in ['riot', 'riotgames']):
            return 'riot'
        elif any(x in url_lower for x in ['gog', 'gogalaxy']):
            return 'gog'
        elif any(x in url_lower for x in ['twitch', 'twitchcdn']):
            return 'twitch'
        else:
            return 'other'
    
    def get_prometheus_metrics(self):
        """Gibt Metriken im Prometheus Format zurück"""
        with self.lock:
            output = []
            
            # Basic cache metrics
            output.append(f"# HELP lancache_requests_total Total number of requests")
            output.append(f"# TYPE lancache_requests_total counter")
            output.append(f"lancache_requests_total {self.metrics['cache_requests_total']}")
            
            output.append(f"# HELP lancache_hits_total Total number of cache hits")
            output.append(f"# TYPE lancache_hits_total counter")
            output.append(f"lancache_hits_total {self.metrics['cache_hits_total']}")
            
            output.append(f"# HELP lancache_misses_total Total number of cache misses")
            output.append(f"# TYPE lancache_misses_total counter")
            output.append(f"lancache_misses_total {self.metrics['cache_misses_total']}")
            
            output.append(f"# HELP lancache_bytes_total Total bytes served")
            output.append(f"# TYPE lancache_bytes_total counter")
            output.append(f"lancache_bytes_total {self.metrics['cache_bytes_total']}")
            
            # Hit rate
            total_requests = self.metrics['cache_requests_total']
            hit_rate = (self.metrics['cache_hits_total'] / total_requests) if total_requests > 0 else 0
            output.append(f"# HELP lancache_hit_rate Current cache hit rate")
            output.append(f"# TYPE lancache_hit_rate gauge")
            output.append(f"lancache_hit_rate {hit_rate}")
            
            # Average response time
            avg_response_time = (self.metrics['cache_response_time_sum'] / 
                               self.metrics['cache_response_time_count']) if self.metrics['cache_response_time_count'] > 0 else 0
            output.append(f"# HELP lancache_response_time_avg Average response time in seconds")
            output.append(f"# TYPE lancache_response_time_avg gauge")
            output.append(f"lancache_response_time_avg {avg_response_time}")
            
            # CDN metrics
            output.append(f"# HELP lancache_cdn_requests_total Requests per CDN")
            output.append(f"# TYPE lancache_cdn_requests_total counter")
            for cdn, count in self.metrics['cdn_requests'].items():
                output.append(f'lancache_cdn_requests_total{{cdn="{cdn}"}} {count}')
            
            output.append(f"# HELP lancache_cdn_hits_total Cache hits per CDN")
            output.append(f"# TYPE lancache_cdn_hits_total counter")
            for cdn, count in self.metrics['cdn_hits'].items():
                output.append(f'lancache_cdn_hits_total{{cdn="{cdn}"}} {count}')
            
            output.append(f"# HELP lancache_cdn_bytes_total Bytes served per CDN")
            output.append(f"# TYPE lancache_cdn_bytes_total counter")
            for cdn, bytes_val in self.metrics['cdn_bytes'].items():
                output.append(f'lancache_cdn_bytes_total{{cdn="{cdn}"}} {bytes_val}')
            
            # Status codes
            output.append(f"# HELP lancache_status_codes_total HTTP status codes")
            output.append(f"# TYPE lancache_status_codes_total counter")
            for status, count in self.metrics['status_codes'].items():
                output.append(f'lancache_status_codes_total{{status="{status}"}} {count}')
            
            return "\n".join(output)

class MetricsHandler(BaseHTTPRequestHandler):
    def __init__(self, metrics, *args, **kwargs):
        self.metrics = metrics
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(self.metrics.get_prometheus_metrics().encode('utf-8'))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

class LanCacheMonitor:
    def __init__(self, log_file="/data/logs/access.log", metrics_port=9114):
        self.log_file = log_file
        self.metrics_port = metrics_port
        self.metrics = PrometheusMetrics()
        self.running = True
        
        # Web server für Metriken
        handler = lambda *args, **kwargs: MetricsHandler(self.metrics, *args, **kwargs)
        self.httpd = HTTPServer(('0.0.0.0', metrics_port), handler)
        
    def parse_log_line(self, line):
        """Parst Nginx Access Log"""
        # Standard Nginx log format
        pattern = r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) (?:\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)" "([^"]*)" (\d+\.\d+)'
        match = re.match(pattern, line)
        
        if match:
            return {
                'ip': match.group(1),
                'timestamp': match.group(2),
                'method': match.group(3),
                'url': match.group(4),
                'status': int(match.group(5)),
                'bytes': int(match.group(6)),
                'referer': match.group(7),
                'user_agent': match.group(8),
                'cache_status': match.group(9),
                'response_time': float(match.group(10))
            }
        return None
    
    def tail_log(self):
        """Überwacht Log-Datei kontinuierlich"""
        print(f"Monitoring LanCache logs: {self.log_file}")
        
        while self.running:
            try:
                with open(self.log_file, 'r') as f:
                    # Gehe zum Ende der Datei
                    f.seek(0, 2)
                    
                    while self.running:
                        line = f.readline()
                        if line:
                            entry = self.parse_log_line(line.strip())
                            if entry:
                                self.metrics.update(entry)
                        else:
                            time.sleep(0.1)
                            
            except FileNotFoundError:
                print(f"Waiting for log file {self.log_file}...")
                time.sleep(5)
            except Exception as e:
                print(f"Error reading log: {e}")
                time.sleep(5)
    
    def start_metrics_server(self):
        """Startet Prometheus Metrics HTTP Server"""
        print(f"Starting metrics server on port {self.metrics_port}")
        self.httpd.serve_forever()
    
    def start(self):
        """Startet alle Services"""
        # Starte Metrics Server in separatem Thread
        metrics_thread = threading.Thread(target=self.start_metrics_server)
        metrics_thread.daemon = True
        metrics_thread.start()
        
        # Starte Log Monitoring
        try:
            self.tail_log()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.running = False
            self.httpd.shutdown()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='LanCache Docker Monitoring')
    parser.add_argument('--log-file', 
                       default=os.getenv('LOG_PATH', '/data/logs/access.log'),
                       help='Path to nginx access log')
    parser.add_argument('--metrics-port',
                       default=int(os.getenv('PROMETHEUS_PORT', '9114')),
                       type=int,
                       help='Port for Prometheus metrics')
    
    args = parser.parse_args()
    
    monitor = LanCacheMonitor(args.log_file, args.metrics_port)
    monitor.start()
