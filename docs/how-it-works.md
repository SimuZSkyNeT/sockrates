# How it works

Sockrates is built on one idea: **a proxy's own report is not evidence.** Everything below
exists to turn a claim into a demonstration.

## The pipeline

```
sources ──▶ collect ──▶ cross-examine ──▶ record ──▶ export
            (~0.6s)      (~25s, 600 threads)  (history)   (7 formats)
```

### 1. Collect

Eleven public endpoints are fetched in sequence and scraped for `ip:port` pairs with a plain
regex. Sources that 404, hang, or change shape are skipped without stopping the run — these
lists rot constantly and a scraper that dies with them is useless.

Typical yield: **~2,500 unique candidates in under a second.**

### 2. Cross-examine

Each candidate goes through a SOCKS5 negotiation spoken directly over a socket. There is no
PySocks dependency: the protocol is a dozen bytes, and writing it out means we can see exactly
where a proxy fails.

```
→ 05 01 00                     version 5, one method, "no authentication"
← 05 00                        accepted
→ 05 01 00 <atyp> <addr> <port>  CONNECT
← 05 00 ...                    granted
```

Domain targets are sent as `ATYP=3`, so **the proxy resolves the name**. That is deliberate:
resolving locally would hide proxies whose network cannot reach the host at all.

Then the proof, which depends on the target:

**TLS targets** — we complete the handshake *through* the tunnel with the right SNI and read
the certificate back, requiring it to name the host we asked for. A proxy that faked the
connection cannot produce a valid certificate for `api.telegram.org`. Recorded as
`verified: tls-cert`.

**Telegram datacenters** — there is no TLS to inspect, so we speak MTProto:

```
→ ef                           abridged transport
→ [0][msg_id][len] be7e8ef1 <16-byte nonce>     req_pq_multi
← ...                          05162463 <same nonce> ...   resPQ
```

We require the constructor to be `resPQ` **and** the nonce to come back unchanged. Nothing
else on the internet answers that. Recorded as `verified: mtproto`.

**Anything else** — a bare TCP connect, recorded honestly as `verified: tcp`. It is the
weakest proof available and the output says so.

### 3. The liar control

Every candidate is additionally asked to connect to `192.0.2.1:65533` — TEST-NET-1, reserved
by [RFC 5737](https://www.rfc-editor.org/rfc/rfc5737) and unroutable by design. **A proxy that
reports success there is lying**, and would have lied about everything else too. It is dropped.

Disable with `--no-strict` if you want speed over truth.

### 4. The record

No SOCKS5 server exposes its uptime; there is no field for it. What *can* be known is what we
have observed, so Sockrates keeps a small history in `~/.sockrates/history.json`:

```json
{"1.2.3.4:1080": {"first": 1787..., "first_ok": 1787..., "last_ok": 1787...,
                  "last_seen": 1787..., "checks": 48, "ok": 45}}
```

From it come two columns that matter more than any label a public list prints:

- **Known for** — how long we have seen this proxy working (`12m`, `7h`, `3d`).
- **Reliability** — the share of our checks it passed, with the sample size: `94% of 48`.

Entries are forgotten after 14 days of not being *seen* — deliberately not "not being alive",
because pruning on the last success would erase every failure and drift all scores towards 100%.

Filter on the record with `--min-age HOURS` and `--min-reliability PCT`. On a first run these
are naturally empty; the record is worth something after a few hours of `--watch`.

### 5. Export

Latency is measured **to your target through the proxy**, not to the proxy itself, and results
are sorted by it. That single number is worth more than the "elite / anonymous / transparent"
labels public lists attach, which are unverifiable and frequently wrong.

## Why so much of it fails

Roughly 3–5% of a public SOCKS5 list survives all of this. The rest are, in order of
frequency: long dead; alive but refusing port 443; alive but unable to route to the target's
network; and liars. That number is not a defect of the sources — it is what the sources are.
