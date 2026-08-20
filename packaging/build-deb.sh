#!/usr/bin/env bash
# Build a .deb for Debian / Ubuntu / Mint / Pop!_OS.
# Hand-rolled rather than dh-python: the payload is two dependency-free modules,
# and a full debian/ tree would be more machinery than the thing it packages.
set -e
cd "$(dirname "$0")/.."

VER=$(grep -m1 '^__version__' sockrates.py | cut -d'"' -f2)
ARCH=all
OUT=dist
PKG="$OUT/sockrates_${VER}_${ARCH}"
rm -rf "$PKG"
mkdir -p "$PKG"/DEBIAN \
         "$PKG"/usr/bin \
         "$PKG"/usr/lib/python3/dist-packages \
         "$PKG"/usr/share/man/man1 \
         "$PKG"/usr/share/applications \
         "$PKG"/usr/share/doc/sockrates

install -m644 sockrates.py sockrates_gui.py "$PKG"/usr/lib/python3/dist-packages/

for name in sockrates sockrates-gui; do
    mod=$(echo "$name" | tr - _)
    cat > "$PKG/usr/bin/$name" <<EOF
#!/usr/bin/python3
import sys
from $mod import main
sys.exit(main())
EOF
    chmod 755 "$PKG/usr/bin/$name"
done

gzip -9nc packaging/sockrates.1 > "$PKG"/usr/share/man/man1/sockrates.1.gz
install -m644 packaging/sockrates.desktop "$PKG"/usr/share/applications/
for s in 16 24 32 48 64 128 256 512; do
    d="$PKG/usr/share/icons/hicolor/${s}x${s}/apps"
    mkdir -p "$d"
    install -m644 "packaging/icons/sockrates-$s.png" "$d/sockrates.png"
done
mkdir -p "$PKG"/usr/share/icons/hicolor/scalable/apps
install -m644 packaging/icons/sockrates.svg "$PKG"/usr/share/icons/hicolor/scalable/apps/
install -m644 README.md "$PKG"/usr/share/doc/sockrates/
gzip -9nc CHANGELOG.md > "$PKG"/usr/share/doc/sockrates/changelog.gz

cat > "$PKG"/usr/share/doc/sockrates/copyright <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: sockrates
Source: https://github.com/SimuZSkyNeT/sockrates

Files: *
Copyright: 2026 SimuZSkyNeT
License: Apache-2.0
 Licensed under the Apache License, Version 2.0. You may obtain a copy at
 <https://www.apache.org/licenses/LICENSE-2.0>, and on Debian systems in
 /usr/share/common-licenses/Apache-2.0.
EOF

cat > "$PKG"/DEBIAN/control <<EOF
Package: sockrates
Version: $VER
Section: net
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9)
Recommends: python3-tk
Maintainer: SimuZSkyNeT <simuzcrypto@gmail.com>
Homepage: https://github.com/SimuZSkyNeT/sockrates
Description: SOCKS5 proxy finder that makes every proxy prove it works
 Sockrates collects open SOCKS5 proxies from public lists and cross-examines
 each one until it demonstrates that it reaches the target you care about.
 .
 TLS targets are proven end to end with a certificate check through the tunnel;
 Telegram datacenters get a real MTProto handshake; and every candidate is also
 asked to connect somewhere unroutable, so proxies that fake success are
 discarded instead of padding the results.
 .
 It runs in the terminal and as a desktop application, and has no third-party
 dependencies. The desktop app needs python3-tk.
EOF
# Recommends, not Depends: the terminal side works perfectly without Tkinter,
# and pulling in X libraries on a headless server would be rude.

if command -v fakeroot >/dev/null; then
    fakeroot dpkg-deb --build --root-owner-group "$PKG" >/dev/null
else
    dpkg-deb --build --root-owner-group "$PKG" >/dev/null
fi
rm -rf "$PKG"
echo "✅ $PKG.deb"
