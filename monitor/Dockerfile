FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests prometheus_client

COPY lancache_monitor_docker.py /app/monitor.py

RUN mkdir -p /data/logs

EXPOSE 9114

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:9114/health || exit 1

CMD ["python", "/app/monitor.py"]
