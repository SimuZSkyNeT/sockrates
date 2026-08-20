# Telegram targets

**"Works with Telegram" is not one property.** Telegram clients speak two entirely different
protocols to two different places, and a proxy can serve one and refuse the other.

## The two targets

| | `telegram-bot` | `telegram-mtproto` |
|---|---|---|
| Used by | Bot API clients (python-telegram-bot, aiogram, plain HTTPS) | User clients — Telethon, Pyrogram, the mobile and desktop apps |
| Speaks to | `api.telegram.org:443` | datacenter IPs, port 443 |
| Protocol | HTTPS | MTProto |
| How Sockrates proves it | TLS handshake + certificate must name `telegram.org` | `req_pq_multi` sent, valid `resPQ` with our nonce required |
| Recorded as | `verified: tls-cert` | `verified: mtproto` |

Measured on one run of the same 2,547 candidates:

| works for | count |
|---|---|
| Bot API only | 36 |
| MTProto only | 152 |
| both | 42 |

Only 42 of 230 serve both. **Pick the target you will actually use** — testing the wrong one
throws away most of what you found and keeps proxies that will fail in production.

## The datacenters

MTProto checks run against DC2 (Amsterdam) by default. The full set Sockrates knows:

| DC | address | location |
|---|---|---|
| DC1 | `149.154.175.50` | Miami |
| DC2 | `149.154.167.51` | Amsterdam |
| DC3 | `149.154.175.100` | Miami |
| DC4 | `149.154.167.91` | Amsterdam |
| DC5 | `91.108.56.130` | Singapore |

Port 443 is used because it survives restrictive networks that drop Telegram's other ports.
A proxy that reaches one datacenter can normally reach the others; if you need a specific one,
pass it as a custom target:

```bash
python3 sockrates.py --target 91.108.56.130:443
```

Custom targets matching a known datacenter address automatically get the MTProto proof rather
than a bare TCP connect.

## Using the results

**Telethon / Pyrogram** — export with `--format python` and paste:

```python
import socks
from telethon import TelegramClient

client = TelegramClient("session", api_id, api_hash,
                        proxy=(socks.SOCKS5, "1.2.3.4", 1080))
```

**Bot API** — export with `--format uri`:

```python
import httpx
client = httpx.Client(proxy="socks5://1.2.3.4:1080")   # pip install httpx[socks]
```

## A warning worth repeating

An open proxy operator sees every packet you send. MTProto and HTTPS are both encrypted, so
the *content* of your Telegram traffic is not readable by them — but they do see that you
connect to Telegram, from which IP, and when. If that metadata matters to you, an open proxy
you found on a public list is the wrong tool.

Telegram also has its own **MTProto proxy** format (`tg://proxy?...`, with a secret), which is
a different thing from a SOCKS5 proxy. Sockrates does not hunt for those.
