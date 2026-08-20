# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-08-20

First release.

### Added
- **Scan mode** (`--scan`): discover proxies by scanning a CIDR / range / host you are
  authorised to test, instead of reading public lists. Every open port is then verified like
  any other candidate. Capped at a /16 per call.
- SOCKS5 hunting across 11 public sources — roughly 2,500 unique candidates in under a second.
- **Proof, not claims**: TLS handshake with certificate verification for HTTPS targets, a real
  MTProto `req_pq_multi` / `resPQ` exchange for Telegram datacenters, and a liar control that
  discards any proxy reporting success on an unroutable address.
- Separate Telegram targets for the Bot API and MTProto, because a proxy can serve one and
  refuse the other.
- A local track record (`~/.sockrates/history.json`): how long each proxy has been known to
  work and the share of checks it passed, with `--min-age` and `--min-reliability` to filter on.
- `--watch` mode: re-hunt on a loop and keep an output file permanently true, reporting how
  many died since the previous run.
- Seven export formats: plain, `socks5://` URIs, CSV, JSON, proxychains, PySocks/Telethon, curl.
- Country lookup and filtering.
- An **About** tab with the donation address and an update check that reads the published
  changelog, so it can show what a new version contains instead of just its number.
- Packages for Debian/Ubuntu (`.deb`), Fedora/RHEL/openSUSE (`.rpm`), Arch (`PKGBUILD`) and
  PyPI (wheel + sdist), a `Makefile` that builds them all, a man page, a desktop entry and
  icons — plus CI that builds and attaches them to each release.
- A Tkinter desktop app (`--gui`) with live results, sortable columns, source selection, a
  filter box, right-click actions, auto-refresh, persisted settings, and re-verification before
  every save or copy.
