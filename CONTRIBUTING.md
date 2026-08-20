# Contributing

## The one rule

**Never loosen a proof.** Sockrates exists because other scrapers hand out proxies that do not
work. Any change that makes a result easier to obtain — skipping the certificate check,
dropping the liar control, accepting a TCP connect where a handshake is possible — defeats the
entire point, no matter how many more proxies it appears to find.

More is not better. Fewer and true is better.

## Adding a source

Sources go in `SOURCES_SOCKS5`. It must be a plain-text endpoint containing `ip:port` pairs;
the scraper regexes them out and ignores everything else, so most list formats work as-is.

Before opening a PR, show what it adds that we do not already have:

```bash
python3 - <<'EOF'
import sockrates as sk
old = set(sk.collect([u for u in sk.SOURCES_SOCKS5 if "yoursource" not in u]))
new = set(sk.collect(["https://your.source/socks5.txt"]))
print(f"{len(new)} found, {len(new - old)} not already covered")
EOF
```

A source that adds fewer than a few hundred unique entries is usually a mirror of one we
already read, and only costs a round-trip on every run.

## Adding a target

A target is `(host, port, sni_or_None, cert_needle_or_None)` in `TARGETS`. If the protocol
allows a real handshake — as MTProto does — implement it rather than settling for a TCP
connect, and give it its own `verified` label so the output stays honest about what was proven.

## Testing

There is no unit-test suite: the thing under test is the internet. What is expected before a
PR is evidence from a real run, on both faces:

```bash
python3 sockrates.py --target telegram-mtproto --limit 500 --timeout 5
python3 sockrates.py --gui
```

Paste the summary line into the PR. If you changed the verification logic, also paste a
before/after count — that number is the review.

## Style

- Standard library only. A dependency has to earn its place, and so far none has.
- Comments explain **why**, not what. The MTProto block is the model: the code shows what it
  sends, the comment says why anything less would not be proof.
- Keep the terminal and the app in step. A feature that only exists in one of them is a bug
  report waiting to happen.

## Reporting a bad result

The useful bug report is a proxy Sockrates said was good that was not — or the reverse. Include
the address, the target, and what actually happened when you used it. That is the only failure
mode that matters here.
