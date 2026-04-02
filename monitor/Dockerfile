FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir requests prometheus_client

COPY lancache_monitor_docker.py /app/monitor.py

RUN mkdir -p /data/logs

EXPOSE 9114


CMD ["python", "/app/monitor.py"]
