#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PAAS 启动脚本: 下载 xray -> 生成证书/配置 -> 前台运行

MODE=wstls    VLESS + WebSocket + TLS(自签)  <- 默认, 已验证兼容 mihomo 1.19.33
MODE=reality  VLESS + Reality                <- 部分客户端不兼容, 备用
MODE=ws       VLESS + WebSocket (明文)        <- 仅排障

环境变量:
  PORT                容器监听端口(平台注入)
  UUID                VLESS 用户 UUID
  MODE                wstls | reality | ws
  WSPATH              WebSocket 路径
  CONF_DIR            证书/配置落盘目录, 默认 /tmp
  XRAY_VERSION        锁定 xray 版本, 如 v25.3.6; 默认 latest
  REALITY_PRIVATE_KEY Reality 私钥(仅 reality 模式)
  REALITY_SNI         Reality 伪装域名(仅 reality 模式)
  REALITY_DEST        转发目标 host:port
  REALITY_SHORT_ID    shortId
"""

import json
import os
import sys
import time
import zipfile
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "xray")
MARK = os.path.join(ROOT, ".xray-version")

PORT = os.environ.get("PORT") or "8080"
UUID = os.environ.get("UUID") or "68133b31-4a2a-4ba3-9ad7-01783afc08e0"
MODE = (os.environ.get("MODE") or "wstls").strip().lower()
WSPATH = os.environ.get("WSPATH") or "/w104235bcdf"
CONF_DIR = os.environ.get("CONF_DIR") or "/tmp"
VER = (os.environ.get("XRAY_VERSION") or "latest").strip()
PRIV = os.environ.get("REALITY_PRIVATE_KEY") or "w6BZ477jprB8ZCuEJkTxlG8Gyuz_49cvTqFAh35-ku8"
SNI = os.environ.get("REALITY_SNI") or "www.microsoft.com"
DEST = os.environ.get("REALITY_DEST") or (SNI + ":443")
SID = os.environ.get("REALITY_SHORT_ID") or "3f9c7a1e5d842b60"

if not WSPATH.startswith("/"):
    WSPATH = "/" + WSPATH

CERT_PATH = os.path.join(CONF_DIR, "xray-cert.pem")
KEY_PATH = os.path.join(CONF_DIR, "xray-key.pem")
CFG_PATH = os.path.join(CONF_DIR, "xray-config.json")

TAG = "latest/download" if VER.lower() == "latest" else "download/" + VER
MIRRORS = [
    "https://github.com/XTLS/Xray-core/releases/%s/Xray-linux-64.zip" % TAG,
    "https://gh-proxy.com/https://github.com/XTLS/Xray-core/releases/%s/Xray-linux-64.zip" % TAG,
    "https://ghfast.top/https://github.com/XTLS/Xray-core/releases/%s/Xray-linux-64.zip" % TAG,
]

CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIBqDCCAU6gAwIBAgIUfijpANKW5JqLpAY1vKg/HdqPHhAwCgYIKoZIzj0EAwIw
QTELMAkGA1UEBhMCU0UxEjAQBgNVBAoMCVRyeUFsdGFyZTEeMBwGA1UEAwwVc2Ut
c3RvMDYudHJ5YWx0YXJlLmFpMB4XDTI2MTEyMzE2MTgzOVoXDTM2MTEyMTE2MTgz
OVowQTELMAkGA1UEBhMCU0UxEjAQBgNVBAoMCVRyeUFsdGFyZTEeMBwGA1UEAwwV
c2Utc3RvMDYudHJ5YWx0YXJlLmFpMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE
sws/+4ghyLU74N/9J3xgi35pSCIXpd0HoKjsstq+AnrlPc0QVfiBGV6ksUti8SYc
xm/1OjHPn+Ip8NyL7as2CKMkMCIwIAYDVR0RBBkwF4IVc2Utc3RvMDYudHJ5YWx0
YXJlLmFpMAoGCCqGSM49BAMCA0gAMEUCIQD+1Z+/+NjlWbkclJUaNq55P3fX5/H9
emxg+RHH9hD2FwIgPDAduoXrt+DTSZWs8uUGv3a1W+wT9Hhp0ghGTWE0Vio=
-----END CERTIFICATE-----"""

KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgKvN5tXFEI9XgmEAO
gcr4tArmR1SKKjOHupFGO22Xa/mhRANCAASzCz/7iCHItTvg3/0nfGCLfmlIIhel
3QegqOyy2r4CeuU9zRBV+IEZXqSxS2LxJhzGb/U6Mc+f4inw3IvtqzYI
-----END PRIVATE KEY-----"""


def log(msg):
    print("[boot] " + msg, flush=True)


def installed_version():
    try:
        with open(MARK, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def ensure_binary():
    have = installed_version()
    if os.path.isfile(BIN) and os.access(BIN, os.X_OK):
        if have == VER:
            log("xray already present (version=%s), skip download" % (have or "?"))
            return
        if not have and VER.lower() == "latest":
            with open(MARK, "w", encoding="utf-8") as f:
                f.write(VER)
            log("xray present, adopting as version=latest, skip download")
            return
    if os.path.isfile(BIN) and have != VER:
        log("version mismatch: installed=%s want=%s, re-downloading" % (have or "?", VER))

    tmp = "/tmp/xray.zip" if os.path.isdir("/tmp") else os.path.join(CONF_DIR, "xray.zip")
    last = None
    for url in MIRRORS:
        for i in range(1, 3):
            try:
                log("downloading %s (attempt %d)" % (url.split("/releases/")[0], i))
                urllib.request.urlretrieve(url, tmp)
                if os.path.getsize(tmp) < 3000000:
                    raise IOError("archive too small: %d bytes" % os.path.getsize(tmp))
                with zipfile.ZipFile(tmp) as z:
                    z.extractall(ROOT)
                os.chmod(BIN, 0o755)
                with open(MARK, "w", encoding="utf-8") as f:
                    f.write(VER)
                log("download ok (version=%s)" % VER)
                return
            except Exception as e:
                last = e
                log("failed: %r" % (e,))
                time.sleep(2)
    log("FATAL cannot obtain xray binary: %r" % (last,))
    sys.exit(1)


def write_cert():
    if os.path.isfile(CERT_PATH) and os.path.isfile(KEY_PATH):
        return
    with open(CERT_PATH, "w", encoding="utf-8") as f:
        f.write(CERT_PEM + "\n")
    with open(KEY_PATH, "w", encoding="utf-8") as f:
        f.write(KEY_PEM + "\n")
    log("self-signed cert written")


def wstls_inbound():
    return {
        "listen": "0.0.0.0",
        "port": int(PORT),
        "protocol": "vless",
        "settings": {
            "clients": [{"id": UUID}],
            "decryption": "none",
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "alpn": ["http/1.1"],
                "certificates": [
                    {"certificateFile": CERT_PATH, "keyFile": KEY_PATH}
                ],
            },
            "wsSettings": {"path": WSPATH},
        },
    }


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
    if MODE == "reality":
        inbound = reality_inbound()
    elif MODE == "ws":
        inbound = ws_inbound()
    else:
        inbound = wstls_inbound()
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
    if MODE in ("wstls", "ws"):
        os.makedirs(CONF_DIR, exist_ok=True)
    if MODE == "wstls":
        write_cert()
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(build_config(), f, indent=2)
    log("mode=%s listen 0.0.0.0:%s ws-path=%s uuid=%s ver=%s"
        % (MODE, PORT, WSPATH, UUID, VER))
    os.execv(BIN, [BIN, "run", "-c", CFG_PATH])


if __name__ == "__main__":
    main()
