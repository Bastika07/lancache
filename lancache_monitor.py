#!/usr/bin/env python3
"""
LanCache Real-time Monitoring Script
Überwacht LanCache Logs und erstellt Live-Statistiken
"""

import re
import time
import json
from datetime import datetime
from collections import defaultdict, deque
import threading

class LanCacheMonitor:
    def __init__(self, log_file="/data/logs/access.log"):
        self.log_file = log_file
        self.stats = {
            'requests_per_minute': deque(maxlen=60),
            'cache_hits': 0,
            'cache_misses': 0,
            'total_bytes': 0,
            'cdn_stats': defaultdict(lambda: {'hits': 0, 'misses': 0, 'bytes': 0}),
            'client_stats': defaultdict(lambda: {'requests': 0, 'bytes': 0})
        }
        self.running = True
        
    def parse_log_line(self, line):
        """Parst eine Nginx Log-Zeile"""
        pattern = r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)" "([^"]*)" (\d+\.\d+)'
        match = re.match(pattern, line)
        
        if match:
            return {
                'ip': match.group(1),
                'timestamp': match.group(2),
                'method': match.group(3),
                'url': match.group(4),
                'status': int(match.group(6)),
                'bytes': int(match.group(7)),
                'cache_status': match.group(10),
                'response_time': float(match.group(11))
            }
        return None
    
    def update_stats(self, entry):
        """Aktualisiert Statistiken"""
        if not entry:
            return
            
        # Basic stats
        if entry['cache_status'] == 'HIT':
            self.stats['cache_hits'] += 1
        else:
            self.stats['cache_misses'] += 1
            
        self.stats['total_bytes'] += entry['bytes']
        
        # CDN detection from URL
        cdn = 'unknown'
        url = entry['url'].lower()
        if 'steam' in url:
            cdn = 'steam'
        elif 'epic' in url:
            cdn = 'epic'
        elif 'blizzard' in url or 'battle.net' in url:
            cdn = 'blizzard'
        elif 'origin' in url or 'ea.com' in url:
            cdn = 'origin'
        elif 'uplay' in url or 'ubi.com' in url:
            cdn = 'uplay'
        elif 'windows' in url or 'microsoft' in url:
            cdn = 'windows'
            
        # Update CDN stats
        if entry['cache_status'] == 'HIT':
            self.stats['cdn_stats'][cdn]['hits'] += 1
        else:
            self.stats['cdn_stats'][cdn]['misses'] += 1
        self.stats['cdn_stats'][cdn]['bytes'] += entry['bytes']
        
        # Update client stats
        self.stats['client_stats'][entry['ip']]['requests'] += 1
        self.stats['client_stats'][entry['ip']]['bytes'] += entry['bytes']
    
    def print_stats(self):
        """Gibt aktuelle Statistiken aus"""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"LanCache Live Stats - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        print(f"Total Requests: {total_requests:,}")
        print(f"Cache Hits: {self.stats['cache_hits']:,}")
        print(f"Hit Rate: {hit_rate:.2f}%")
        print(f"Total Data: {self.stats['total_bytes'] / (1024**3):.2f} GB")
        
        print(f"\nTop CDNs:")
        sorted_cdns = sorted(self.stats['cdn_stats'].items(), 
                           key=lambda x: x[1]['bytes'], reverse=True)[:5]
        for cdn, data in sorted_cdns:
            total_cdn_requests = data['hits'] + data['misses']
            cdn_hit_rate = (data['hits'] / total_cdn_requests * 100) if total_cdn_requests > 0 else 0
            print(f"  {cdn}: {data['bytes'] / (1024**3):.2f} GB ({cdn_hit_rate:.1f}% hit rate)")
    
    def monitor(self):
        """Hauptmonitoring-Loop"""
        print(f"Monitoring LanCache logs: {self.log_file}")
        
        try:
            with open(self.log_file, 'r') as f:
                # Gehe zum Ende der Datei
                f.seek(0, 2)
                
                while self.running:
                    line = f.readline()
                    if line:
                        entry = self.parse_log_line(line.strip())
                        self.update_stats(entry)
                    else:
                        time.sleep(0.1)
                        
        except FileNotFoundError:
            print(f"Log file {self.log_file} not found!")
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            self.running = False
    
    def start_monitoring(self):
        """Startet Monitoring in separatem Thread"""
        monitor_thread = threading.Thread(target=self.monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Stats-Output alle 30 Sekunden
        try:
            while True:
                time.sleep(30)
                self.print_stats()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.running = False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='LanCache Monitoring Tool')
    parser.add_argument('--log-file', default='/data/logs/access.log',
                       help='Path to nginx access log file')
    
    args = parser.parse_args()
    
    monitor = LanCacheMonitor(args.log_file)
    monitor.start_monitoring()
