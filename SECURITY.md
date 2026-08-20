# Security and responsible use

## What this tool is

Sockrates verifies proxies that **already advertise themselves** on public lists. It makes one
short connection per candidate to check a claim. It is not a port scanner: it does not sweep
address ranges, does not probe hosts nobody published, and does not attempt authentication.

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
- `ip-api.com`, only when country lookup is on, and only proxy addresses are sent.
