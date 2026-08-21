#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sockrates — find open proxies (SOCKS5/SOCKS4/HTTP), and make each prove it works.

The name is the method. Socrates never accepted a claim at face value; neither
does this. Public lists hand you thousands of proxies in under a second, and
most of them are dead, unreachable for your target, or lying about it. So every
candidate here is cross-examined until it demonstrates what it claims.

The hard part is not finding proxies. Public lists are enormous and mostly dead,
and a proxy that answers a handshake often cannot reach the host you need. So the
tool is built around one idea:

    a proxy is only "good" if it completes a real connection to YOUR target,
    measured with a stopwatch — and if it is not lying about it.

Two checks make the difference:

  * end-to-end proof — for TLS targets we complete the handshake through the
    proxy and verify the certificate, which no fake success can survive;
  * a liar control — we also ask the proxy to connect somewhere that must fail.
    Proxies that report success for everything are dropped, because they would
    poison the output with hosts that never actually connect.

Built-in targets know what Telegram needs, which is not one thing but two:
Bot API clients speak HTTPS to api.telegram.org, user clients (MTProto) open raw
TCP to datacenter IPs. A proxy can allow one and block the other.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import ipaddress
import json
import os
import re
import socket
import ssl
import struct
import sys
import time
from dataclasses import dataclass, asdict
from typing import Iterable, Optional

__version__ = "0.5.0"

REPO = "SimuZSkyNeT/sockrates"
HOME_URL = f"https://github.com/{REPO}"
CHANGELOG_URL = f"https://raw.githubusercontent.com/{REPO}/main/CHANGELOG.md"
DONATE_EVM = "0x74E71BB8849FF0e17FA73Fc61DA107032D117dF6"  # any EVM chain


def _ver_tuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check_for_update(timeout: float = 6.0):
    """Read the published CHANGELOG and report a newer version, with its notes.

    Deliberately reads the changelog rather than a version file: if we are going
    to tell someone an update exists, we should be able to say what is in it.
    Returns (version, notes) or None. Never raises — being offline is not an error.
    """
    import urllib.request
    try:
        req = urllib.request.Request(CHANGELOG_URL,
                                     headers={"User-Agent": f"sockrates/{__version__}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", "ignore")
    except Exception:
        return None
    entries = re.findall(r"^## \[?v?(\d+\.\d+\.\d+)\]?(.*?)(?=^## |\Z)",
                         text, re.M | re.S)
    if not entries:
        return None
    latest, notes = entries[0]
    if _ver_tuple(latest) <= _ver_tuple(__version__):
        return None
    return latest, notes.strip()


def detect_install():
    """How was this copy installed? Returns (method, command, cwd).

    The right way to update depends entirely on the install: a git checkout pulls,
    a pip/pipx install upgrades, and a system package (.deb/.rpm) must go through
    the OS package manager — which needs root, so the app shows the command rather
    than running a package manager behind your back.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # walk up looking for a .git — a working checkout updates with git pull
    d = here
    for _ in range(4):
        if os.path.isdir(os.path.join(d, ".git")):
            return ("git", ["git", "-C", d, "pull", "--ff-only"], d)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    low = here.replace("\\", "/").lower()
    if "/pipx/" in low:
        return ("pipx", ["pipx", "upgrade", "sockrates"], None)
    if "site-packages" in low:
        return ("pip", [sys.executable, "-m", "pip", "install", "--upgrade", "sockrates"], None)
    if "dist-packages" in low:
        # Debian/Fedora system package — owned by root, updated by the OS
        return ("system", None, None)
    return ("unknown", None, None)


def apply_update():
    """Run the update for this install. Returns (ok, message). Never raises."""
    import subprocess
    method, cmd, _ = detect_install()
    if method == "system":
        return (False, "Installed as a system package — update with your package manager:\n"
                       "  Debian/Ubuntu:  sudo apt install --only-upgrade sockrates\n"
                       "  Fedora/RHEL:    sudo dnf upgrade sockrates")
    if not cmd:
        return (False, "Could not tell how this copy was installed. Update it the way you "
                       "installed it (git pull, pipx upgrade, or your package manager).")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return (False, f"'{cmd[0]}' is not installed, so I can't update automatically.")
    except Exception as e:
        return (False, f"Update failed: {e}")
    out = (p.stdout + p.stderr).strip()
    if p.returncode != 0:
        return (False, f"Update failed:\n{out[-400:]}")
    if "up to date" in out.lower() or "already" in out.lower():
        return (True, "Already up to date.")
    return (True, "Updated. Restart Sockrates to run the new version.")

# --------------------------------------------------------------------------
# Sources: plain-text endpoints of ip:port pairs, each tagged with the proxy
# type it serves. A source's type is how a scraped ip:port becomes a typed
# candidate — the lists themselves rarely say. Unreachable or reshuffled sources
# are skipped silently: the set is meant to rot gracefully.
# --------------------------------------------------------------------------
SOURCES = {
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000",
        "https://proxyspace.pro/socks5.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/main/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
    ],
    "socks4": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=5000",
        "https://proxyspace.pro/socks4.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/main/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks4/global/socks4_checked.txt",
    ],
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000",
        "https://proxyspace.pro/https.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/main/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    ],
}
# Back-compat alias for anyone importing the old name.
SOURCES_SOCKS5 = SOURCES["socks5"]

# Telegram datacenter addresses used by MTProto clients (Telethon, mobile apps).
# Port 443 is the one that survives most restrictive networks.
TELEGRAM_DCS = [
    ("149.154.175.50", 443),   # DC1  Miami
    ("149.154.167.51", 443),   # DC2  Amsterdam
    ("149.154.175.100", 443),  # DC3  Miami
    ("149.154.167.91", 443),   # DC4  Amsterdam
    ("91.108.56.130", 443),    # DC5  Singapore
]

TARGETS = {
    # name: (host, port, tls_sni or None, cert_must_contain or None)
    "telegram-bot": ("api.telegram.org", 443, "api.telegram.org", "telegram.org"),
    "telegram-mtproto": (TELEGRAM_DCS[1][0], 443, None, None),
    "https": ("www.cloudflare.com", 443, "www.cloudflare.com", "cloudflare.com"),
}

# A host:port that must NOT connect. Any proxy claiming success here is lying
# about every other result it gives us, so it is discarded.
LIAR_CONTROL = ("192.0.2.1", 65533)  # TEST-NET-1, reserved and unroutable

IPPORT_RX = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3}):(\d{2,5})\b")


@dataclass
class Result:
    proxy: str
    latency: float
    target: str
    verified: str  # "tls-cert" | "mtproto" | "tcp" — how strong the proof is
    country: str = ""
    age_h: float = 0.0        # hours since we first saw this proxy alive
    reliability: float = 0.0  # share of our checks it has passed, 0..1
    checks: int = 0           # how many times we have tested it
    ptype: str = "socks5"     # socks5 | socks4 | http
    anonymity: str = ""       # "" not checked | transparent | anonymous | elite | ?
    udp: str = ""             # "" not checked | yes | no (SOCKS5 UDP relay)

    @property
    def addr(self) -> str:
        """Just ip:port, whatever scheme the candidate carried."""
        return self.proxy.split("://", 1)[-1]

    @property
    def uri(self) -> str:
        return f"{self.ptype}://{self.addr}"

    def line(self) -> str:
        return self.addr

    @property
    def age_label(self) -> str:
        h = self.age_h
        if h < 1:
            return f"{int(h*60)}m"
        if h < 48:
            return f"{h:.0f}h"
        return f"{h/24:.0f}d"


# --------------------------------------------------------------------------
# History — the only honest way to answer "how long has this proxy been up?"
#
# A SOCKS5 server never tells you its uptime; there is no field for it, and any
# list that prints one is guessing. What CAN be known is what *we* have observed:
# when we first saw it answer, how many times we have asked since, and how often
# it delivered. Run with --watch and this turns into a real reliability record.
# --------------------------------------------------------------------------
HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".sockrates", "history.json")
HISTORY_FORGET_DAYS = 14


def load_history(path: str = HISTORY_PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(hist: dict, path: str = HISTORY_PATH) -> None:
    # 🔴 Prune on last *seen*, not last *ok*. Pruning on last_ok would forget a
    # proxy the moment it fails, so its failures would never count and every
    # reliability score would drift towards 100%.
    cutoff = time.time() - HISTORY_FORGET_DAYS * 86400
    hist = {k: v for k, v in hist.items()
            if float(v.get("last_seen") or v.get("last_ok") or 0) > cutoff}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(hist, f)
        os.replace(tmp, path)
    except Exception:
        pass


# How much a single run moves the reliability score. A lifetime pass-ratio weighs
# a proxy's first day the same as today, so one that died a week ago still looks
# decent; an exponential moving average (stab) tracks *recent* behaviour instead.
EWMA_ALPHA = 0.3


def record(hist: dict, tested: Iterable[str], alive: list["Result"]) -> None:
    """Fold one hunt into the history and stamp the results with what we know."""
    now = time.time()
    ok = {r.proxy for r in alive}
    for p in tested:
        e = hist.setdefault(p, {"first": now, "last_ok": 0, "last_seen": now,
                                "checks": 0, "ok": 0, "stab": 0.0})
        e["checks"] = int(e.get("checks", 0)) + 1
        e["last_seen"] = now
        outcome = 1.0 if p in ok else 0.0
        # first observation seeds the average with the outcome itself
        e["stab"] = (outcome if e["checks"] == 1
                     else EWMA_ALPHA * outcome + (1 - EWMA_ALPHA) * float(e.get("stab", 0.0)))
        if p in ok:
            e["ok"] = int(e.get("ok", 0)) + 1
            e["last_ok"] = now
            if not e.get("first_ok"):
                e["first_ok"] = now
    for r in alive:
        e = hist.get(r.proxy, {})
        first = float(e.get("first_ok") or e.get("first") or now)
        r.age_h = max(0.0, (now - first) / 3600.0)
        r.checks = int(e.get("checks", 1))
        # reliability is now the recency-weighted stability, not the lifetime ratio
        r.reliability = float(e.get("stab", 1.0))


# --------------------------------------------------------------------------
# SOCKS5, spoken directly over a socket. No third-party dependency: the
# protocol is a dozen bytes and PySocks would only hide what is going on.
# --------------------------------------------------------------------------
def socks5_connect(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int,
                   timeout: float) -> socket.socket:
    """Open a socket, negotiate SOCKS5 with no authentication, ask for dest.

    Raises on any refusal. Returns a socket already tunnelled to dest.
    """
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        # greeting: version 5, one method, "no authentication"
        s.sendall(b"\x05\x01\x00")
        rep = _recv_exact(s, 2)
        if rep[0] != 0x05:
            raise OSError("not SOCKS5")
        if rep[1] != 0x00:
            raise OSError("authentication required")

        # request: CONNECT
        try:
            packed = ipaddress.ip_address(dest_host)
            atyp = b"\x01" if packed.version == 4 else b"\x04"
            addr = packed.packed
        except ValueError:
            # domain name: let the proxy resolve it (remote DNS)
            raw = dest_host.encode()
            atyp, addr = b"\x03", bytes([len(raw)]) + raw
        s.sendall(b"\x05\x01\x00" + atyp + addr + struct.pack(">H", dest_port))

        rep = _recv_exact(s, 4)
        if rep[1] != 0x00:
            raise OSError(f"refused (code {rep[1]})")
        # drain the bound address so the socket is clean for real traffic
        if rep[3] == 0x01:
            _recv_exact(s, 4 + 2)
        elif rep[3] == 0x03:
            _recv_exact(s, _recv_exact(s, 1)[0] + 2)
        elif rep[3] == 0x04:
            _recv_exact(s, 16 + 2)
        return s
    except Exception:
        s.close()
        raise


def socks4_connect(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int,
                   timeout: float) -> socket.socket:
    """Negotiate SOCKS4/4a CONNECT (no auth). Returns a socket tunnelled to dest.

    SOCKS4 has no domain support; SOCKS4a adds it by sending 0.0.0.x and the
    hostname, and letting the proxy resolve — so a domain target works either way.
    """
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        try:
            ip = ipaddress.ip_address(dest_host)
            if ip.version != 4:
                raise OSError("SOCKS4 is IPv4 only")
            req = b"\x04\x01" + struct.pack(">H", dest_port) + ip.packed + b"\x00"
        except ValueError:
            # SOCKS4a: unroutable marker IP + the hostname, proxy resolves it
            req = (b"\x04\x01" + struct.pack(">H", dest_port) + b"\x00\x00\x00\x01"
                   + b"\x00" + dest_host.encode() + b"\x00")
        s.sendall(req)
        rep = _recv_exact(s, 8)
        if rep[0] != 0x00 or rep[1] != 0x5A:   # 0x5A = request granted
            raise OSError(f"refused (code {rep[1]})")
        return s
    except Exception:
        s.close()
        raise


def http_connect(proxy_host: str, proxy_port: int, dest_host: str, dest_port: int,
                 timeout: float) -> socket.socket:
    """Tunnel through an HTTP proxy with the CONNECT method (no auth).

    This is what an "HTTP/HTTPS proxy" means for arbitrary TCP: the proxy opens a
    raw tunnel to dest:port and everything after is end to end, so our own TLS or
    MTProto handshake runs through it unchanged.
    """
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        hostport = f"{dest_host}:{dest_port}"
        req = (f"CONNECT {hostport} HTTP/1.1\r\nHost: {hostport}\r\n"
               f"Proxy-Connection: keep-alive\r\n\r\n").encode()
        s.sendall(req)
        # read headers up to the blank line
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(256)
            if not chunk:
                raise OSError("connection closed early")
            buf += chunk
            if len(buf) > 8192:
                raise OSError("oversized CONNECT reply")
        status = buf.split(b"\r\n", 1)[0]
        parts = status.split(None, 2)
        if len(parts) < 2 or parts[1] != b"200":
            raise OSError(f"CONNECT refused: {status[:60].decode('latin1', 'replace')}")
        return s
    except Exception:
        s.close()
        raise


# proxy type -> the function that opens a tunnel through it. "https" is an HTTP
# proxy reached the same way (CONNECT); the distinction only matters to the
# operator, not to the tunnel, so they share one connector.
CONNECTORS = {
    "socks5": socks5_connect,
    "socks4": socks4_connect,
    "http": http_connect,
    "https": http_connect,
}
PROXY_TYPES = ["socks5", "socks4", "http"]


def connect_through(ptype: str, phost: str, pport: int, dhost: str, dport: int,
                    timeout: float) -> socket.socket:
    fn = CONNECTORS.get(ptype)
    if not fn:
        raise OSError(f"unknown proxy type {ptype!r}")
    return fn(phost, pport, dhost, dport, timeout)


def split_scheme(cand: str):
    """('socks5://1.2.3.4:1080') -> ('socks5', '1.2.3.4', 1080).

    A bare 'ip:port' defaults to socks5, so old lists and files still work.
    """
    scheme = "socks5"
    if "://" in cand:
        scheme, cand = cand.split("://", 1)
    host, port = cand.rsplit(":", 1)
    return scheme.lower(), host, int(port)


def _recv_exact(s: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise OSError("connection closed early")
        buf += chunk
    return buf


def mtproto_handshake(sock: socket.socket, timeout: float) -> bool:
    """Speak just enough MTProto to make Telegram answer.

    A TCP connection proves the proxy reached *something*. This proves it reached
    *Telegram*: we send req_pq_multi over the abridged transport and require a
    well-formed resPQ carrying back the nonce we chose. Nothing else on the
    internet replies to that.
    """
    import os
    sock.settimeout(timeout)
    nonce = os.urandom(16)
    # unencrypted message: auth_key_id=0, msg_id, length, body
    body = struct.pack("<I", 0xBE7E8EF1) + nonce            # req_pq_multi#be7e8ef1
    msg_id = (int(time.time()) << 32)
    payload = struct.pack("<qq", 0, msg_id) + struct.pack("<I", len(body)) + body
    if len(payload) % 4:
        return False
    sock.sendall(b"\xef")                                    # abridged transport
    words = len(payload) // 4
    head = bytes([words]) if words < 0x7F else b"\x7f" + words.to_bytes(3, "little")
    sock.sendall(head + payload)

    first = sock.recv(1)
    if not first:
        return False
    n = first[0]
    if n == 0x7F:
        n = int.from_bytes(_recv_exact(sock, 3), "little")
    data = _recv_exact(sock, n * 4)
    # skip auth_key_id(8) + msg_id(8) + len(4); then constructor resPQ#05162463
    if len(data) < 24:
        return False
    if struct.unpack_from("<I", data, 20)[0] != 0x05162463:
        return False
    # the server echoes our nonce: proof it is answering US, not replaying
    return data[24:40] == nonce


# --------------------------------------------------------------------------
# Anonymity — does the proxy hide you, or leak your real IP?
#
# transparent : the target sees YOUR real IP (the proxy forwards it). Useless
#               for privacy — you might as well not use a proxy.
# anonymous   : your IP is hidden, but the request carries proxy-tell headers
#               (Via, X-Forwarded-For…), so the target knows a proxy is in play.
# elite       : your IP is hidden AND no proxy headers leak — indistinguishable
#               from a direct connection.
#
# The test: ask a "judge" that echoes back the request it received. If our own
# public IP appears in it, transparent; else if a proxy header is present,
# anonymous; else elite. Judges are plain HTTP so any proxy type can reach them.
# --------------------------------------------------------------------------
IP_ECHO = ["http://api.ipify.org", "http://ipv4.icanhazip.com", "http://ifconfig.me/ip"]
JUDGES = ["httpbin.org", "eu.httpbin.org"]   # /get returns JSON echoing headers+origin
LEAK_HEADERS = {"via", "x-forwarded-for", "x-real-ip", "forwarded", "client-ip",
                "x-proxy-id", "proxy-connection", "x-forwarded", "forwarded-for"}
_REAL_IP_CACHE: list = []


def real_ext_ip(timeout: float = 6.0) -> Optional[str]:
    """Our own public IP, fetched once and cached. Needed to detect a leak."""
    if _REAL_IP_CACHE:
        return _REAL_IP_CACHE[0]
    import urllib.request
    for url in IP_ECHO:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                ip = r.read().decode("utf-8", "ignore").strip()
            ipaddress.ip_address(ip)   # validate
            _REAL_IP_CACHE.append(ip)
            return ip
        except Exception:
            continue
    return None


def anonymity_of(proxy: str, timeout: float, real_ip: Optional[str]) -> str:
    """Return 'transparent' | 'anonymous' | 'elite' | '?' for the proxy.

    '?' means the judge could not be reached through it — an honest 'unknown',
    never guessed.
    """
    try:
        ptype, host, port = split_scheme(proxy)
    except ValueError:
        return "?"
    for judge in JUDGES:
        try:
            if ptype in ("http", "https"):
                # forward proxy: talk to the proxy directly with an absolute URI.
                # Many HTTP proxies refuse CONNECT to :80 but serve plain GETs.
                sock = socket.create_connection((host, port), timeout=timeout)
                request_line = f"GET http://{judge}/get HTTP/1.1"
            else:
                # socks: tunnel to the judge, then a normal origin-form request
                sock = connect_through(ptype, host, port, judge, 80, timeout)
                request_line = "GET /get HTTP/1.1"
        except Exception:
            continue
        try:
            sock.settimeout(timeout)
            req = (f"{request_line}\r\nHost: {judge}\r\n"
                   f"User-Agent: sockrates/{__version__}\r\nAccept: application/json\r\n"
                   f"Connection: close\r\n\r\n").encode()
            sock.sendall(req)
            buf = b""
            while len(buf) < 65536:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except Exception:
            continue
        finally:
            try:
                sock.close()
            except Exception:
                pass
        body = buf.split(b"\r\n\r\n", 1)[-1]
        try:
            data = json.loads(body.decode("utf-8", "ignore"))
            headers = {k.lower(): str(v) for k, v in (data.get("headers") or {}).items()}
            origin = str(data.get("origin", ""))
        except Exception:
            # not JSON (an HTML judge or an error page) — fall back to raw text
            text = body.decode("latin1", "ignore").lower()
            headers = {h: "" for h in LEAK_HEADERS if h in text}
            origin = text
        blob = origin + " " + " ".join(headers.values())
        if real_ip and real_ip in blob:
            return "transparent"
        if any(h in headers for h in LEAK_HEADERS):
            return "anonymous"
        return "elite"
    return "?"


def check(proxy: str, target: str, timeout: float, strict: bool) -> Optional[Result]:
    """Return a Result if the proxy really reaches the target, else None.

    `proxy` may be a bare 'ip:port' (assumed socks5) or 'scheme://ip:port' where
    scheme is socks5 / socks4 / http / https. The verification below is identical
    for every type — only how the tunnel opens differs.
    """
    try:
        ptype, host, port = split_scheme(proxy)
    except ValueError:
        return None
    dest_host, dest_port, sni, cert_needle = TARGETS[target]

    t0 = time.time()
    try:
        sock = connect_through(ptype, host, port, dest_host, dest_port, timeout)
    except Exception:
        return None

    verified = "tcp"
    try:
        if sni:
            # End-to-end proof: a fake success cannot produce a valid certificate.
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(sock, server_hostname=sni) as tls:
                cert = tls.getpeercert()
                names = {v for t in cert.get("subject", ()) for k, v in t if k == "commonName"}
                names |= {v for k, v in cert.get("subjectAltName", ()) if k == "DNS"}
                if cert_needle and not any(cert_needle in n for n in names):
                    return None
                verified = "tls-cert"
        elif dest_port == 443 and _is_telegram_dc(dest_host):
            # raw MTProto target: make Telegram itself answer, not just the TCP stack
            if not mtproto_handshake(sock, timeout):
                return None
            verified = "mtproto"
        else:
            sock.close()
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass
    latency = round(time.time() - t0, 3)

    if strict and _is_liar(ptype, host, port, timeout):
        return None
    return Result(proxy=proxy, latency=latency, target=target, verified=verified, ptype=ptype)


def _is_telegram_dc(host: str) -> bool:
    return any(host == ip for ip, _ in TELEGRAM_DCS)


def _is_liar(ptype: str, host: str, port: int, timeout: float) -> bool:
    """True if the proxy reports success connecting somewhere impossible."""
    try:
        s = connect_through(ptype, host, port, LIAR_CONTROL[0], LIAR_CONTROL[1],
                            min(timeout, 4.0))
        s.close()
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Export formats. A proxy list is consumed by very different tools, and
# reformatting it by hand is exactly the kind of chore that makes people stop
# using a good list.
# --------------------------------------------------------------------------
def fmt_plain(res: list["Result"]) -> str:
    return "\n".join(r.addr for r in res)


def fmt_uri(res: list["Result"]) -> str:
    """scheme:// URIs — what curl, requests and most env vars want."""
    return "\n".join(r.uri for r in res)


def fmt_csv(res: list["Result"]) -> str:
    out = ["type,host,port,latency_s,country,anonymity,udp,verified,known_for,reliability_pct,checks,target"]
    for r in res:
        h, _, p_ = r.addr.rpartition(":")
        out.append(f"{r.ptype},{h},{p_},{r.latency},{r.country},{r.anonymity},{r.udp},{r.verified},"
                   f"{r.age_label},{round(100*r.reliability)},{r.checks},{r.target}")
    return "\n".join(out)


def fmt_json(res: list["Result"]) -> str:
    return json.dumps([asdict(r) for r in res], indent=2)


# proxychains keyword per type: it speaks socks4/socks5/http, and treats an
# https proxy as http.
_PCHAIN = {"socks5": "socks5", "socks4": "socks4", "http": "http", "https": "http"}
# PySocks constant per type, for the paste-ready Python list.
_PYSOCKS = {"socks5": "socks.SOCKS5", "socks4": "socks.SOCKS4",
            "http": "socks.HTTP", "https": "socks.HTTP"}


def fmt_proxychains(res: list["Result"]) -> str:
    """Drop-in block for proxychains.conf ([ProxyList] section)."""
    head = ["# generated by sockrates — paste under [ProxyList]"]
    return "\n".join(head + [f"{_PCHAIN.get(r.ptype, 'socks5')} "
                             f"{r.addr.rsplit(':',1)[0]} {r.addr.rsplit(':',1)[1]}"
                             for r in res])


def fmt_python(res: list["Result"]) -> str:
    """Ready to paste into a Telethon/PySocks script."""
    rows = ",\n".join(f"    ({_PYSOCKS.get(r.ptype, 'socks.SOCKS5')}, "
                      f"{r.addr.rsplit(':',1)[0]!r}, {r.addr.rsplit(':',1)[1]})" for r in res)
    return ("import socks  # pip install pysocks\n\n"
            "# verified by sockrates, fastest first\n"
            f"PROXIES = [\n{rows}\n]\n")


# curl scheme per type: socks5h keeps DNS remote; http proxies use the http scheme.
_CURL = {"socks5": "socks5h", "socks4": "socks4a", "http": "http", "https": "http"}


def fmt_curl(res: list["Result"]) -> str:
    return "\n".join(f"curl --proxy {_CURL.get(r.ptype,'socks5h')}://{r.addr} \\\n"
                     f"     https://api.telegram.org/" for r in res[:50])


FORMATS = {
    "plain": (fmt_plain, ".txt", "ip:port, one per line"),
    "uri": (fmt_uri, ".txt", "socks5://ip:port"),
    "csv": (fmt_csv, ".csv", "spreadsheet: host, port, latency, country, proof"),
    "json": (fmt_json, ".json", "full records"),
    "proxychains": (fmt_proxychains, ".conf", "block for proxychains.conf"),
    "python": (fmt_python, ".py", "PySocks/Telethon list, ready to paste"),
    "curl": (fmt_curl, ".sh", "example curl commands (first 50)"),
}


def render(res: list["Result"], fmt: str) -> str:
    return FORMATS[fmt][0](res)


def _fetch_ipports(url: str, timeout: float) -> set[str]:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": f"sockrates/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8", "ignore")
    return {f"{ip}:{port}" for ip, port in IPPORT_RX.findall(text) if 0 < int(port) < 65536}


def collect(types: Iterable[str] = ("socks5",), timeout: float = 12.0,
            verbose: bool = False) -> list[str]:
    """Collect typed candidates ('scheme://ip:port') for the given proxy types.

    Each type's sources tag their addresses with that type. The same ip:port can
    legitimately appear as both a socks5 and an http candidate — they are checked
    and tracked separately, because a box can run one and not the other.
    """
    found: set[str] = set()
    for ptype in types:
        for url in SOURCES.get(ptype, []):
            try:
                got = _fetch_ipports(url, timeout)
            except Exception as e:
                if verbose:
                    print(f"  ✗ [{ptype}] {url.split('/')[2]}: {e}", file=sys.stderr)
                continue
            for hp in got:
                found.add(f"{ptype}://{hp}")
            if verbose:
                print(f"  ✓ [{ptype}] {url.split('/')[2]:<26} +{len(got)}", file=sys.stderr)
    return sorted(found)


# --------------------------------------------------------------------------
# Scan mode — generate candidates from IP ranges instead of public lists.
#
# Public lists are other people's discoveries. Scanning finds proxies nobody has
# published yet: you enumerate a range, knock on the ports SOCKS5 usually lives
# on, and keep whatever answers a SOCKS5 greeting. What survives then goes through
# the exact same cross-examination as a listed proxy — a bare open port is not a
# working proxy until it proves it.
#
# 🔴 This reaches out to machines that never advertised themselves. Only scan
# ranges you own or are authorised to test. Port scanning is treated as
# unauthorised access in some jurisdictions regardless of intent; the default
# rate is deliberately gentle, and there is no "scan the whole internet" switch.
# --------------------------------------------------------------------------
SOCKS5_PORTS = [1080, 1081, 1085, 4145, 5678, 9050, 9051, 7890, 1090, 8080, 3128, 9999]


def _socks5_open(host: str, port: int, timeout: float) -> bool:
    """True if host:port answers a SOCKS5 no-auth greeting. Cheap pre-filter."""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
    except Exception:
        return False
    try:
        s.settimeout(timeout)
        s.sendall(b"\x05\x01\x00")
        rep = _recv_exact(s, 2)   # read exactly 2 bytes: a split reply is not a refusal
        return rep[0] == 0x05 and rep[1] in (0x00, 0x02)
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


# A harmless, always-up anchor to prove a socks4/http proxy actually tunnels.
# Unlike SOCKS5, those protocols have no server-initiated greeting, so the only
# way to know the port really is such a proxy is to open a real tunnel through it.
SCAN_ANCHOR = ("1.1.1.1", 80)


def _proxy_open(ptype: str, host: str, port: int, timeout: float) -> bool:
    """True if host:port behaves as a proxy of the given type."""
    if ptype == "socks5":
        return _socks5_open(host, port, timeout)
    try:
        s = connect_through(ptype, host, port, SCAN_ANCHOR[0], SCAN_ANCHOR[1], timeout)
        s.close()
        return True
    except Exception:
        return False


def _dns_query(name: str) -> bytes:
    """A minimal DNS 'A' query packet — used to prove a SOCKS5 UDP relay works."""
    qid = b"\x53\x6b"  # fixed id; we match it back in the reply
    header = qid + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return header + q + b"\x00\x01\x00\x01"   # QTYPE=A, QCLASS=IN


def socks5_udp_works(host: str, port: int, timeout: float) -> bool:
    """True if the SOCKS5 proxy actually relays UDP (UDP ASSOCIATE + a real DNS round trip).

    Most SOCKS5 servers advertise but never relay UDP; the only way to know is to
    associate, send a DNS query through the relay, and require a DNS answer back.
    The control TCP socket must stay open for the association to live.
    """
    ctrl = None
    try:
        ctrl = socket.create_connection((host, port), timeout=timeout)
        ctrl.settimeout(timeout)
        ctrl.sendall(b"\x05\x01\x00")
        if _recv_exact(ctrl, 2)[1] != 0x00:
            return False
        # UDP ASSOCIATE (cmd 0x03); we don't know our source addr, send 0.0.0.0:0
        ctrl.sendall(b"\x05\x03\x00\x01" + b"\x00\x00\x00\x00" + b"\x00\x00")
        rep = _recv_exact(ctrl, 4)
        if rep[1] != 0x00:
            return False   # 0x07 = command not supported → TCP-only proxy
        atyp = rep[3]
        if atyp == 0x01:
            baddr = socket.inet_ntoa(_recv_exact(ctrl, 4))
        elif atyp == 0x04:
            baddr = socket.inet_ntop(socket.AF_INET6, _recv_exact(ctrl, 16))
        elif atyp == 0x03:
            baddr = _recv_exact(ctrl, _recv_exact(ctrl, 1)[0]).decode("latin1")
        else:
            return False
        bport = struct.unpack(">H", _recv_exact(ctrl, 2))[0]
        # a relay bound to 0.0.0.0 means "send to the same IP as the proxy"
        if baddr in ("0.0.0.0", "::"):
            baddr = host

        # SOCKS5 UDP request: RSV(2) FRAG(1) ATYP DST.ADDR DST.PORT DATA
        dns = _dns_query("example.com")
        pkt = b"\x00\x00\x00\x01" + socket.inet_aton("8.8.8.8") + struct.pack(">H", 53) + dns
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.settimeout(timeout)
        try:
            u.sendto(pkt, (baddr, bport))
            data, _ = u.recvfrom(2048)
        finally:
            u.close()
        # strip the SOCKS5 UDP header, then require our DNS id + an answer
        if len(data) < 10 or data[:3] != b"\x00\x00\x00":
            return False
        body = data[10:] if data[3] == 0x01 else data  # skip header for ATYP v4
        return body[:2] == b"\x53\x6b" and len(body) > 12 and (body[7] > 0)
    except Exception:
        return False
    finally:
        if ctrl:
            try:
                ctrl.close()
            except Exception:
                pass


def expand_targets(spec: str, ports: list[int]) -> list[str]:
    """Turn a CIDR / range / host into host:port candidates.

    Accepts: 203.0.113.0/24 · 203.0.113.1-203.0.113.50 · 203.0.113.7 · a file of any.
    """
    hosts: list[str] = []
    spec = spec.strip()
    if os.path.exists(spec):
        with open(spec) as f:
            for line in f:
                hosts += expand_hosts(line.strip())
    else:
        hosts = expand_hosts(spec)
    return [f"{h}:{p}" for h in hosts for p in ports]


def expand_hosts(spec: str) -> list[str]:
    if not spec or spec.startswith("#"):
        return []
    if "/" in spec:
        net = ipaddress.ip_network(spec, strict=False)
        if net.num_addresses > 65536:
            raise ValueError(f"{spec} is {net.num_addresses} addresses — "
                             "scan a /16 or smaller, in pieces")
        return [str(h) for h in net.hosts()]
    if "-" in spec and spec.count(".") >= 3:
        a, b = spec.split("-", 1)
        start = int(ipaddress.ip_address(a.strip()))
        end = int(ipaddress.ip_address(b.strip() if "." in b else a.rsplit(".", 1)[0] + "." + b.strip()))
        if not 0 <= end - start <= 65536:
            raise ValueError(f"{spec} spans too many addresses")
        return [str(ipaddress.ip_address(i)) for i in range(start, end + 1)]
    return [spec]


def scan(targets: list[str], workers: int, timeout: float,
         progress: bool = False, types: list[str] = None) -> list[str]:
    """Find host:port pairs that behave as a proxy. Returns typed candidates.

    Each host:port is probed for every requested type; a port that answers as
    both socks5 and http yields two candidates, each verified separately later.
    """
    types = types or ["socks5"]
    found: list[str] = []
    done = 0
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {}
        for t in targets:
            host, _, port = t.rpartition(":")
            for ptype in types:
                futs[ex.submit(_proxy_open, ptype, host, int(port), timeout)] = \
                    f"{ptype}://{host}:{port}"
        total = len(futs)
        for f in futures.as_completed(futs):
            done += 1
            try:
                if f.result():
                    found.append(futs[f])
            except Exception:
                pass
            if progress and done % 2000 == 0:
                print(f"  … {done:,}/{total:,} knocked, {len(found)} open",
                      file=sys.stderr, flush=True)
    return sorted(found)


def classify_anonymity(res: list[Result], workers: int, timeout: float,
                       progress: bool = False) -> None:
    """Fill in each result's anonymity level, in place. One judge trip per proxy."""
    real = real_ext_ip(timeout)
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(anonymity_of, r.proxy, timeout, real): r for r in res}
        for f in futures.as_completed(futs):
            try:
                futs[f].anonymity = f.result()
            except Exception:
                futs[f].anonymity = "?"
    if progress:
        from collections import Counter
        c = Counter(r.anonymity for r in res)
        print("   anonymity: " + ", ".join(f"{k} {v}" for k, v in c.most_common()),
              file=sys.stderr, flush=True)


def test_udp(res: list[Result], workers: int, timeout: float) -> None:
    """Fill in each SOCKS5 result's udp field. Non-socks5 proxies can't do it."""
    def one(r: Result):
        if r.ptype != "socks5":
            r.udp = "n/a"
            return
        _, h, p = split_scheme(r.proxy)
        r.udp = "yes" if socks5_udp_works(h, p, timeout) else "no"
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, res))


def hunt(proxies: list[str], target: str, workers: int, timeout: float,
         strict: bool, progress: bool = False, history: bool = True,
         anonymity: bool = False, udp: bool = False) -> list[Result]:
    out: list[Result] = []
    done = 0
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check, p, target, timeout, strict): p for p in proxies}
        for f in futures.as_completed(futs):
            done += 1
            try:
                r = f.result()
            except Exception:
                r = None
            if r:
                out.append(r)
            if progress and done % 500 == 0:
                print(f"  … {done}/{len(proxies)} tested, {len(out)} alive",
                      file=sys.stderr, flush=True)
    if anonymity and out:
        classify_anonymity(out, workers, timeout, progress=progress)
    if udp and out:
        test_udp(out, workers, timeout)
    if history:
        h = load_history()
        record(h, proxies, out)
        save_history(h)
    out.sort(key=lambda r: r.latency)
    return out


def add_countries(res: list[Result], timeout: float = 10.0) -> None:
    """Fill in the country of each proxy, in batches, from a free endpoint.

    Opt-in: it is one more network round-trip and the service rate-limits, so it
    is not worth paying for unless you actually want to pick proxies by country.
    """
    import urllib.request
    for i in range(0, len(res), 100):
        chunk = res[i:i + 100]
        body = json.dumps([{"query": r.addr.split(":")[0], "fields": "countryCode,query"}
                           for r in chunk]).encode()
        try:
            req = urllib.request.Request("http://ip-api.com/batch", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            by_ip = {d.get("query"): d.get("countryCode", "") for d in data if isinstance(d, dict)}
            for r in chunk:
                r.country = by_ip.get(r.addr.split(":")[0], "") or ""
        except Exception:
            return  # best effort: a missing country never invalidates a proxy


def _parse_types(spec: str, ap) -> list[str]:
    if spec.strip().lower() == "all":
        return list(PROXY_TYPES)
    types = [t.strip().lower() for t in spec.split(",") if t.strip()]
    for t in types:
        if t not in CONNECTORS:
            ap.error(f"unknown proxy type '{t}' (choose from {', '.join(PROXY_TYPES)}, or all)")
    return types or ["socks5"]


def _read_infile(path: str, types: list[str]) -> list[str]:
    """Read a proxy list. Lines may carry a scheme ('http://ip:port') or be bare
    'ip:port', in which case each requested type is tried."""
    default_types = types or ["socks5"]
    out: set[str] = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "://" in line:
                scheme = line.split("://", 1)[0].lower()
                m = IPPORT_RX.search(line)
                if m and scheme in CONNECTORS:
                    out.add(f"{scheme}://{m.group(0)}")
            else:
                m = IPPORT_RX.search(line)
                if m:
                    for t in default_types:
                        out.add(f"{t}://{m.group(0)}")
    return sorted(out)


def _watch(a, log) -> int:
    """Keep --out permanently true.

    Free proxies rot within minutes, so a file written once is a lie by the time
    you read it. This re-hunts on a loop and rewrites the file, so whatever is on
    disk was verified minutes ago at worst. Ctrl-C to stop.
    """
    if a.out == "-":
        print("--watch needs --out FILE", file=sys.stderr)
        return 2
    every = max(30.0, a.watch * 60)
    prev: set[str] = set()
    run = 0
    while True:
        run += 1
        t0 = time.time()
        proxies = collect(getattr(a, 'types', ['socks5']))
        res = hunt(proxies, a.target, a.workers, a.timeout, not a.no_strict,
                   history=not a.no_history)
        if a.max_latency:
            res = [r for r in res if r.latency <= a.max_latency]
        if a.country or a.only_country:
            add_countries(res)
            if a.only_country:
                want = {c.strip().upper() for c in a.only_country.split(",") if c.strip()}
                res = [r for r in res if r.country in want]
        now = {r.proxy for r in res}
        died = len(prev - now) if prev else 0
        with open(a.out, "w") as f:
            f.write(render(res, "json" if a.as_json else a.format) + "\n")
        log(f"[run {run}] {len(res)} live · {len(proxies):,} tested in {time.time()-t0:.0f}s"
            + (f" · {died} of last run's {len(prev)} died ({100*died/len(prev):.0f}%)" if prev else "")
            + f" · next in {every/60:.0f} min")
        prev = now
        try:
            time.sleep(every)
        except KeyboardInterrupt:
            log("stopped")
            return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="sockrates",
        description="Find open SOCKS5 proxies that really reach a target (Telegram included).")
    ap.add_argument("--target", default="telegram-bot",
                    help=f"what to verify against: {', '.join(TARGETS)}, or host:port")
    ap.add_argument("--tls", metavar="SNI",
                    help="for a custom host:port target, complete a TLS handshake with this SNI")
    ap.add_argument("--cert-contains", metavar="TEXT",
                    help="require the certificate to mention TEXT (implies --tls)")
    ap.add_argument("--in", dest="infile", help="test this file instead of downloading lists")
    ap.add_argument("--type", default="socks5", metavar="LIST",
                    help="proxy types to hunt, comma-separated: "
                         f"{', '.join(PROXY_TYPES)}, or 'all' (default: socks5)")
    ap.add_argument("--scan", metavar="RANGE",
                    help="discover proxies by scanning a CIDR / range / host instead of using "
                         "public lists, e.g. 203.0.113.0/24. Only scan what you may.")
    ap.add_argument("--ports", metavar="LIST",
                    help="comma-separated ports for --scan (default: common SOCKS5 ports)")
    ap.add_argument("--out", default="-", help="where to write the good ones ('-' = stdout)")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="shorthand for --format json")
    ap.add_argument("--format", default="plain", choices=sorted(FORMATS),
                    help="output format: " + " · ".join(f"{k} ({v[2]})" for k, v in FORMATS.items()))
    ap.add_argument("--workers", type=int, default=600)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--max-latency", type=float, default=0.0, help="drop slower ones (0 = keep all)")
    ap.add_argument("--min-age", type=float, default=0.0, metavar="HOURS",
                    help="only proxies we have known to work for at least this long")
    ap.add_argument("--anonymity", action="store_true",
                    help="also classify each proxy as transparent / anonymous / elite "
                         "(one extra judge request per proxy)")
    ap.add_argument("--only-elite", action="store_true",
                    help="keep only elite proxies (implies --anonymity)")
    ap.add_argument("--udp", action="store_true",
                    help="also test whether each SOCKS5 proxy relays UDP (UDP ASSOCIATE)")
    ap.add_argument("--min-reliability", type=float, default=0.0, metavar="PCT",
                    help="only proxies that passed at least PCT%% of our past checks")
    ap.add_argument("--no-history", action="store_true",
                    help="do not read or write ~/.sockrates/history.json")
    ap.add_argument("--limit", type=int, default=0, help="test at most N proxies (0 = all)")
    ap.add_argument("--no-strict", action="store_true",
                    help="skip the liar control (faster, lower quality)")
    ap.add_argument("--country", action="store_true",
                    help="look up each proxy's country (one extra call per 100)")
    ap.add_argument("--only-country", metavar="CC",
                    help="keep only these country codes, comma separated (implies --country)")
    ap.add_argument("--watch", type=float, default=0, metavar="MIN",
                    help="never stop: re-hunt every MIN minutes and keep --out true. "
                         "A list is only as good as the minute it was verified in.")
    ap.add_argument("--update", action="store_true",
                    help="update Sockrates in place (git pull / pipx / pip, as appropriate)")
    ap.add_argument("--gui", action="store_true",
                    help="open the desktop app instead of running in the terminal")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    if a.update:
        upd = check_for_update()
        if upd:
            print(f"→ {upd[0]} is available (you have {__version__})")
        ok, msg = apply_update()
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1

    # One executable, two faces: the terminal for scripts and cron, the desktop
    # app for picking through results by hand.
    if a.gui:
        try:
            import sockrates_gui
        except ImportError as e:
            print(f"GUI unavailable: {e}\n"
                  "Tkinter ships with Python but some distros split it out:\n"
                  "  Debian/Ubuntu: sudo apt install python3-tk\n"
                  "  Fedora:        sudo dnf install python3-tkinter\n"
                  "  Arch:          sudo pacman -S tk", file=sys.stderr)
            return 3
        return sockrates_gui.main()

    if a.target not in TARGETS:
        if ":" not in a.target:
            ap.error(f"unknown target '{a.target}'")
        h, _, p = a.target.rpartition(":")
        TARGETS[a.target] = (h, int(p), a.tls or (h if a.cert_contains else None), a.cert_contains)

    log = (lambda *x: None) if a.quiet else (lambda *x: print(*x, file=sys.stderr, flush=True))

    a.types = _parse_types(a.type, ap)

    if a.watch:
        return _watch(a, log)

    t0 = time.time()
    if a.scan:
        ports = ([int(x) for x in a.ports.split(",") if x.strip()] if a.ports else SOCKS5_PORTS)
        try:
            targets = expand_targets(a.scan, ports)
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
        log(f"🔭 scanning {a.scan} — {len(targets):,} host:port pairs on {len(ports)} port(s)")
        log("   ⚠️  only scan ranges you own or are authorised to test")
        proxies = scan(targets, a.workers, min(a.timeout, 4.0), progress=not a.quiet,
                       types=a.types)
        log(f"   {len(proxies)} open proxy port(s) [{', '.join(a.types)}] in "
            f"{time.time()-t0:.1f}s — now verifying each really works")
    elif a.infile:
        proxies = _read_infile(a.infile, a.types)
        log(f"📥 {len(proxies):,} proxies from {a.infile}")
    else:
        nsrc = sum(len(SOURCES.get(t, [])) for t in a.types)
        log(f"📥 collecting {', '.join(a.types)} from {nsrc} sources…")
        proxies = collect(a.types, verbose=not a.quiet)
        log(f"   {len(proxies):,} unique in {time.time()-t0:.1f}s")
    if a.limit:
        proxies = proxies[:a.limit]
    if not proxies:
        log("nothing to test")
        return 1

    log(f"🎯 testing against '{a.target}' "
        f"({TARGETS[a.target][0]}:{TARGETS[a.target][1]}), "
        f"{'strict' if not a.no_strict else 'no liar control'}")
    t1 = time.time()
    res = hunt(proxies, a.target, a.workers, a.timeout, not a.no_strict,
               progress=not a.quiet, history=not a.no_history,
               anonymity=a.anonymity or a.only_elite, udp=a.udp)
    if a.max_latency:
        res = [r for r in res if r.latency <= a.max_latency]
    if a.min_age:
        res = [r for r in res if r.age_h >= a.min_age]
    if a.min_reliability:
        res = [r for r in res if 100 * r.reliability >= a.min_reliability]
    if a.only_elite:
        res = [r for r in res if r.anonymity == "elite"]

    if a.country or a.only_country:
        add_countries(res)
        if a.only_country:
            want = {c.strip().upper() for c in a.only_country.split(",") if c.strip()}
            res = [r for r in res if r.country in want]

    took = time.time() - t1
    rate = 100.0 * len(res) / max(len(proxies), 1)
    log(f"✅ {len(res)} good out of {len(proxies):,} ({rate:.2f}%) in {took:.1f}s")
    if res:
        log(f"   fastest {res[0].latency:.2f}s · median {res[len(res)//2].latency:.2f}s")
        veterans = [r for r in res if r.age_h >= 24]
        if veterans:
            log(f"   {len(veterans)} have been working for over a day "
                f"(oldest {max(r.age_label for r in veterans)})")

    if res and (a.country or a.only_country):
        from collections import Counter
        top = Counter(r.country or "??" for r in res).most_common(6)
        log("   countries: " + ", ".join(f"{c} {n}" for c, n in top))

    body = render(res, "json" if a.as_json else a.format)
    if a.out == "-":
        print(body)
    else:
        with open(a.out, "w") as f:
            f.write(body + "\n")
        log(f"💾 {a.out}")
    return 0 if res else 2


if __name__ == "__main__":
    sys.exit(main())
