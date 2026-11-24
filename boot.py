#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PAAS 启动脚本: 下载 xray -> 生成 VLESS+WS 配置 -> 前台运行

环境变量:
  PORT    容器监听端口(平台注入)
  UUID    VLESS 用户 UUID
  WSPATH  WebSocket 路径
"""

import json
import os
import stat
import sys
import time
import zipfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "xray")
URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"

PORT = os.environ.get("PORT") or "8080"
UUID = os.environ.get("UUID") or "68133b31-4a2a-4ba3-9ad7-01783afc08e0"
WSPATH = os.environ.get("WSPATH") or "/w104235bcdf"
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


def build_config():
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
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
        ],
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
    log("listen 0.0.0.0:%s  ws-path=%s  uuid=%s" % (PORT, WSPATH, UUID))
    os.execv(BIN, [BIN, "run", "-c", cfg])


if __name__ == "__main__":
    main()
