# Installing

Sockrates is one dependency-free Python program, so every route below ends up in the same
place. Pick whichever suits your machine.

## Debian, Ubuntu, Mint, Pop!\_OS

```bash
wget https://github.com/SimuZSkyNeT/sockrates/releases/latest/download/sockrates_0.3.0_all.deb
sudo apt install ./sockrates_0.3.0_all.deb
```

`apt install ./file.deb` rather than `dpkg -i` so the recommended `python3-tk` (the desktop
app) is pulled in for you. Remove with `sudo apt remove sockrates`.

## Fedora, RHEL, openSUSE

```bash
sudo dnf install https://github.com/SimuZSkyNeT/sockrates/releases/latest/download/sockrates-0.3.0-1.noarch.rpm
```

openSUSE: `sudo zypper install <url>`. Remove with `sudo dnf remove sockrates`.

## Arch, Manjaro, EndeavourOS

```bash
git clone https://github.com/SimuZSkyNeT/sockrates.git
cd sockrates/packaging
makepkg -si
```

## Any distribution — pip / pipx

```bash
pipx install sockrates          # isolated, recommended
pip install --user sockrates    # or straight into your user site
```

`pipx` will not give you the desktop entry or the man page — it installs the two commands and
nothing else. Tkinter has to come from your distribution either way (`python3-tk`,
`python3-tkinter`, `tk`); pip cannot install it.

## From source, no packaging at all

```bash
git clone https://github.com/SimuZSkyNeT/sockrates.git
cd sockrates
python3 sockrates.py --help          # it already works, right there
sudo make install                    # or put it on PATH properly
```

`make install` places the modules under `/usr/lib/sockrates`, the two commands in
`/usr/bin`, plus the man page, desktop entry and icons. `sudo make uninstall` reverses it.

## The desktop app

The GUI needs Tkinter. It ships with CPython but several distributions package it separately:

| | |
|---|---|
| Debian, Ubuntu | `sudo apt install python3-tk` |
| Fedora, RHEL | `sudo dnf install python3-tkinter` |
| Arch | `sudo pacman -S tk` |
| openSUSE | `sudo zypper install python3-tk` |

The `.deb` and `.rpm` list it as *recommended*, not required — the terminal side works perfectly
without it, and a headless server should not be made to pull in X libraries for a CLI tool.

After installing a package, **Sockrates** appears in your applications menu. From a terminal,
either `sockrates --gui` or `sockrates-gui`.

## Building the packages yourself

```bash
make test     # protocol self-test
make deb      # → dist/sockrates_<version>_all.deb
make rpm      # → dist/sockrates-<version>-1.noarch.rpm
make wheel    # → dist/*.whl and *.tar.gz
make arch     # → dist/*.pkg.tar.zst   (Arch only)
make all      # everything this machine can build
```

Building the `.rpm` on a non-rpm distribution works too — the spec declares Fedora's build
dependency names, so pass `make rpm RPMFLAGS=--nodeps`. The package is noarch Python with
nothing to compile, so skipping them changes nothing.

Every release is also built by [CI](../.github/workflows/release.yml) and attached to the
GitHub release, so you never have to trust a binary somebody built on their laptop.

## Files it creates

| path | what |
|---|---|
| `~/.sockrates/history.json` | what has been observed about each proxy |
| `~/.sockrates.json` | the desktop app's last settings |

Neither is touched unless you run it. `--no-history` skips the first entirely.
