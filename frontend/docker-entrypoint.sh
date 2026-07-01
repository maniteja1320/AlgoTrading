#!/bin/sh
set -e

PORT="${PORT:-80}"
# Runtime backend URL (Railway). Accept VITE_API_URL as alias for convenience.
BACKEND="${BACKEND_URL:-${VITE_API_URL:-}}"
BACKEND="${BACKEND%/}"

PROXY_BLOCK=""
if [ -n "$BACKEND" ]; then
  BACKEND_HOST=$(echo "$BACKEND" | sed -e 's|^https\?://||' -e 's|/.*||')
  PROXY_BLOCK="location /api/ {
        proxy_pass ${BACKEND}/api/;
        proxy_http_version 1.1;
        proxy_ssl_server_name on;
        proxy_set_header Host ${BACKEND_HOST};
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        proxy_pass ${BACKEND}/health;
        proxy_http_version 1.1;
        proxy_ssl_server_name on;
        proxy_set_header Host ${BACKEND_HOST};
    }"
  echo "API proxy enabled -> ${BACKEND}"
else
  echo "WARNING: BACKEND_URL not set — /api requests will fail. Set BACKEND_URL on the frontend service."
fi

# Write nginx config (__API_PROXY__ placeholder must not be indented in sed replacement)
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
