#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PAAS 启动脚本: 下载 xray -> 生成配置 -> 前台运行

MODE=reality  VLESS + Reality (推荐, 直通 TCP 端口, 无需域名和证书)
MODE=ws       VLESS + WebSocket (明文, 仅排障用)

环境变量:
  PORT                 容器监听端口(平台注入)
  UUID                 VLESS 用户 UUID
  MODE                 reality | ws, 默认 reality
  WSPATH               ws 模式下的 WebSocket 路径
  REALITY_PRIVATE_KEY  Reality 私钥(服务端)
  REALITY_SNI          Reality 伪装的站点域名, 同时作为 serverNames
  REALITY_DEST         转发目标 host:port, 留空则用 REALITY_SNI:443
  REALITY_SHORT_ID     shortId, 十六进制, 长度偶数且 <= 16
"""

import json
import os
import sys
import time
import zipfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "xray")
URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"

PORT = os.environ.get("PORT") or "8080"
UUID = os.environ.get("UUID") or "68133b31-4a2a-4ba3-9ad7-01783afc08e0"
MODE = (os.environ.get("MODE") or "reality").strip().lower()
WSPATH = os.environ.get("WSPATH") or "/w104235bcdf"
PRIV = os.environ.get("REALITY_PRIVATE_KEY") or "w6BZ477jprB8ZCuEJkTxlG8Gyuz_49cvTqFAh35-ku8"
SNI = os.environ.get("REALITY_SNI") or "www.microsoft.com"
DEST = os.environ.get("REALITY_DEST") or (SNI + ":443")
SID = os.environ.get("REALITY_SHORT_ID") or "3f9c7a1e5d842b60"

if not WSPATH.startswith("/"):
    WSPATH = "/" + WSPATH


def log(msg):
    print("[boot] " + msg, flush=True)


def ensure_binary():
    if os.path.isfile(BIN) and os.access(BIN, os.X_OK):
        log("xray already present, skip download")
        return
    tmp = "/tmp/xray.zip"
    last = None
    for i in range(1, 4):
        try:
            log("downloading xray (attempt %d)" % i)
            urllib.request.urlretrieve(URL, tmp)
            with zipfile.ZipFile(tmp) as z:
                z.extractall(ROOT)
            os.chmod(BIN, 0o755)
            log("download ok")
            return
        except Exception as e:
            last = e
            log("download failed: %r" % (e,))
            time.sleep(3)
    log("FATAL cannot obtain xray binary: %r" % (last,))
    sys.exit(1)


def reality_inbound():
    return {
        "listen": "0.0.0.0",
        "port": int(PORT),
        "protocol": "vless",
        "settings": {
            "clients": [{"id": UUID, "flow": "xtls-rprx-vision"}],
            "decryption": "none",
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "show": False,
                "dest": DEST,
                "xver": 0,
                "serverNames": [SNI],
                "privateKey": PRIV,
                "shortIds": [SID],
            },
        },
    }


def ws_inbound():
    return {
        "listen": "0.0.0.0",
        "port": int(PORT),
        "protocol": "vless",
        "settings": {
            "clients": [{"id": UUID, "flow": ""}],
            "decryption": "none",
        },
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": WSPATH},
        },
    }


def build_config():
    inbound = reality_inbound() if MODE == "reality" else ws_inbound()
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [inbound],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"},
        ],
        "routing": {
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "block"},
                {"type": "field", "protocol": ["bittorrent"], "outboundTag": "block"},
            ]
        },
    }


def main():
    ensure_binary()
    cfg = "/tmp/xray-config.json"
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(build_config(), f, indent=2)
    if MODE == "reality":
        log("mode=reality listen 0.0.0.0:%s sni=%s dest=%s sid=%s uuid=%s"
            % (PORT, SNI, DEST, SID, UUID))
    else:
        log("mode=ws listen 0.0.0.0:%s ws-path=%s uuid=%s" % (PORT, WSPATH, UUID))
    os.execv(BIN, [BIN, "run", "-c", cfg])


if __name__ == "__main__":
    main()
