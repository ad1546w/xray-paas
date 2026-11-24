#!/bin/sh
set -e

PORT="${PORT:-8080}"
UUID="${UUID:-68133b31-4a2a-4ba3-9ad7-01783afc08e0}"
WSPATH="${WSPATH:-/w104235bcdf}"
CONF=/tmp/xray-config.json

cat > "$CONF" <<EOF
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": ${PORT},
      "protocol": "vless",
      "settings": {
        "clients": [ { "id": "${UUID}", "flow": "" } ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": { "path": "${WSPATH}" }
      }
    }
  ],
  "outbounds": [
    { "protocol": "freedom", "tag": "direct" },
    { "protocol": "blackhole", "tag": "block" }
  ],
  "routing": {
    "rules": [
      { "type": "field", "ip": ["geoip:private"], "outboundTag": "block" },
      { "type": "field", "protocol": ["bittorrent"], "outboundTag": "block" }
    ]
  }
}
EOF

echo "[xray] port=${PORT} path=${WSPATH} uuid=${UUID}"
exec /usr/local/bin/xray run -c "$CONF"
