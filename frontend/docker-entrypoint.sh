#!/bin/sh
set -e

PORT="${PORT:-80}"
BACKEND="${BACKEND_URL:-${VITE_API_URL:-}}"
BACKEND="${BACKEND%/}"

PROXY_BLOCK=""
if [ -n "$BACKEND" ]; then
  BACKEND_HOST=$(echo "$BACKEND" | sed -e 's|^https\?://||' -e 's|:.*||' -e 's|/.*||')
  SSL_LINES=""
  if echo "$BACKEND" | grep -q '^https://'; then
    SSL_LINES="proxy_ssl_server_name on;
        proxy_ssl_verify off;"
  fi
  PROXY_BLOCK="location /api/ {
        proxy_pass ${BACKEND}/api/;
        proxy_http_version 1.1;
        ${SSL_LINES}
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        client_max_body_size 1m;
        proxy_set_header Host ${BACKEND_HOST};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection \"\";
    }

    location /health {
        proxy_pass ${BACKEND}/health;
        proxy_http_version 1.1;
        ${SSL_LINES}
        proxy_connect_timeout 30s;
        proxy_read_timeout 30s;
        proxy_set_header Host ${BACKEND_HOST};
    }"
  echo "API proxy enabled -> ${BACKEND} (host: ${BACKEND_HOST})"
else
  echo "WARNING: BACKEND_URL not set — /api requests will fail."
fi

printf '%s\n' "$PROXY_BLOCK" > /tmp/proxy_block.txt
sed "s/PORT_PLACEHOLDER/${PORT}/g" /etc/nginx/conf.d/default.conf.template > /tmp/nginx.conf
awk '
  /__API_PROXY__/ {
    while ((getline line < "/tmp/proxy_block.txt") > 0) print line
    next
  }
  { print }
' /tmp/nginx.conf > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
