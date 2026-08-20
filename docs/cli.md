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
| `--in FILE` | — | re-test an existing list instead of downloading |
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
| `--gui` | off | open the desktop app instead |
| `--quiet` | off | no progress on stderr |

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
