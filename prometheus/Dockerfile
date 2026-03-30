FROM prom/prometheus:latest

COPY prometheus.yml                  /etc/prometheus/prometheus.yml
COPY rules/lancache_alert_rules.yml  /etc/prometheus/rules/lancache_alert_rules.yml

EXPOSE 9090
