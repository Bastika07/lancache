FROM nginx:alpine

COPY index.html    /usr/share/nginx/html/index.html
COPY style.css     /usr/share/nginx/html/style.css
COPY nginx.conf    /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
