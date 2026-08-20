# Fedora / RHEL / openSUSE
#
# %{python3_sitelib} comes from python3-devel on Fedora. Define a fallback so the
# spec also builds on distributions whose rpm lacks the Python macros — the
# package is noarch Python, so nothing about the result changes.
%{!?python3_sitelib: %global python3_sitelib %(python3 -c "import sysconfig; print(sysconfig.get_path('purelib'))")}

Name:           sockrates
Version:        0.2.3
Release:        1%{?dist}
Summary:        SOCKS5 proxy finder that makes every proxy prove it works

License:        Apache-2.0
URL:            https://github.com/SimuZSkyNeT/sockrates
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
Requires:       python3 >= 3.9
# The terminal side needs nothing else; the desktop app needs Tk, but a headless
# box should not be made to pull in X for a CLI tool.
Recommends:     python3-tkinter

%description
Sockrates collects open SOCKS5 proxies from public lists and cross-examines each
one until it demonstrates that it reaches the target you care about.

TLS targets are proven end to end with a certificate check made through the
tunnel; Telegram datacenters get a real MTProto handshake; and every candidate is
additionally asked to connect somewhere unroutable, so proxies that fake success
are discarded rather than padding the results.

It runs in the terminal and as a desktop application, and has no third-party
dependencies.

%prep
%autosetup

%build
# Nothing to compile: two dependency-free modules.

%install
install -Dm644 sockrates.py     %{buildroot}%{python3_sitelib}/sockrates.py
install -Dm644 sockrates_gui.py %{buildroot}%{python3_sitelib}/sockrates_gui.py

mkdir -p %{buildroot}%{_bindir}
for name in sockrates sockrates-gui; do
  mod=$(echo $name | tr - _)
  cat > %{buildroot}%{_bindir}/$name <<EOF
#!/usr/bin/python3
import sys
from $mod import main
sys.exit(main())
EOF
  chmod 755 %{buildroot}%{_bindir}/$name
done

# Byte-compile explicitly, stripping the buildroot from the recorded paths, so
# the .pyc files exist on every rpm distro and not only on those whose macros
# happen to do it for us.
python3 -m compileall -q -s %{buildroot} -p / %{buildroot}%{python3_sitelib} || :

install -Dm644 packaging/sockrates.1 %{buildroot}%{_mandir}/man1/sockrates.1
install -Dm644 packaging/sockrates.desktop \
        %{buildroot}%{_datadir}/applications/%{name}.desktop
for s in 16 24 32 48 64 128 256 512; do
  install -Dm644 packaging/icons/sockrates-$s.png \
    %{buildroot}%{_datadir}/icons/hicolor/${s}x${s}/apps/%{name}.png
done
install -Dm644 packaging/icons/sockrates.svg \
  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg

%check
python3 tests/test_protocol.py

%files
%license LICENSE NOTICE
%doc README.md CHANGELOG.md docs/
%{_bindir}/sockrates
%{_bindir}/sockrates-gui
%{python3_sitelib}/sockrates.py
%{python3_sitelib}/sockrates_gui.py
%{python3_sitelib}/__pycache__/sockrates*.pyc
%{_mandir}/man1/sockrates.1*
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.*

%changelog
* Fri Aug 21 2026 SimuZSkyNeT <318048242+SimuZSkyNeT@users.noreply.github.com> - 0.2.3-1
- Empty scan range falls back to public lists instead of erroring.
* Fri Aug 21 2026 SimuZSkyNeT <318048242+SimuZSkyNeT@users.noreply.github.com> - 0.2.2-1
- Scan and custom-target fields are always typeable; clicking one selects its mode.
* Fri Aug 21 2026 SimuZSkyNeT <318048242+SimuZSkyNeT@users.noreply.github.com> - 0.2.1-1
- Fix keyboard focus in settings fields on some window managers; validate numeric inputs.
* Thu Aug 20 2026 SimuZSkyNeT <318048242+SimuZSkyNeT@users.noreply.github.com> - 0.2.0-1
- Add scan mode (--scan) to discover proxies by scanning authorised ranges.
* Thu Aug 20 2026 SimuZSkyNeT <318048242+SimuZSkyNeT@users.noreply.github.com> - 0.1.0-1
- First release.
