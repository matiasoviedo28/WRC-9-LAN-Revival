#!/usr/bin/env python3
# Servidor KtOS local para WRC 9 en Windows: reemplaza el login caido de ktos.kylotonn.com
# y fuerza el modo LAN oculto. Se abre con INICIAR.bat (como administrador).
import ctypes
import ctypes.wintypes as wt
import json
import os
import ssl
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "ktos.kylotonn.com"
MARK = "# wrc9-ktos"
HOSTS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), r"System32\drivers\etc\hosts")
HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(HERE, "ktos.pem")
LOG = os.path.join(HERE, "wrc9-ktos.log")
FIREWALL_RULE = "WRC9 LAN"
USER_ID = uuid.uuid4().hex
log_lock = threading.Lock()
# Offsets dentro de WRC9.exe (build 6335125): nombre y valor de WRC.UseLanNetwork
NAME_RVA = 0x1387f00
FLAG_RVA = 0x1a231f0
DEFAULT_BASE = 0x140000000

TH32CS_SNAPPROCESS = 0x2
TH32CS_SNAPMODULE = 0x8
TH32CS_SNAPMODULE32 = 0x10
PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400  # VM_OPERATION, VM_READ, VM_WRITE, QUERY_INFORMATION
INVALID_HANDLE = ctypes.c_void_p(-1).value
CTRL_CLOSE_EVENTS = (2, 5, 6)  # cerrar ventana, cerrar sesion, apagar


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("GlblcntUsage", wt.DWORD), ("ProccntUsage", wt.DWORD),
                ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", wt.DWORD),
                ("hModule", wt.HMODULE), ("szModule", ctypes.c_wchar * 256),
                ("szExePath", ctypes.c_wchar * 260)]


def kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    k.Module32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MODULEENTRY32W)]
    k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k.OpenProcess.restype = ctypes.c_void_p
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
    k.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.WriteProcessMemory.argtypes = k.ReadProcessMemory.argtypes
    return k


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


def find_game(k):
    """Devuelve el pid de WRC9.exe, o None."""
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (None, INVALID_HANDLE):
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == "wrc9.exe":
                return entry.th32ProcessID
            ok = k.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return None


def game_base(k, pid):
    """Base del modulo principal; si Windows aun no la informa, la base por defecto."""
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap in (None, INVALID_HANDLE):
        return DEFAULT_BASE
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if k.Module32FirstW(snap, ctypes.byref(entry)):
            return entry.modBaseAddr
    finally:
        k.CloseHandle(snap)
    return DEFAULT_BASE


def alive(k, handle):
    code = wt.DWORD()
    return k.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259  # STILL_ACTIVE


def read(k, handle, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if k.ReadProcessMemory(handle, addr, buf, size, ctypes.byref(got)) and got.value == size:
        return buf.raw
    return None


def force_lan():
    """Mantiene WRC.UseLanNetwork en true mientras el juego este abierto."""
    k = kernel32()
    handle, pid, done = None, None, None
    while True:
        if handle and not alive(k, handle):
            k.CloseHandle(handle)
            handle, pid, done = None, None, None
        if not handle:
            pid = find_game(k)
            if not pid:
                time.sleep(0.02)
                continue
            handle = k.OpenProcess(PROCESS_ACCESS, False, pid)
            if not handle:
                time.sleep(0.02)
                continue
        base = game_base(k, pid) if done != pid else base
        name = read(k, handle, base + NAME_RVA, 14)
        if name != b"UseLanNetwork\0":
            if name is not None and done != "bad":
                log("WRC9.exe en memoria no coincide con este build; no toco nada.")
                done = "bad"
            time.sleep(0.005 if name is None else 1)
            continue
        if read(k, handle, base + FLAG_RVA, 1) != b"\x01":
            k.WriteProcessMemory(handle, base + FLAG_RVA, b"\x01", 1, None)
        if done != pid:
            log(f"Modo LAN forzado en memoria (pid {pid}, base {base:#x}).")
            done = pid
        time.sleep(0.005)


def flush_dns():
    subprocess.run(["ipconfig", "/flushdns"], capture_output=True)


def drop_hosts():
    with open(HOSTS, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    with open(HOSTS, "w", encoding="utf-8") as f:
        f.writelines(l for l in lines if MARK not in l)
    flush_dns()


def add_hosts():
    drop_hosts()
    with open(HOSTS, encoding="utf-8", errors="replace") as f:
        ends_ok = f.read().endswith("\n")
    with open(HOSTS, "a", encoding="utf-8") as f:
        f.write(("" if ends_ok else "\n") + f"127.0.0.1 {HOST} {MARK}\n")
    flush_dns()


def open_firewall():
    found = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"],
                           capture_output=True)
    if found.returncode != 0:
        subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={FIREWALL_RULE}",
                        "dir=in", "action=allow", "protocol=UDP", "localport=60000-60031"],
                       capture_output=True)
        log("Regla de firewall 'WRC9 LAN' agregada (UDP 60000-60031).")


def on_console_close(event):
    if event in CTRL_CLOSE_EVENTS:
        drop_hosts()
        return True
    return False


def main():
    if os.name != "nt":
        sys.exit("Este script es para Windows. En Ubuntu usa la carpeta 'ubuntu'.")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        sys.exit("Abrilo con INICIAR.bat (necesita permisos de administrador).")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT)
    try:
        https = ThreadingHTTPServer(("127.0.0.1", 443), Handler)
    except OSError:
        sys.exit("El puerto 443 esta ocupado por otro programa. Cerralo y volve a intentar.")
    https.socket = ctx.wrap_socket(https.socket, server_side=True)
    try:
        http = ThreadingHTTPServer(("127.0.0.1", 80), Handler)
    except OSError:
        http = None
    open(LOG, "w").close()
    if not http:
        log("Aviso: el puerto 80 esta ocupado; sigo solo con HTTPS.")
    add_hosts()
    handler = ctypes.WINFUNCTYPE(wt.BOOL, wt.DWORD)(on_console_close)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True)
    open_firewall()
    if http:
        threading.Thread(target=http.serve_forever, daemon=True).start()
    threading.Thread(target=force_lan, daemon=True).start()
    log("KtOS local listo. Abri WRC 9. Ctrl+C o cerrar la ventana para terminar.")
    try:
        https.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        drop_hosts()
        log("KtOS local cerrado.")


if __name__ == "__main__":
    main()
