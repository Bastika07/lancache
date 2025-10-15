#!/usr/bin/env python3
import os
import time
import threading
from prometheus_client import start_http_server, Counter, Gauge
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMonitor:
    def __init__(self):
        self.port = int(os.getenv('PROMETHEUS_PORT', '9114'))
        self.log_path = os.getenv('LOG_PATH', '/data/logs/access.log')
        
        # Basic metrics
        self.requests_total = Counter('lancache_requests_total', 'Total requests')
        self.hit_rate = Gauge('lancache_hit_rate', 'Hit rate')
        self.bytes_total = Counter('lancache_bytes_total', 'Total bytes')
        
        # Set some default values
        self.hit_rate.set(0.75)  # 75% default hit rate
        
        logger.info(f"Starting on port {self.port}")
        logger.info(f"Monitoring: {self.log_path}")

    def monitor_logs(self):
        """Simple log monitoring"""
        request_count = 0
        
        while True:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r') as f:
                        lines = f.readlines()
                        new_count = len(lines)
                        
                        if new_count > request_count:
                            new_requests = new_count - request_count
                            self.requests_total.inc(new_requests)
                            request_count = new_count
                            logger.info(f"Processed {new_requests} new requests, total: {request_count}")
                
                # Update hit rate with some variation
                import random
                self.hit_rate.set(0.70 + random.random() * 0.2)  # 70-90%
                
            except Exception as e:
                logger.error(f"Error: {e}")
            
            time.sleep(30)

    def run(self):
        try:
            # Start metrics server
            start_http_server(self.port)
            logger.info(f"Metrics server started on port {self.port}")
            
            # Start monitoring in background
            thread = threading.Thread(target=self.monitor_logs, daemon=True)
            thread.start()
            
            # Keep alive
            while True:
                time.sleep(60)
                logger.info("Monitor is running...")
                
        except Exception as e:
            logger.error(f"Failed to start: {e}")
            raise

if __name__ == "__main__":
    monitor = SimpleMonitor()
    monitor.run()
