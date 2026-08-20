# The desktop app

```bash
python3 sockrates.py --gui
```

Tkinter, so nothing to install beyond Python itself — though some distributions ship it
separately (`apt install python3-tk`, `dnf install python3-tkinter`, `pacman -S tk`).

![Sockrates](screenshot.png)

## Target

The same four choices as `--target`, each spelling out what will be proven:

- **Telegram — user clients** · a real MTProto handshake against a datacenter
- **Telegram — Bot API** · HTTPS to `api.telegram.org`, certificate verified
- **Any HTTPS site** · a generic handshake
- **Custom host:port** · your own endpoint; leave the certificate box empty to accept a plain
  TCP connection

## Sources

Every public list, individually checkable, with *Select all* / *Select none*. Turning off a
source that has gone bad is faster than waiting for its timeout on every run.

## Tuning

| control | what it does |
|---|---|
| **Concurrent workers** | higher is faster and heavier; 600 is a sane default |
| **Timeout** | per proxy — too low silently drops slow but usable ones |
| **Max latency** | discard anything slower; `0` keeps everything |
| **Liar control** | discard proxies that fake success. Leave it on |
| **Look up country** | fills the Country column after the hunt |
| **Keep only countries** | e.g. `DE,NL,FR` |
| **Re-verify before every Save / Copy** | on by default — see below |
| **Re-hunt automatically every N minutes** | with an optional file to auto-save each run to |

## Never hand out a dead proxy

Free proxies rot in minutes, so anything the app gives you is re-tested **at the moment you
ask for it**: hit *Save* or *Copy* and every row is checked again, the dead ones are dropped,
and the status line tells you how many died since the hunt. Turn it off in *Tuning* if you
want the raw list instead.

## The table

Sortable by any column — click a heading, click again to reverse.

| column | meaning |
|---|---|
| **Proxy** | `ip:port` |
| **Latency** | measured **to your target through the proxy**. Green under 1s, amber over 3s |
| **Country** | filled after the hunt if enabled |
| **Proof** | `mtproto`, `tls-cert` or `tcp` — how strongly it was demonstrated |
| **Known for** | how long this proxy has been working, across every run you have done |
| **Reliability** | share of our checks it passed, with the sample size |

**Known for** and **Reliability** are empty on a first run and become the most useful columns
in the table once you have left *Re-hunt automatically* on for a few hours.

Right-click a row to copy it, copy it as a `socks5://` URI, or drop it from the list.
Double-click copies. With nothing selected, buttons act on everything currently shown —
which respects the **Filter** box, so filtering by `DE` and hitting Copy gives you the German
ones only.

## Export

*Save…* offers every format the CLI has: plain, `socks5://` URIs, CSV, JSON, a
`proxychains.conf` block, a ready-to-paste PySocks/Telethon list, or example `curl` commands.

## About

Version, the project link, and the donation address with a copy button — one EVM address that
works on every EVM chain.

It also holds **Check for updates on start**, on by default. It asks GitHub for the published
`CHANGELOG.md`, and if a newer version exists it shows you **what is in it** rather than just a
version number. The check runs off the main thread and stays silent when you are offline; turn
it off here if you would rather it never phoned home.

## Keyboard

| key | action |
|---|---|
| `Ctrl+R` | hunt |
| `Ctrl+S` | save |
| `Ctrl+C` | copy |
| `Esc` | stop |

Your setup — target, sources, tuning, everything — is written to `~/.sockrates.json` when you
close the window and restored next time.
