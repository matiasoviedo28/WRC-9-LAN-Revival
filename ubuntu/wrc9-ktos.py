#!/usr/bin/env python3
# Servidor KtOS local para WRC 9: reemplaza el login caido de ktos.kylotonn.com.
# Uso: sudo python3 wrc9-ktos.py   (dejarlo abierto mientras se juega; Ctrl+C lo cierra)
import json
import os
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "ktos.kylotonn.com"
MARK = "# wrc9-ktos"
HOSTS = "/etc/hosts"
HTTP_PORT = int(os.environ.get("WRC9_HTTP_PORT", 80))
HTTPS_PORT = int(os.environ.get("WRC9_HTTPS_PORT", 443))
USE_HOSTS = HTTPS_PORT == 443
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wrc9-ktos.log")
USER_ID = uuid.uuid4().hex
log_lock = threading.Lock()
# Offsets dentro de WRC9.exe (build 6335125): nombre y valor de WRC.UseLanNetwork
NAME_RVA = 0x1387f00
FLAG_RVA = 0x1a231f0


def log(text):
    line = time.strftime("%H:%M:%S ") + text
    print(line, flush=True)
    with log_lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def reply_for(path):
    body = {"status": 0, "status_text": "OK", "msg": "", "date": int(time.time()), "data": {}}
    if path.split("?")[0].endswith("/users/login"):
        body["data"] = {
            "user_id": USER_ID,
            "token": uuid.uuid4().hex,
            "req_genkey": uuid.uuid4().hex,
            "new_user": False,
            "token_validity_time": 86400,
        }
    return body


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def answer(self):
        size = int(self.headers.get("Content-Length") or 0)
        sent = self.rfile.read(size) if size else b""
        log(f"{self.command} {self.path} ({len(sent)} bytes)")
        data = json.dumps(reply_for(self.path)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = answer

    def log_message(self, *args):
        pass


def game_base():
    """Devuelve (pid, base) del proceso de WRC9.exe. force_lan valida la base."""
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                if not f.read().split(b"\0")[0].endswith(b"WRC9.exe"):
                    continue
            with open(f"/proc/{pid}/maps") as f:
                for line in f:
                    if line.rstrip().endswith("/WRC9.exe"):
                        return int(pid), int(line.split("-")[0], 16)
            return int(pid), 0x140000000
        except OSError:
            continue
    return None


def force_lan():
    """Mantiene WRC.UseLanNetwork en true mientras el juego este abierto."""
    done = None
    while True:
        found = game_base()
        if not found:
            done = None
            time.sleep(0.02)
            continue
        pid, base = found
        try:
            with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
                mem.seek(base + NAME_RVA)
                if mem.read(14) != b"UseLanNetwork\0":
                    if done != "bad":
                        log("WRC9.exe en memoria no coincide con este build; no toco nada.")
                        done = "bad"
                    time.sleep(1)
                    continue
                mem.seek(base + FLAG_RVA)
                if mem.read(1) != b"\x01":
                    mem.seek(base + FLAG_RVA)
                    mem.write(b"\x01")
                if done != pid:
                    log(f"Modo LAN forzado en memoria (pid {pid}, base {base:#x}).")
                    done = pid
        except OSError:
            pass
        time.sleep(0.005)


def make_cert(folder):
    key, crt = f"{folder}/k.pem", f"{folder}/c.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key,
         "-out", crt, "-days", "3650", "-subj", f"/CN={HOST}"],
        check=True, capture_output=True)
    return crt, key


def drop_hosts():
    with open(HOSTS) as f:
        lines = f.readlines()
    with open(HOSTS, "w") as f:
        f.writelines(l for l in lines if MARK not in l)


def add_hosts():
    drop_hosts()
    with open(HOSTS, "a") as f:
        f.write(f"127.0.0.1 {HOST} {MARK}\n")


def main():
    if USE_HOSTS and os.geteuid() != 0:
        sys.exit("Ejecutalo con: sudo python3 wrc9-ktos.py")
    with tempfile.TemporaryDirectory() as folder:
        crt, key = make_cert(folder)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        http = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
        https = ThreadingHTTPServer(("127.0.0.1", HTTPS_PORT), Handler)
        https.socket = ctx.wrap_socket(https.socket, server_side=True)
    if USE_HOSTS:
        add_hosts()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    open(LOG, "w").close()
    threading.Thread(target=http.serve_forever, daemon=True).start()
    threading.Thread(target=force_lan, daemon=True).start()
    log("KtOS local listo. Abri WRC 9. Ctrl+C para cerrar.")
    try:
        https.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if USE_HOSTS:
            drop_hosts()
        log("KtOS local cerrado.")


if __name__ == "__main__":
    main()
