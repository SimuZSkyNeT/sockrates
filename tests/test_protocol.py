#!/usr/bin/env python3
"""Self-test for the wire protocols, against a local server that speaks them back.

CI cannot assert anything about real proxies — they change by the minute. What it
can pin down is the framing: that we negotiate SOCKS5 correctly, that we reject a
refusal, and that the MTProto handshake accepts a genuine resPQ and nothing else.
"""
import os
import socket
import struct
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sockrates as sk  # noqa: E402

FAILS = []


def check(name, cond):
    print(("  ok   " if cond else "  FAIL ") + name)
    if not cond:
        FAILS.append(name)


def serve(handler) -> tuple[str, int, threading.Thread]:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    host, port = srv.getsockname()

    def run():
        try:
            conn, _ = srv.accept()
            with conn:
                handler(conn)
        except Exception:
            pass
        finally:
            srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return host, port, t


def socks5_ok(conn, then=None):
    """Accept the greeting and grant the CONNECT."""
    assert conn.recv(3) == b"\x05\x01\x00"
    conn.sendall(b"\x05\x00")
    conn.recv(256)  # the CONNECT request
    conn.sendall(b"\x05\x00\x00\x01" + b"\x00\x00\x00\x00" + struct.pack(">H", 0))
    if then:
        then(conn)


def test_connect_granted():
    host, port, _ = serve(socks5_ok)
    try:
        s = sk.socks5_connect(host, port, "example.com", 443, 5)
        s.close()
        check("SOCKS5 CONNECT accepted", True)
    except Exception as e:
        check(f"SOCKS5 CONNECT accepted ({e})", False)


def test_connect_refused():
    def refuse(conn):
        assert conn.recv(3) == b"\x05\x01\x00"
        conn.sendall(b"\x05\x00")
        conn.recv(256)
        conn.sendall(b"\x05\x05\x00\x01" + b"\x00" * 6)   # 0x05 = connection refused
    host, port, _ = serve(refuse)
    try:
        sk.socks5_connect(host, port, "example.com", 443, 5)
        check("SOCKS5 refusal is raised", False)
    except OSError:
        check("SOCKS5 refusal is raised", True)


def test_auth_required():
    def need_auth(conn):
        conn.recv(3)
        conn.sendall(b"\x05\x02")   # username/password required
    host, port, _ = serve(need_auth)
    try:
        sk.socks5_connect(host, port, "example.com", 443, 5)
        check("proxies demanding auth are rejected", False)
    except OSError:
        check("proxies demanding auth are rejected", True)


def _mtproto_reply(conn, constructor: int, echo_nonce: bool):
    first = conn.recv(1)
    assert first == b"\xef"
    head = conn.recv(1)
    n = head[0]
    body = conn.recv(n * 4)
    nonce = body[24:40] if echo_nonce else os.urandom(16)
    payload = (struct.pack("<qq", 0, 0) + struct.pack("<I", 20)
               + struct.pack("<I", constructor) + nonce)
    payload += b"\x00" * ((-len(payload)) % 4)
    conn.sendall(bytes([len(payload) // 4]) + payload)


def test_mtproto_genuine():
    host, port, _ = serve(lambda c: socks5_ok(
        c, lambda cc: _mtproto_reply(cc, 0x05162463, True)))
    s = sk.socks5_connect(host, port, "example.com", 443, 5)
    check("genuine resPQ is accepted", sk.mtproto_handshake(s, 5) is True)
    s.close()


def test_mtproto_wrong_constructor():
    host, port, _ = serve(lambda c: socks5_ok(
        c, lambda cc: _mtproto_reply(cc, 0xDEADBEEF, True)))
    s = sk.socks5_connect(host, port, "example.com", 443, 5)
    check("a wrong constructor is rejected", sk.mtproto_handshake(s, 5) is False)
    s.close()


def test_mtproto_wrong_nonce():
    host, port, _ = serve(lambda c: socks5_ok(
        c, lambda cc: _mtproto_reply(cc, 0x05162463, False)))
    s = sk.socks5_connect(host, port, "example.com", 443, 5)
    check("a replayed nonce is rejected", sk.mtproto_handshake(s, 5) is False)
    s.close()


def test_formats():
    r = sk.Result(proxy="socks5://1.2.3.4:1080", latency=0.5, target="telegram-mtproto",
                  verified="mtproto", country="NL", age_h=30, reliability=0.9, checks=10,
                  ptype="socks5")
    check("plain format", sk.render([r], "plain") == "1.2.3.4:1080")
    check("uri format", sk.render([r], "uri") == "socks5://1.2.3.4:1080")
    check("proxychains format", "socks5 1.2.3.4 1080" in sk.render([r], "proxychains"))
    check("csv carries the record", "90,10" in sk.render([r], "csv"))
    # minutes under an hour, hours up to two days, days after that
    check("age is human", (r.age_label == "30h"
                           and sk.Result("p", 0, "t", "tcp", age_h=0.5).age_label == "30m"
                           and sk.Result("p", 0, "t", "tcp", age_h=72).age_label == "3d"))
    check("every format renders", all(sk.render([r], k) for k in sk.FORMATS))


def test_proxy_types():
    # the scheme drives which format keyword/URI comes out
    h = sk.Result(proxy="http://5.6.7.8:8080", latency=0.2, target="https",
                  verified="tls-cert", ptype="http")
    s4 = sk.Result(proxy="socks4://9.9.9.9:1080", latency=0.3, target="https",
                   verified="tls-cert", ptype="socks4")
    check("http uri", sk.render([h], "uri") == "http://5.6.7.8:8080")
    check("http proxychains", "http 5.6.7.8 8080" in sk.render([h], "proxychains"))
    check("http pysocks", "socks.HTTP" in sk.render([h], "python"))
    check("socks4 uri", sk.render([s4], "uri") == "socks4://9.9.9.9:1080")
    check("socks4 proxychains", "socks4 9.9.9.9 1080" in sk.render([s4], "proxychains"))
    check("addr strips scheme", h.addr == "5.6.7.8:8080")
    check("split_scheme parses", sk.split_scheme("http://5.6.7.8:8080") == ("http", "5.6.7.8", 8080))
    check("split_scheme defaults socks5", sk.split_scheme("1.2.3.4:1080") == ("socks5", "1.2.3.4", 1080))


def test_socks4_and_http_connect():
    # a SOCKS4 server that grants the request → connect returns a socket
    def s4_grant(conn):
        conn.recv(64)
        conn.sendall(b"\x00\x5a" + b"\x00" * 6)   # request granted
    host, port, _ = serve(s4_grant)
    try:
        sk.socks4_connect(host, port, "1.1.1.1", 80, 5).close()
        check("SOCKS4 grant accepted", True)
    except Exception as e:
        check(f"SOCKS4 grant accepted ({e})", False)

    def s4_reject(conn):
        conn.recv(64)
        conn.sendall(b"\x00\x5b" + b"\x00" * 6)   # rejected
    host, port, _ = serve(s4_reject)
    try:
        sk.socks4_connect(host, port, "1.1.1.1", 80, 5)
        check("SOCKS4 rejection is raised", False)
    except OSError:
        check("SOCKS4 rejection is raised", True)

    def http_ok(conn):
        conn.recv(256)
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
    host, port, _ = serve(http_ok)
    try:
        sk.http_connect(host, port, "1.1.1.1", 80, 5).close()
        check("HTTP CONNECT 200 accepted", True)
    except Exception as e:
        check(f"HTTP CONNECT 200 accepted ({e})", False)

    def http_deny(conn):
        conn.recv(256)
        conn.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
    host, port, _ = serve(http_deny)
    try:
        sk.http_connect(host, port, "1.1.1.1", 80, 5)
        check("HTTP CONNECT refusal is raised", False)
    except OSError:
        check("HTTP CONNECT refusal is raised", True)


def test_scan_detects_socks5():
    """The port-knock must recognise a SOCKS5 greeting and reject anything else."""
    host, port, _ = serve(lambda c: (c.recv(3), c.sendall(b"\x05\x00")))
    check("scan detects an open SOCKS5 port", sk._socks5_open(host, port, 5) is True)

    # a server that answers something that is not SOCKS5 must be rejected
    host, port, _ = serve(lambda c: (c.recv(3), c.sendall(b"HTTP")))
    check("scan rejects a non-SOCKS5 port", sk._socks5_open(host, port, 5) is False)

    check("scan rejects a closed port", sk._socks5_open("127.0.0.1", 1, 1) is False)


def test_expand_hosts():
    check("CIDR expands", len(sk.expand_hosts("203.0.113.0/30")) == 2)
    check("range expands", len(sk.expand_hosts("203.0.113.1-203.0.113.10")) == 10)
    check("single host", sk.expand_hosts("203.0.113.7") == ["203.0.113.7"])
    try:
        sk.expand_hosts("10.0.0.0/8")   # 16M addresses
        check("oversized CIDR is refused", False)
    except ValueError:
        check("oversized CIDR is refused", True)


def test_anonymity_classify():
    import json as _json
    real = "9.9.9.9"

    def judge(headers: dict, origin: str):
        def h(conn):
            conn.recv(4096)
            body = _json.dumps({"headers": headers, "origin": origin}).encode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         b"Connection: close\r\n\r\n" + body)
        return h

    # socks5 tunnel to a judge that echoes our real IP → transparent
    def s5_then(handler):
        def h(conn):
            socks5_ok(conn, handler)
        return h
    host, port, _ = serve(s5_then(judge({"Host": "j"}, "9.9.9.9")))
    check("transparent detected",
          sk.anonymity_of(f"socks5://{host}:{port}", 5, real) == "transparent")

    host, port, _ = serve(s5_then(judge({"Via": "1.1 proxy"}, "5.5.5.5")))
    check("anonymous detected (proxy header, IP hidden)",
          sk.anonymity_of(f"socks5://{host}:{port}", 5, real) == "anonymous")

    host, port, _ = serve(s5_then(judge({"Host": "j", "Accept": "*"}, "5.5.5.5")))
    check("elite detected (no leak, no proxy header)",
          sk.anonymity_of(f"socks5://{host}:{port}", 5, real) == "elite")

    check("unreachable judge is '?'",
          sk.anonymity_of("socks5://127.0.0.1:1", 1, real) == "?")


def test_udp_associate():
    import struct as _st
    # a SOCKS5 server that associates UDP and a UDP relay that answers a DNS query
    def udp_relay():
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.bind(("127.0.0.1", 0))
        return u

    relay = udp_relay()
    rhost, rport = relay.getsockname()

    def s5_udp(conn):
        assert conn.recv(3) == b"\x05\x01\x00"
        conn.sendall(b"\x05\x00")
        conn.recv(256)  # UDP ASSOCIATE request
        conn.sendall(b"\x05\x00\x00\x01" + socket.inet_aton(rhost) + _st.pack(">H", rport))
        # keep control socket open, then serve one UDP datagram
        data, addr = relay.recvfrom(2048)
        # echo back a minimal SOCKS5 UDP reply with a fake DNS answer (id + AN=1)
        dns = b"\x53\x6b\x81\x80\x00\x01\x00\x01" + b"\x00" * 20
        relay.sendto(b"\x00\x00\x00\x01" + socket.inet_aton("8.8.8.8")
                     + _st.pack(">H", 53) + dns, addr)
        try:
            conn.recv(1)
        except Exception:
            pass

    host, port, _ = serve(s5_udp)
    check("SOCKS5 UDP relay detected", sk.socks5_udp_works(host, port, 5) is True)
    relay.close()

    # a server that refuses UDP ASSOCIATE (cmd not supported)
    def s5_no_udp(conn):
        conn.recv(3)
        conn.sendall(b"\x05\x00")
        conn.recv(256)
        conn.sendall(b"\x05\x07\x00\x01" + b"\x00" * 6)   # 0x07 = not supported
    host, port, _ = serve(s5_no_udp)
    check("SOCKS5 UDP refusal detected", sk.socks5_udp_works(host, port, 3) is False)


def test_ewma_reliability():
    hist = {}
    p = "socks5://1.1.1.1:1080"
    r = lambda: [sk.Result(proxy=p, latency=0.1, target="t", verified="tcp")]
    # 3 alive then 2 dead: a lifetime ratio would be 3/5=60%, EWMA weights the
    # recent deaths harder, so stability should fall well below that.
    sk.record(hist, [p], r())
    sk.record(hist, [p], r())
    sk.record(hist, [p], r())
    sk.record(hist, [p], [])
    sk.record(hist, [p], [])
    stab = hist[p]["stab"]
    check("EWMA weights recent failures", stab < 0.6 and hist[p]["checks"] == 5)


def test_history_keeps_failures():
    """The score must not drift to 100% by forgetting the dead."""
    hist = {}
    alive = [sk.Result(proxy="1.1.1.1:1", latency=0.1, target="t", verified="tcp")]
    sk.record(hist, ["1.1.1.1:1", "2.2.2.2:2"], alive)
    sk.record(hist, ["1.1.1.1:1", "2.2.2.2:2"], [])
    check("failures are remembered", hist["2.2.2.2:2"]["checks"] == 2
          and hist["2.2.2.2:2"]["ok"] == 0)


if __name__ == "__main__":
    print("sockrates protocol self-test")
    for fn in (test_connect_granted, test_connect_refused, test_auth_required,
               test_socks4_and_http_connect,
               test_mtproto_genuine, test_mtproto_wrong_constructor,
               test_mtproto_wrong_nonce, test_scan_detects_socks5, test_expand_hosts,
               test_formats, test_proxy_types, test_anonymity_classify,
               test_udp_associate, test_ewma_reliability,
               test_history_keeps_failures):
        fn()
    print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all good'}")
    sys.exit(1 if FAILS else 0)
