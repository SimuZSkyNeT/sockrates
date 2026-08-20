# Command line reference

```
python3 sockrates.py [options]
```

Exit codes: `0` found something · `1` nothing to test · `2` tested but found nothing ·
`3` GUI requested but Tkinter missing.

## Target

| flag | default | meaning |
|---|---|---|
| `--target NAME\|HOST:PORT` | `telegram-bot` | `telegram-bot`, `telegram-mtproto`, `https`, or any `host:port` |
| `--tls SNI` | — | for a custom target, complete a TLS handshake with this SNI |
| `--cert-contains TEXT` | — | require the certificate to mention TEXT (implies TLS) |

```bash
python3 sockrates.py --target telegram-mtproto
python3 sockrates.py --target api.example.com:443 --cert-contains example.com
python3 sockrates.py --target 10.0.0.5:1080          # plain TCP reachability
```

## Input and output

| flag | default | meaning |
|---|---|---|
| `--type LIST` | socks5 | proxy types to hunt: `socks5,socks4,http` or `all` |
| `--in FILE` | — | re-test an existing list instead of downloading |
| `--scan RANGE` | — | discover proxies by scanning a CIDR / range / host instead of lists |
| `--ports LIST` | common SOCKS5 ports | comma-separated ports for `--scan` |
| `--out FILE` | `-` (stdout) | where to write |
| `--format NAME` | `plain` | `plain`, `uri`, `csv`, `json`, `proxychains`, `python`, `curl` |
| `--json` | — | shorthand for `--format json` |

## Filters

| flag | default | meaning |
|---|---|---|
| `--max-latency S` | `0` (off) | drop anything slower than S seconds |
| `--min-age HOURS` | `0` (off) | only proxies known to work for at least this long |
| `--min-reliability PCT` | `0` (off) | only proxies that passed at least PCT% of past checks |
| `--country` | off | look up each proxy's country (one call per 100) |
| `--anonymity` | off | grade each proxy transparent / anonymous / elite |
| `--only-elite` | off | keep only elite proxies (implies `--anonymity`) |
| `--only-country CC,CC` | — | keep only these countries (implies `--country`) |
| `--limit N` | `0` (all) | test at most N candidates |

## Behaviour

| flag | default | meaning |
|---|---|---|
| `--workers N` | `600` | concurrent checks |
| `--timeout S` | `8.0` | per-proxy timeout |
| `--no-strict` | off | skip the liar control — faster, worse results |
| `--no-history` | off | do not read or write `~/.sockrates/history.json` |
| `--watch MIN` | off | never stop: re-hunt every MIN minutes, rewriting `--out` |
| `--update` | off | update in place (git pull / pipx / pip, per how it was installed) |
| `--gui` | off | open the desktop app instead |
| `--quiet` | off | no progress on stderr |

## Scanning

Instead of reading public lists, `--scan` finds proxies nobody has published yet: it enumerates
a range, knocks on the ports SOCKS5 usually lives on, and every open port then goes through the
**same** cross-examination as a listed proxy — an open port is not a working proxy until it
proves it.

```bash
python3 sockrates.py --scan 203.0.113.0/24 --target telegram-mtproto --out found.txt
python3 sockrates.py --scan 203.0.113.1-203.0.113.50 --ports 1080,1081,9050
python3 sockrates.py --scan ranges.txt --target https   # a file of CIDRs/ranges
```

Accepted forms: a CIDR (`203.0.113.0/24`), an inclusive range (`.1-.50`), a single host, or a
file containing any of these. A `/16` is the largest it will expand in one call.

> ⚠️ **Only scan ranges you own or are explicitly authorised to test.** Reaching out to
> machines that never advertised themselves is treated as unauthorised access in some
> jurisdictions regardless of intent. Sockrates keeps the default rate gentle and refuses
> anything larger than a `/16`, but the responsibility for *where* you point it is yours.

## Recipes

**Keep a file permanently true.** The point of `--watch`: whatever is on disk was verified
minutes ago at worst, and each run reports how many died since the last one.

```bash
python3 sockrates.py --target telegram-mtproto --watch 10 --out /var/lib/live.txt
```

**As a systemd service.**

```ini
[Unit]
Description=Sockrates — keep a verified SOCKS5 list fresh
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/sockrates/sockrates.py \
          --target telegram-mtproto --watch 10 --quiet \
          --out /var/lib/sockrates/live.txt
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
```

**Only the battle-tested ones.** Empty on a first run — the record needs a few hours of
`--watch` before it means anything.

```bash
python3 sockrates.py --min-age 24 --min-reliability 80 --format csv --out proven.csv
```

**Feed it into proxychains.**

```bash
python3 sockrates.py --target https --max-latency 1 --format proxychains --out /tmp/pc
# paste /tmp/pc under [ProxyList] in /etc/proxychains.conf
```

**Re-verify a list you already have**, keeping only what still answers:

```bash
python3 sockrates.py --in old.txt --out still-alive.txt
```

**Use it as a library.**

```python
import sockrates as sk

candidates = sk.collect(sk.SOURCES_SOCKS5)
alive = sk.hunt(candidates, "telegram-mtproto", workers=600, timeout=6, strict=True)
print(sk.render(alive, "uri"))
```
