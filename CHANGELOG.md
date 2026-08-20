# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project follows [Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-08-21

### Added
- **All proxy types, not just SOCKS5.** Sockrates now hunts and verifies **SOCKS5, SOCKS4 and
  HTTP/HTTPS** proxies. Pick any mix with `--type socks5,http` (or `--type all`); the desktop
  app has a checkbox per type. Every type goes through the identical verification — TLS
  certificate check, MTProto handshake, liar control — only the tunnel differs. Output carries
  the scheme (`socks5://`, `http://`) in the uri/csv/json/proxychains/python formats.
- **More sources**, curated by measured hit rate rather than popularity: added fresh
  protocol-separated lists (yakumo checked lists, databay, iplocate, vakhov, vmheaven, Zaeem20)
  and *dropped* two high-star megadumps that verified at 0%.

## [0.2.3] — 2026-08-21

### Fixed
- Clearing the scan range and running now falls back to the public lists instead of demanding
  a range. Clicking a scan box selects scan mode; emptying it quietly returns to list mode.

## [0.2.2] — 2026-08-21

### Fixed
- **The scan Range/Ports and custom host:port fields could not be typed into.** They were
  disabled until you first picked the matching radio button, and a disabled field looks exactly
  like an active one — a dead black box. The fields are now always typeable; clicking or tabbing
  into one selects its mode for you.

## [0.2.1] — 2026-08-21

### Fixed
- **Could not type in the settings fields on some Linux window managers.** A click did not hand
  keyboard focus to the input, so the fields looked dead. Any click on a field now claims focus,
  and the window claims keyboard focus on launch.
- The numeric settings (workers, timeout, latency, refresh interval) now reject non-numeric
  input instead of silently accepting text that would break the next run.

## [0.2.0] — 2026-08-20

### Added
- **Scan mode** (`--scan`): discover proxies by scanning a CIDR / range / host you are
  authorised to test, instead of reading public lists. Every open port is then verified like
  any other candidate. Capped at a /16 per call, and the desktop app confirms before it starts.
- The desktop app grew a header with the wordmark, zebra-striped result rows, and the scan
  option in the Sources tab.

- **In-place update**: `sockrates --update` and an **Update now** button in the app update the
  tool the right way for how it was installed (git pull / pipx / pip), or print the package
  manager command for a system install.

### Fixed
- The scan port-knock now reads the SOCKS5 greeting with an exact-length read, so a reply
  split across packets is no longer mistaken for a refusal.

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
