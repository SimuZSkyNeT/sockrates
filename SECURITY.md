# Security and responsible use

## What this tool is

By default Sockrates verifies proxies that **already advertise themselves** on public lists,
one short connection per candidate. It can **also** scan IP ranges you explicitly give it
(`--scan`) to discover unpublished proxies — a deliberate, opt-in action, never the default,
capped at a `/16` per call, with no facility to sweep the internet at large.

**Only scan ranges you own or are authorised to test.** Unsolicited port scanning is treated
as unauthorised access in some jurisdictions regardless of intent. Where you point `--scan` is
your responsibility, not the tool's.

## What you should know before using the results

An open SOCKS5 proxy is someone else's machine, and its operator can see everything that passes
through it.

- **Encrypted end to end?** They still see who you connect to, from where, and when.
- **Not encrypted?** They can read it, log it, and change it in flight. Never send credentials,
  tokens or session data over an unencrypted connection through a proxy you found on a list.
- **Many open proxies are open by accident** — a misconfiguration, not an invitation. Some are
  open on purpose, to collect exactly the traffic that people like you send through them.

Treat every proxy in the output as hostile infrastructure that happens to forward packets.

## Legality

Whether you may use an open proxy depends on where you are and whose machine it is. Some
jurisdictions treat using a misconfigured service without permission as unauthorised access
regardless of how easy it was. This project takes no position on your situation and provides
no legal advice — **check before you rely on it.**

Do not use these proxies to attack or flood anything, to evade a ban you earned, or to
impersonate someone.

## Reporting a vulnerability

Bugs in Sockrates itself — a crash on malformed input, a way to make it connect somewhere it
was not asked to, a leak of the history file — should be reported privately by opening a
[security advisory](https://github.com/SimuZSkyNeT/sockrates/security/advisories/new) rather
than a public issue.

Please do **not** report "this proxy in my output was dead". Proxies die constantly; that is
why the tool re-verifies. See the freshness section in the README.

## Data it keeps

`~/.sockrates/history.json` — the proxies seen and how they performed. `~/.sockrates.json` —
the app's last settings. Nothing is sent anywhere except:

- the proxy sources you enable, which are fetched;
- `ip-api.com`, only when country lookup is on, and only proxy addresses are sent;
- `raw.githubusercontent.com`, only when the app's update check is enabled, to read the
  published changelog. It sends nothing but the request. Turn it off under **About**.
