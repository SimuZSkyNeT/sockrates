# Sockrates — build targets. Everything lands in dist/.
VERSION := $(shell grep -m1 '^__version__' sockrates.py | cut -d'"' -f2)
TOPDIR  := $(CURDIR)/dist/rpmbuild
# The spec declares Fedora's build dependency names. Building the rpm on a
# non-rpm distro therefore needs --nodeps: the package is noarch Python and has
# nothing to compile, so skipping them changes nothing about the result.
RPMFLAGS ?=

.PHONY: help test wheel deb rpm arch all clean install uninstall icons

help:
	@echo "Sockrates $(VERSION)"
	@echo
	@echo "  make test       run the protocol self-test"
	@echo "  make wheel      build the Python wheel + sdist (PyPI, pip, pipx)"
	@echo "  make deb        build a .deb (Debian, Ubuntu, Mint, Pop!_OS)"
	@echo "  make rpm        build an .rpm (Fedora, RHEL, openSUSE)"
	@echo "  make arch       build a package with makepkg (Arch, Manjaro)"
	@echo "  make all        everything the machine can build"
	@echo "  make install    install straight from source (needs root)"
	@echo "  make clean      remove dist/ and build leftovers"

test:
	python3 tests/test_protocol.py

wheel: test
	python3 -m build --wheel --sdist

deb: test
	./packaging/build-deb.sh

rpm: test
	@command -v rpmbuild >/dev/null || { echo "rpmbuild not installed"; exit 1; }
	mkdir -p $(TOPDIR)/SOURCES
	tar czf $(TOPDIR)/SOURCES/sockrates-$(VERSION).tar.gz \
	    --transform 's,^\./,sockrates-$(VERSION)/,' \
	    --exclude=./.git --exclude=./dist --exclude='./*.egg-info' \
	    --exclude='./__pycache__' --exclude='./tests/__pycache__' ./
	@rpmbuild -bb packaging/sockrates.spec --define "_topdir $(TOPDIR)" $(RPMFLAGS) \
	  || { echo; echo "→ building the rpm outside Fedora? try:  make rpm RPMFLAGS=--nodeps"; exit 1; }
	@find $(TOPDIR)/RPMS -name '*.rpm' -exec cp {} dist/ \;
	@echo "✅ dist/sockrates-$(VERSION)-1.*.rpm"

arch: test
	@command -v makepkg >/dev/null || { echo "makepkg not installed (Arch only)"; exit 1; }
	cd packaging && makepkg -f
	@mv packaging/*.pkg.tar.* dist/ 2>/dev/null || true

all: wheel deb
	-@$(MAKE) rpm
	-@$(MAKE) arch

# Straight from source, no packaging: useful on a distro we do not package for.
install:
	install -Dm644 sockrates.py     $(DESTDIR)/usr/lib/sockrates/sockrates.py
	install -Dm644 sockrates_gui.py $(DESTDIR)/usr/lib/sockrates/sockrates_gui.py
	@for n in sockrates sockrates-gui; do \
	  m=$$(echo $$n | tr - _); \
	  printf '#!/usr/bin/python3\nimport sys\nsys.path.insert(0, "/usr/lib/sockrates")\nfrom %s import main\nsys.exit(main())\n' $$m \
	    > $(DESTDIR)/usr/bin/$$n; \
	  chmod 755 $(DESTDIR)/usr/bin/$$n; \
	done
	install -Dm644 packaging/sockrates.1 $(DESTDIR)/usr/share/man/man1/sockrates.1
	install -Dm644 packaging/sockrates.desktop $(DESTDIR)/usr/share/applications/sockrates.desktop
	@for s in 16 24 32 48 64 128 256 512; do \
	  install -Dm644 packaging/icons/sockrates-$$s.png \
	    $(DESTDIR)/usr/share/icons/hicolor/$${s}x$${s}/apps/sockrates.png; \
	done
	@echo "✅ installed — run 'sockrates --help'"

uninstall:
	rm -rf $(DESTDIR)/usr/lib/sockrates $(DESTDIR)/usr/bin/sockrates \
	       $(DESTDIR)/usr/bin/sockrates-gui \
	       $(DESTDIR)/usr/share/man/man1/sockrates.1 \
	       $(DESTDIR)/usr/share/applications/sockrates.desktop \
	       $(DESTDIR)/usr/share/icons/hicolor/*/apps/sockrates.*

clean:
	rm -rf dist build *.egg-info __pycache__ tests/__pycache__ packaging/src packaging/pkg
