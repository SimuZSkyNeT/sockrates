#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sockrates GUI — the desktop face of the proxy cross-examiner.

Tkinter on purpose: it ships with Python, so the whole project stays at zero
third-party dependencies. Everything the CLI can do is selectable here.

Threading note: Tk is not thread-safe. The hunt runs in worker threads and never
touches a widget — it pushes events onto a queue that the UI drains from the main
thread with `after()`. That is the only safe way to do live results in Tk.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sockrates as ph

# Palette — dark, readable, no images to ship.
BG = "#15181d"
BG2 = "#1c2027"
FG = "#e6e9ef"
MUTED = "#8b93a3"
ACC = "#4da3ff"
OK = "#3ddc84"
WARN = "#ffb454"
ERR = "#ff6b6b"
MONO = ("DejaVu Sans Mono", 10)
UI = ("DejaVu Sans", 10)
UIB = ("DejaVu Sans", 10, "bold")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"Sockrates {ph.__version__} — every proxy must prove itself")
        root.geometry("1160x760")
        root.minsize(900, 600)
        root.configure(bg=BG)

        self.q: queue.Queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.running = False
        self.results: list[ph.Result] = []
        self.sort_col, self.sort_rev = "latency", False

        self._style()
        self._build()
        self._load_cfg()
        self._fix_focus()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(80, self._drain)
        self.root.after(1200, self._check_updates)

    def _fix_focus(self):
        # 🔴 On some Linux window managers a click does not hand keyboard focus to
        # a ttk entry, so typing goes nowhere and the fields look "dead". Force it:
        # any click on an input widget claims focus, and the window claims focus on
        # launch. Class-level bindings cover every entry, present and future.
        for cls in ("TEntry", "TSpinbox", "TCombobox"):
            self.root.bind_class(cls, "<Button-1>",
                                 lambda e: e.widget.focus_set(), add="+")
        self.root.after(200, self._grab_keyboard)

    def _grab_keyboard(self):
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    # ------------------------------------------------------------- settings
    # Remembering the last setup is small but it is the difference between a
    # tool you configure once and one you re-configure every single launch.
    CFG = os.path.join(os.path.expanduser("~"), ".sockrates.json")

    def _save_cfg(self):
        try:
            with open(self.CFG, "w") as f:
                json.dump({
                    "target": self.v_target.get(), "host": self.v_host.get(),
                    "cert": self.v_cert.get(), "workers": int(self.v_workers.get()),
                    "timeout": float(self.v_timeout.get()), "maxlat": float(self.v_maxlat.get()),
                    "strict": bool(self.v_strict.get()), "country": bool(self.v_country.get()),
                    "anon": bool(self.v_anon.get()),
                    "only": self.v_only.get(), "auto": bool(self.v_auto.get()),
                    "every": int(self.v_every.get()), "autofile": self.v_autofile.get(),
                    "updates": bool(self.v_updates.get()), "fresh": bool(self.v_fresh.get()),
                    "srcmode": self.v_srcmode.get(), "scan": self.v_scan.get(),
                    "ports": self.v_ports.get(),
                    "types": [pt for pt, v in self.type_vars.items() if v.get()],
                }, f, indent=2)
        except Exception:
            pass

    def _load_cfg(self):
        try:
            with open(self.CFG) as f:
                c = json.load(f)
        except Exception:
            return
        try:
            self.v_target.set(c.get("target", "telegram-mtproto"))
            self.v_host.set(c.get("host", self.v_host.get()))
            self.v_cert.set(c.get("cert", ""))
            self.v_workers.set(c.get("workers", 600))
            self.v_timeout.set(c.get("timeout", 6.0))
            self.v_maxlat.set(c.get("maxlat", 0.0))
            self.v_strict.set(c.get("strict", True))
            self.v_country.set(c.get("country", True))
            self.v_anon.set(c.get("anon", False))
            self.v_only.set(c.get("only", ""))
            self.v_auto.set(c.get("auto", False))
            self.v_every.set(c.get("every", 10))
            self.v_autofile.set(c.get("autofile", ""))
            self.v_updates.set(c.get("updates", True))
            self.v_fresh.set(c.get("fresh", True))
            self.v_srcmode.set(c.get("srcmode", "lists"))
            self.v_scan.set(c.get("scan", ""))
            self.v_ports.set(c.get("ports", ""))
            self._srcmode()
            keep = set(c.get("types") or [])
            if keep:
                for pt, v in self.type_vars.items():
                    v.set(pt in keep)
            self._toggle_custom()
        except Exception:
            pass

    def _quit(self):
        self._save_cfg()
        self.stop_flag.set()
        self.root.destroy()

    # ---------------------------------------------------------------- style
    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG, fieldbackground=BG2,
                    bordercolor=BG2, font=UI)
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=BG2, relief="flat")
        s.configure("TLabel", background=BG, foreground=FG, font=UI)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("Head.TLabel", background=BG, foreground=ACC, font=UIB)
        s.configure("Brand.TLabel", background=BG, foreground=FG,
                    font=("DejaVu Sans", 17, "bold"))
        s.configure("Tagline.TLabel", background=BG, foreground=MUTED,
                    font=("DejaVu Sans", 9, "italic"))
        s.configure("Warn.TLabel", background=BG, foreground=WARN, font=UI)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        s.map("TCheckbutton", background=[("active", BG)])
        s.configure("TRadiobutton", background=BG, foreground=FG)
        s.map("TRadiobutton", background=[("active", BG)])
        s.configure("TButton", background=BG2, foreground=FG, borderwidth=0, padding=(11, 7))
        s.map("TButton", background=[("active", "#2a303a"), ("disabled", "#20242b")],
              foreground=[("disabled", MUTED)])
        s.configure("Go.TButton", background=ACC, foreground="#08121e", font=UIB)
        s.map("Go.TButton", background=[("active", "#6bb4ff"), ("disabled", "#2a3a4d")])
        s.configure("Stop.TButton", background=ERR, foreground="#1a0808", font=UIB)
        s.map("Stop.TButton",
              background=[("disabled", "#20242b"), ("active", "#ff8787")],
              foreground=[("disabled", MUTED)])
        s.configure("TEntry", fieldbackground=BG2, foreground=FG, insertcolor=FG,
                    borderwidth=0, padding=6)
        s.configure("TSpinbox", fieldbackground=BG2, foreground=FG, arrowcolor=FG,
                    borderwidth=0, padding=4)
        s.configure("TCombobox", fieldbackground=BG2, foreground=FG, arrowcolor=FG,
                    borderwidth=0, padding=4)
        s.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=FG,
                    rowheight=27, borderwidth=0, font=MONO)
        s.configure("Treeview.Heading", background="#242a33", foreground=MUTED,
                    font=UIB, relief="flat", padding=7)
        s.map("Treeview.Heading", background=[("active", "#2f3742")])
        s.map("Treeview", background=[("selected", "#2b4a6f")],
              foreground=[("selected", FG)])
        s.configure("TProgressbar", background=ACC, troughcolor=BG2, borderwidth=0)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=MUTED, padding=(16, 8))
        s.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACC)])

    # ---------------------------------------------------------------- build
    def _build(self):
        wrap = ttk.Frame(self.root, padding=(16, 12, 16, 14))
        wrap.pack(fill="both", expand=True)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(3, weight=1)

        # --- header: a small drawn mark + wordmark, so a screenshot has an identity
        head = ttk.Frame(wrap)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        logo = tk.Canvas(head, width=34, height=34, bg=BG, highlightthickness=0)
        logo.create_oval(4, 4, 24, 24, outline=ACC, width=3)
        logo.create_line(22, 22, 31, 31, fill=ACC, width=4, capstyle="round")
        logo.create_line(9, 13, 13, 18, fill=OK, width=3, capstyle="round")
        logo.create_line(13, 18, 20, 9, fill=OK, width=3, capstyle="round")
        logo.pack(side="left", padx=(0, 10))
        tf = ttk.Frame(head)
        tf.pack(side="left")
        ttk.Label(tf, text="Sockrates", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(tf, text="Every proxy must prove itself.",
                  style="Tagline.TLabel").pack(anchor="w")
        ttk.Label(head, text=f"v{ph.__version__}", style="Muted.TLabel").pack(side="right")

        nb = ttk.Notebook(wrap)
        nb.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        nb.add(self._tab_target(nb), text="   Target   ")
        nb.add(self._tab_sources(nb), text="   Sources   ")
        nb.add(self._tab_tuning(nb), text="   Tuning   ")
        nb.add(self._tab_about(nb), text="   About   ")

        # --- action bar
        bar = ttk.Frame(wrap)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.b_go = ttk.Button(bar, text="▶  Hunt", style="Go.TButton", command=self.start)
        self.b_go.pack(side="left")
        self.b_stop = ttk.Button(bar, text="■  Stop", style="Stop.TButton",
                                 command=self.stop, state="disabled")
        self.b_stop.pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="↻  Re-test", command=self.retest).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Load…", command=self.load).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Save…", command=self.save).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Copy", command=self.copy).pack(side="left", padx=(8, 0))

        self.lbl_stat = ttk.Label(bar, text="idle", style="Muted.TLabel")
        self.lbl_stat.pack(side="right")
        self.v_filter = tk.StringVar()
        self.v_filter.trace_add("write", lambda *_: self._repaint())
        e = ttk.Entry(bar, textvariable=self.v_filter, width=14)
        e.pack(side="right", padx=(0, 12))
        ttk.Label(bar, text="Filter", style="Muted.TLabel").pack(side="right", padx=(10, 6))

        # --- results
        card = ttk.Frame(wrap, style="Card.TFrame", padding=1)
        card.grid(row=3, column=0, sticky="nsew")
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)
        cols = ("proxy", "type", "latency", "country", "anon", "verified", "age", "reliability")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", selectmode="extended")
        heads = {"proxy": ("Proxy", 175), "type": ("Type", 70), "latency": ("Latency", 80),
                 "country": ("Country", 70), "anon": ("Anonymity", 100),
                 "verified": ("Proof", 90),
                 "age": ("Known for", 90), "reliability": ("Reliability", 110)}
        for c in cols:
            t, w = heads[c]
            self.tree.heading(c, text=t, command=lambda c=c: self._sort(c))
            self.tree.column(c, width=w, anchor="w" if c == "proxy" else "center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("even", background=BG2)
        self.tree.tag_configure("odd", background="#20242c")
        self.tree.tag_configure("fast", foreground=OK)
        self.tree.tag_configure("slow", foreground=WARN)

        self.menu = tk.Menu(self.root, tearoff=0, bg=BG2, fg=FG,
                            activebackground=ACC, activeforeground="#08121e", bd=0)
        self.menu.add_command(label="Copy", command=self.copy)
        self.menu.add_command(label="Copy as socks5:// URI", command=lambda: self.copy(uri=True))
        self.menu.add_separator()
        self.menu.add_command(label="Remove from list", command=self._drop)
        self.tree.bind("<Button-3>", self._popup)
        self.tree.bind("<Double-1>", lambda e: self.copy())
        self.root.bind("<Control-r>", lambda e: self.start())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-c>", lambda e: self.copy())
        self.root.bind("<Escape>", lambda e: self.stop())

        # --- progress + log
        foot = ttk.Frame(wrap)
        foot.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        foot.columnconfigure(0, weight=1)
        self.pb = ttk.Progressbar(foot, mode="determinate")
        self.pb.grid(row=0, column=0, sticky="ew")
        self.lbl_log = ttk.Label(foot, text="Ready. Pick a target and hit Hunt.",
                                 style="Muted.TLabel")
        self.lbl_log.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _tab_target(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=14)
        self.v_target = tk.StringVar(value="telegram-mtproto")
        ttk.Label(f, text="What must the proxy actually reach?", style="Head.TLabel"
                  ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        opts = [
            ("telegram-mtproto", "Telegram — user clients (Telethon, apps)",
             "Real MTProto handshake against a datacenter"),
            ("telegram-bot", "Telegram — Bot API",
             "HTTPS to api.telegram.org, certificate verified"),
            ("https", "Any HTTPS site (generic)", "Handshake with cloudflare.com"),
            ("custom", "Custom host:port…", "Your own endpoint, optional cert check"),
        ]
        for i, (val, label, hint) in enumerate(opts, start=1):
            ttk.Radiobutton(f, text=label, value=val, variable=self.v_target,
                            command=self._toggle_custom).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Label(f, text=hint, style="Muted.TLabel").grid(row=i, column=1, sticky="w", padx=14)

        self.v_host = tk.StringVar(value="api.example.com:443")
        self.v_cert = tk.StringVar(value="")
        cf = ttk.Frame(f)
        cf.grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))
        ttk.Label(cf, text="host:port").pack(side="left")
        self.e_host = ttk.Entry(cf, textvariable=self.v_host, width=28)
        self.e_host.pack(side="left", padx=(8, 16))
        ttk.Label(cf, text="certificate must contain").pack(side="left")
        self.e_cert = ttk.Entry(cf, textvariable=self.v_cert, width=22)
        self.e_cert.pack(side="left", padx=8)
        # same rule as the scan boxes: clicking here means "I want the custom target"
        for w in (self.e_host, self.e_cert):
            w.bind("<FocusIn>", lambda e: self.v_target.set("custom"), add="+")
        ttk.Label(f, text="Leave the certificate field empty to accept a plain TCP connection.",
                  style="Muted.TLabel").grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))
        return f

    def _tab_sources(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=14)
        self.v_srcmode = tk.StringVar(value="lists")
        ttk.Label(f, text="Where the candidates come from", style="Head.TLabel").pack(
            anchor="w", pady=(0, 8))

        ttk.Radiobutton(f, text="Public lists — proxies other people have already found",
                        value="lists", variable=self.v_srcmode,
                        command=self._srcmode).pack(anchor="w")
        box = ttk.Frame(f)
        box.pack(fill="x", padx=(22, 0), pady=(2, 4))
        ttk.Label(box, text="Proxy types:", style="Muted.TLabel").pack(side="left")
        # one checkbox per proxy type; the number of source lists behind each is
        # shown so the user knows what they're pulling.
        self.type_vars = {}
        for pt in ph.PROXY_TYPES:
            v = tk.BooleanVar(value=(pt == "socks5"))
            self.type_vars[pt] = v
            n = len(ph.SOURCES.get(pt, []))
            ttk.Checkbutton(box, variable=v, text=f"{pt.upper()} ({n})").pack(
                side="left", padx=(12, 0))
        ttk.Label(f, text="SOCKS5 for Telegram user clients (Telethon); HTTP/SOCKS4 also work "
                          "for the HTTPS and Bot-API targets.", style="Muted.TLabel").pack(
            anchor="w", padx=(22, 0), pady=(2, 10))

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)

        ttk.Radiobutton(f, text="Scan a range — discover proxies nobody has published yet",
                        value="scan", variable=self.v_srcmode,
                        command=self._srcmode).pack(anchor="w")
        sc = ttk.Frame(f)
        sc.pack(anchor="w", padx=(22, 0), pady=(4, 0))
        ttk.Label(sc, text="Range").grid(row=0, column=0, sticky="w")
        self.v_scan = tk.StringVar()
        self.e_scan = ttk.Entry(sc, textvariable=self.v_scan, width=28)
        self.e_scan.grid(row=0, column=1, padx=(8, 16))
        ttk.Label(sc, text="Ports").grid(row=0, column=2, sticky="w")
        self.v_ports = tk.StringVar()
        self.e_ports = ttk.Entry(sc, textvariable=self.v_ports, width=20)
        self.e_ports.grid(row=0, column=3, padx=8)
        # 🔑 Clicking or typing in a scan box selects scan mode, so the field is
        # never a dead black box. FocusIn covers both mouse and Tab.
        for w in (self.e_scan, self.e_ports):
            w.bind("<FocusIn>", lambda e: self._pick_mode("scan"), add="+")
        ttk.Label(f, text="e.g.  203.0.113.0/24   ·   .1-.50   ·   a single host   "
                          "(blank ports = common SOCKS5 ports)",
                  style="Muted.TLabel").pack(anchor="w", padx=(22, 0), pady=(4, 0))
        self.lbl_scanwarn = ttk.Label(
            f, text="⚠  Only scan ranges you own or are authorised to test.",
            style="Warn.TLabel")
        self.lbl_scanwarn.pack(anchor="w", padx=(22, 0), pady=(6, 0))
        self._srcmode()
        return f

    def _srcmode(self):
        # 🔑 The scan fields are never disabled — a disabled ttk entry looks like
        # a dead black box you cannot click into. They stay typeable; clicking or
        # typing in one selects scan mode (see the FocusIn binding). Only the run
        # button's label follows the mode.
        scanning = self.v_srcmode.get() == "scan"
        if hasattr(self, "b_go"):
            self.b_go.configure(text="▶  Scan" if scanning else "▶  Hunt")

    def _pick_mode(self, mode: str):
        """Typing/clicking in a scan field selects scan mode to match."""
        if self.v_srcmode.get() != mode:
            self.v_srcmode.set(mode)
            self._srcmode()

    def _tab_tuning(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=14)
        ttk.Label(f, text="Speed, strictness and filters", style="Head.TLabel"
                  ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))
        self.v_workers = tk.IntVar(value=600)
        self.v_timeout = tk.DoubleVar(value=6.0)
        self.v_maxlat = tk.DoubleVar(value=0.0)
        self.v_strict = tk.BooleanVar(value=True)
        self.v_country = tk.BooleanVar(value=True)
        self.v_only = tk.StringVar(value="")

        # only digits and a dot may be typed — a spinbox bound to a number must
        # never end up holding "DE,NL", which would crash the next hunt.
        vnum = (f.register(lambda P: P == "" or P.replace(".", "", 1).isdigit()), "%P")

        def num(r, c, label, var, frm, to, inc, hint):
            ttk.Label(f, text=label).grid(row=r, column=c, sticky="w", pady=4)
            ttk.Spinbox(f, from_=frm, to=to, increment=inc, textvariable=var, width=8,
                        validate="key", validatecommand=vnum
                        ).grid(row=r, column=c + 1, sticky="w", padx=(8, 20))
            ttk.Label(f, text=hint, style="Muted.TLabel").grid(row=r, column=c + 2, sticky="w")

        num(1, 0, "Concurrent workers", self.v_workers, 10, 3000, 50,
            "higher = faster, heavier on your machine")
        num(2, 0, "Timeout (s)", self.v_timeout, 1, 30, 1,
            "per proxy; too low drops slow but usable ones")
        num(3, 0, "Max latency (s)", self.v_maxlat, 0, 30, 0.5,
            "0 = keep them all")
        ttk.Checkbutton(f, text="Liar control — discard proxies that fake success",
                        variable=self.v_strict).grid(row=4, column=0, columnspan=3,
                                                     sticky="w", pady=(10, 2))
        ttk.Checkbutton(f, text="Look up country", variable=self.v_country).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=2)
        self.v_anon = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Classify anonymity (transparent / anonymous / elite) — "
                               "one extra request per proxy", variable=self.v_anon).grid(
            row=5, column=3, columnspan=3, sticky="w", pady=2)
        ttk.Label(f, text="Keep only countries").grid(row=6, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(f, textvariable=self.v_only, width=22).grid(row=6, column=1, sticky="w",
                                                              padx=(8, 20), pady=(8, 0))
        ttk.Label(f, text="e.g. DE,NL,FR — empty = anywhere", style="Muted.TLabel"
                  ).grid(row=6, column=2, sticky="w", pady=(8, 0))

        # 🔑 Free proxies rot within minutes. An automatic re-hunt is the single
        # most useful thing this app can do: it keeps the file on disk true.
        # 🔑 The promise of this app is that what it hands you WORKS. Free proxies
        # rot in minutes, so the only honest way to keep that promise is to
        # re-check them in the instant you export or copy, and drop the dead.
        self.v_fresh = tk.BooleanVar(value=True)
        self.v_auto = tk.BooleanVar(value=False)
        self.v_every = tk.IntVar(value=10)
        self.v_autofile = tk.StringVar(value="")
        ttk.Separator(f, orient="horizontal").grid(row=7, column=0, columnspan=6,
                                                   sticky="ew", pady=14)
        ttk.Label(f, text="Keep it fresh", style="Head.TLabel").grid(
            row=8, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="Re-verify before every Save / Copy — never hand out a dead proxy",
                        variable=self.v_fresh).grid(row=8, column=3, columnspan=3, sticky="w")
        ttk.Checkbutton(f, text="Re-hunt automatically every", variable=self.v_auto).grid(
            row=9, column=0, sticky="w", pady=4)
        ttk.Spinbox(f, from_=1, to=180, textvariable=self.v_every, width=6,
                    validate="key", validatecommand=vnum).grid(
            row=9, column=1, sticky="w", padx=(8, 6))
        ttk.Label(f, text="minutes — a list an hour old is mostly dead",
                  style="Muted.TLabel").grid(row=9, column=2, sticky="w")
        ttk.Label(f, text="Auto-save each run to").grid(row=10, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(f, textvariable=self.v_autofile, width=30).grid(
            row=10, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Button(f, text="Choose…", command=self._pick_autofile).grid(
            row=10, column=3, sticky="w", padx=8, pady=(6, 0))
        return f

    def _pick_autofile(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt")
        if p:
            self.v_autofile.set(p)

    def _tab_about(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent, padding=14)
        ttk.Label(f, text=f"Sockrates {ph.__version__}", style="Head.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(f, text="Every proxy must prove itself.", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))
        ttk.Label(f, text="Open SOCKS5 finder that cross-examines every candidate until it\n"
                          "demonstrates it reaches your target — Telegram included.",
                  justify="left").grid(row=2, column=0, columnspan=4, sticky="w")

        ttk.Separator(f, orient="horizontal").grid(row=3, column=0, columnspan=4,
                                                   sticky="ew", pady=12)
        ttk.Label(f, text="Support the project", style="Head.TLabel").grid(
            row=4, column=0, columnspan=4, sticky="w")
        ttk.Label(f, text="It is free and always will be. If it saved you time, a tip helps.",
                  style="Muted.TLabel").grid(row=5, column=0, columnspan=4, sticky="w",
                                             pady=(0, 6))
        ttk.Label(f, text="EVM — works on every EVM chain (ETH, BSC, Base, Arbitrum…)").grid(
            row=6, column=0, columnspan=4, sticky="w")
        wal = ttk.Entry(f, width=46, font=MONO)
        wal.insert(0, ph.DONATE_EVM)
        wal.configure(state="readonly")
        wal.grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 0))
        ttk.Button(f, text="Copy address", command=self._copy_wallet).grid(
            row=7, column=3, sticky="w", padx=8, pady=(4, 0))

        ttk.Separator(f, orient="horizontal").grid(row=8, column=0, columnspan=4,
                                                   sticky="ew", pady=12)
        self.v_updates = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Check for updates on start (asks GitHub for the changelog)",
                        variable=self.v_updates).grid(row=9, column=0, columnspan=4, sticky="w")
        self.lbl_upd = ttk.Label(f, text="", style="Muted.TLabel")
        self.lbl_upd.grid(row=10, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Button(f, text="Check now", command=lambda: self._check_updates(force=True)).grid(
            row=10, column=3, sticky="w", padx=8, pady=(6, 0))

        ttk.Label(f, text=ph.HOME_URL, style="Muted.TLabel").grid(
            row=11, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Label(f, text="Apache License 2.0 · no third-party dependencies",
                  style="Muted.TLabel").grid(row=12, column=0, columnspan=4, sticky="w")
        return f

    def _copy_wallet(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(ph.DONATE_EVM)
        self.lbl_log.configure(text="donation address copied — thank you")

    def _check_updates(self, force: bool = False):
        """Ask GitHub whether a newer version exists, and show what changed.

        Off the main thread, and silent when offline: an update check that blocks
        the app or nags on a bad connection is worse than no update check.
        """
        if not force and not self.v_updates.get():
            return
        self.lbl_upd.configure(text="checking…")

        def work():
            got = ph.check_for_update()
            self.q.put(("update", got))

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, got):
        if not got:
            self.lbl_upd.configure(text=f"you are on the latest version ({ph.__version__})")
            return
        ver, notes = got
        self.lbl_upd.configure(text=f"version {ver} is available")
        win = tk.Toplevel(self.root)
        win.title(f"Sockrates {ver} is available")
        win.configure(bg=BG)
        win.transient(self.root)
        frm = ttk.Frame(win, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Sockrates {ver} — what's new", style="Head.TLabel").pack(anchor="w")
        box = tk.Text(frm, width=78, height=18, bg=BG2, fg=FG, bd=0, wrap="word",
                      font=UI, padx=10, pady=8)
        box.insert("1.0", notes or "(no notes)")
        box.configure(state="disabled")
        box.pack(fill="both", expand=True, pady=(8, 10))

        method, _, _ = ph.detect_install()
        how = {"git": "This copy is a git checkout — Update now runs git pull.",
               "pipx": "Installed with pipx — Update now runs pipx upgrade.",
               "pip": "Installed with pip — Update now runs pip install --upgrade.",
               "system": "Installed as a system package — update it with your package "
                         "manager (apt / dnf). The button will show you the exact command.",
               "unknown": "Update it the way you installed it."}.get(method, "")
        ttk.Label(frm, text=how, style="Muted.TLabel", wraplength=560,
                  justify="left").pack(anchor="w")

        line = ttk.Frame(frm)
        line.pack(fill="x", pady=(12, 0))
        self.lbl_updmsg = ttk.Label(line, text="", style="Muted.TLabel", wraplength=380,
                                    justify="left")
        self.lbl_updmsg.pack(side="left")
        ttk.Button(line, text="Close", command=win.destroy).pack(side="right")
        self.b_update = ttk.Button(line, text="Update now", style="Go.TButton",
                                   command=lambda: self._do_update(win))
        self.b_update.pack(side="right", padx=8)

    def _do_update(self, win):
        self.b_update.configure(state="disabled")
        self.lbl_updmsg.configure(text="updating…")
        self.root.update_idletasks()

        def work():
            ok, msg = ph.apply_update()
            self.q.put(("updresult", (ok, msg, win)))

        threading.Thread(target=work, daemon=True).start()

    def _show_updresult(self, payload):
        ok, msg, win = payload
        try:
            self.lbl_updmsg.configure(text=msg, foreground=OK if ok else ERR)
            self.b_update.configure(state="normal")
        except tk.TclError:
            return  # dialog already closed
        # if a git/pip update actually applied, offer to relaunch into the new code
        if ok and "restart" in msg.lower():
            if messagebox.askyesno("Sockrates", "Updated. Restart now to run the new version?"):
                self._save_cfg()
                os.execv(sys.executable, [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:])

    def _toggle_custom(self):
        # kept for the radio's command and config load; the fields are no longer
        # disabled (a disabled entry reads as a dead box), so there is nothing to
        # toggle — clicking a field selects the custom target via its FocusIn bind.
        pass

    # ---------------------------------------------------------------- run
    def _target_key(self) -> str:
        t = self.v_target.get()
        if t != "custom":
            return t
        hp = self.v_host.get().strip()
        host, _, port = hp.rpartition(":")
        if not host or not port.isdigit():
            raise ValueError("Custom target must look like host:port")
        cert = self.v_cert.get().strip() or None
        ph.TARGETS[hp] = (host, int(port), host if cert else None, cert)
        return hp

    def start(self):
        if self.running:
            return
        try:
            target = self._target_key()
        except ValueError as e:
            messagebox.showerror("Sockrates", str(e))
            return
        scan_spec = None
        srcs = []
        # An empty range means "I'm not scanning" — fall back to the public lists
        # instead of scolding the user. Clicking a scan box earlier flipped the
        # mode; clearing it should quietly flip back.
        if self.v_srcmode.get() == "scan" and not self.v_scan.get().strip():
            self.v_srcmode.set("lists")
            self._srcmode()
        if self.v_srcmode.get() == "scan":
            spec = self.v_scan.get().strip()
            try:
                ports = ([int(x) for x in self.v_ports.get().split(",") if x.strip()]
                         or ph.SOCKS5_PORTS)
                scan_spec = ph.expand_targets(spec, ports)   # validates size / format
            except ValueError as e:
                messagebox.showerror("Sockrates", str(e))
                return
            if not messagebox.askokcancel(
                    "Scan a range",
                    f"About to scan {len(scan_spec):,} host:port pairs in {spec}.\n\n"
                    "Only do this on ranges you own or are authorised to test."):
                return
        else:
            srcs = [pt for pt, v in self.type_vars.items() if v.get()]
            if not srcs:
                messagebox.showerror("Sockrates", "Pick at least one proxy type.")
                return
        self._reset()
        self.running = True
        self.stop_flag.clear()
        self.b_go.configure(state="disabled")
        self.b_stop.configure(state="normal")
        threading.Thread(target=self._work, args=(target, srcs, None, scan_spec),
                         daemon=True).start()

    def retest(self):
        if self.running:
            return
        current = [self.tree.item(i, "values")[0] for i in self.tree.get_children()]
        self._before = len(current)
        if not current:
            messagebox.showinfo("Sockrates", "Nothing in the table to re-test.")
            return
        try:
            target = self._target_key()
        except ValueError as e:
            messagebox.showerror("Sockrates", str(e))
            return
        self._reset()
        self.running = True
        self.stop_flag.clear()
        self.b_go.configure(state="disabled")
        self.b_stop.configure(state="normal")
        threading.Thread(target=self._work, args=(target, [], current), daemon=True).start()

    def stop(self):
        self.stop_flag.set()
        self.q.put(("log", "stopping — letting running checks finish…"))

    def _num(self, var, default):
        """Read a numeric field defensively — an empty or half-typed box is not a crash."""
        try:
            return type(default)(var.get())
        except (ValueError, tk.TclError):
            return default

    def _work(self, target: str, sources: list[str], preset: list[str] | None,
              scan_spec: list[str] | None = None):
        try:
            types = [pt for pt, v in self.type_vars.items() if v.get()] or ["socks5"]
            if scan_spec is not None:
                self.q.put(("log", f"scanning {len(scan_spec):,} host:port pairs "
                                   f"for {', '.join(types)}…"))
                t0 = time.time()
                proxies = ph.scan(scan_spec, self._num(self.v_workers, 600),
                                  min(self._num(self.v_timeout, 6.0), 4.0), types=types)
                self.q.put(("log", f"{len(proxies)} open port(s) in {time.time()-t0:.1f}s "
                                   "— now verifying each really works"))
            elif preset is None:
                self.q.put(("log", f"collecting {', '.join(types)}…"))
                t0 = time.time()
                proxies = ph.collect(types, verbose=False)
                self.q.put(("log", f"{len(proxies):,} unique candidates in {time.time()-t0:.1f}s"))
            else:
                proxies = preset
                self.q.put(("log", f"re-testing {len(proxies)} proxies…"))
            if not proxies:
                self.q.put(("done", "no candidates — every source failed"))
                return

            self.q.put(("total", len(proxies)))
            timeout = self._num(self.v_timeout, 6.0)
            strict = bool(self.v_strict.get())
            maxlat = self._num(self.v_maxlat, 0.0)
            import concurrent.futures as F
            ex = F.ThreadPoolExecutor(max_workers=self._num(self.v_workers, 600))
            try:
                futs = [ex.submit(ph.check, p, target, timeout, strict) for p in proxies]
                for i, fu in enumerate(F.as_completed(futs), 1):
                    if self.stop_flag.is_set():
                        break
                    try:
                        r = fu.result()
                    except Exception:
                        r = None
                    if r and (not maxlat or r.latency <= maxlat):
                        self.q.put(("hit", r))
                    if i % 25 == 0:
                        self.q.put(("tick", i))
            finally:
                ex.shutdown(wait=False, cancel_futures=True)
            if self.v_anon.get() and self.results:
                self.q.put(("log", f"classifying anonymity of {len(self.results)}…"))
                ph.classify_anonymity(self.results, self._num(self.v_workers, 600),
                                      self._num(self.v_timeout, 6.0))
                self.q.put(("refresh", None))
            # same record the CLI keeps: how long we have known each proxy and
            # how often it held up. Without this the two faces would disagree.
            try:
                h = ph.load_history()
                alive = [r for r in self.results]
                ph.record(h, proxies, alive)
                ph.save_history(h)
            except Exception:
                pass
            self.q.put(("countries", None))
        except Exception as e:  # never let the worker die silently
            self.q.put(("done", f"error: {e}"))
            return
        self.q.put(("done", ""))

    # ---------------------------------------------------------------- ui pump
    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.lbl_log.configure(text=payload)
                elif kind == "total":
                    self.pb.configure(maximum=payload, value=0)
                    self.total = payload
                elif kind == "tick":
                    self.pb.configure(value=payload)
                    self.lbl_stat.configure(
                        text=f"{payload:,}/{getattr(self,'total',0):,} tested · "
                             f"{len(self.results)} good")
                elif kind == "hit":
                    self.results.append(payload)
                    self._insert(payload)
                elif kind == "countries":
                    if self.v_country.get() and self.results:
                        self.lbl_log.configure(text="looking up countries…")
                        threading.Thread(target=self._countries, daemon=True).start()
                elif kind == "update":
                    self._show_update(payload)
                elif kind == "updresult":
                    self._show_updresult(payload)
                elif kind == "refresh":
                    self._repaint()
                elif kind == "done":
                    self._finish(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._drain)

    def _countries(self):
        ph.add_countries(self.results)
        only = {c.strip().upper() for c in self.v_only.get().split(",") if c.strip()}
        if only:
            self.results = [r for r in self.results if r.country in only]
        self.q.put(("refresh", None))

    def _insert(self, r: ph.Result):
        speed = "fast" if r.latency <= 1.0 else ("slow" if r.latency > 3 else "")
        # zebra striping keeps a long list readable; speed colour rides on top
        zebra = "odd" if (len(self.tree.get_children()) % 2) else "even"
        rel = f"{100*r.reliability:.0f}% of {r.checks}" if r.checks else "—"
        self.tree.insert("", "end",
                         values=(r.addr, r.ptype, f"{r.latency:.2f}s", r.country or "—",
                                 r.anonymity or "—", r.verified,
                                 r.age_label if r.checks else "—", rel),
                         tags=(zebra, speed))

    def _fresh(self, rows: list[ph.Result]) -> list[ph.Result]:
        """Re-test `rows` right now and return only the survivors."""
        if not self.v_fresh.get() or not rows:
            return rows
        import concurrent.futures as F
        try:
            target = self._target_key()
        except ValueError:
            return rows
        self.lbl_log.configure(text=f"re-verifying {len(rows)} before handing them over…")
        self.root.update_idletasks()
        timeout = float(self.v_timeout.get())
        alive: list[ph.Result] = []
        with F.ThreadPoolExecutor(max_workers=min(300, max(10, len(rows)))) as ex:
            futs = {ex.submit(ph.check, r.proxy, target, timeout,
                              bool(self.v_strict.get())): r for r in rows}
            for fu in F.as_completed(futs):
                try:
                    got = fu.result()
                except Exception:
                    got = None
                if got:
                    got.country = futs[fu].country
                    alive.append(got)
        alive.sort(key=lambda r: r.latency)
        dead = len(rows) - len(alive)
        self.lbl_log.configure(
            text=f"{len(alive)} still alive" + (f" · {dead} had died since the hunt" if dead else
                                                " · all of them still good"))
        return alive

    def _shown(self) -> list[ph.Result]:
        """What the table is currently showing: filter + sort applied."""
        q = self.v_filter.get().strip().lower()
        rows = [r for r in self.results
                if not q or q in r.proxy.lower() or q in (r.country or "").lower()]
        # anonymity sorts best-first: elite > anonymous > transparent > ? > unset
        _anon_rank = {"elite": 0, "anonymous": 1, "transparent": 2, "?": 3, "": 4}
        key = {"proxy": lambda r: r.addr, "type": lambda r: r.ptype,
               "latency": lambda r: r.latency,
               "country": lambda r: r.country, "verified": lambda r: r.verified,
               "anon": lambda r: _anon_rank.get(r.anonymity, 5),
               "age": lambda r: r.age_h,
               "reliability": lambda r: (r.reliability, r.checks)}[self.sort_col]
        return sorted(rows, key=key, reverse=self.sort_rev)

    def _repaint(self):
        self.tree.delete(*self.tree.get_children())
        rows = self._shown()
        for r in rows:
            self._insert(r)
        extra = f" of {len(self.results)}" if len(rows) != len(self.results) else ""
        self.lbl_stat.configure(text=f"{len(rows)}{extra} good")

    def _sort(self, col: str):
        self.sort_rev = not self.sort_rev if col == self.sort_col else False
        self.sort_col = col
        self._repaint()

    def _reset(self):
        self.results.clear()
        self.tree.delete(*self.tree.get_children())
        self.pb.configure(value=0)
        self.lbl_stat.configure(text="working…")

    def _finish(self, err: str):
        self.running = False
        self.b_go.configure(state="normal")
        self.b_stop.configure(state="disabled")
        self.pb.configure(value=self.pb["maximum"])
        self._repaint()
        if err:
            self.lbl_log.configure(text=err)
            return

        n = len(self.results)
        tot = getattr(self, "total", 0)
        rate = 100.0 * n / tot if tot else 0
        fast = min((r.latency for r in self.results), default=0)
        msg = f"done — {n} good out of {tot:,} ({rate:.2f}%)"
        if n:
            msg += f" · fastest {fast:.2f}s"
        # 🔑 on a re-test, the interesting number is how many DIED since last time:
        # it tells you how often you need to re-hunt.
        before = getattr(self, "_before", 0)
        if before:
            dead = before - n
            msg += f" · {dead}/{before} died since the last check ({100*dead/before:.0f}%)"
            self._before = 0
        self.lbl_log.configure(text=msg)

        if self.v_autofile.get() and self.results:
            try:
                with open(self.v_autofile.get(), "w") as f:
                    f.write(ph.render(self._shown(), "plain") + "\n")
            except Exception as e:
                self.lbl_log.configure(text=f"{msg} · auto-save failed: {e}")
        self._save_cfg()
        if self.v_auto.get():
            mins = max(1, int(self.v_every.get()))
            self._auto_at = time.time() + mins * 60
            self._auto_job = self.root.after(mins * 60 * 1000, self._auto_fire)
            self.lbl_stat.configure(text=f"{n} good · next run in {mins} min")

    def _auto_fire(self):
        if not self.v_auto.get() or self.running:
            return
        self.start()

    # ---------------------------------------------------------------- io
    def load(self):
        p = filedialog.askopenfilename(title="Load a proxy list",
                                       filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not p:
            return
        with open(p) as f:
            found = {m.group(0) for line in f for m in [ph.IPPORT_RX.search(line)] if m}
        self._reset()
        self.results = [ph.Result(proxy=x, latency=0.0, target="(not tested)", verified="—")
                        for x in sorted(found)]
        self._repaint()
        self.lbl_log.configure(text=f"{len(found)} loaded — hit “Re-test shown” to verify them")

    def save(self):
        rows = self._fresh(self._shown())
        if not rows:
            messagebox.showinfo("Sockrates", "Nothing to save yet.")
            return
        win = tk.Toplevel(self.root)
        win.title("Export")
        win.configure(bg=BG)
        win.transient(self.root)
        win.grab_set()
        frm = ttk.Frame(win, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Export {len(rows)} proxies as…", style="Head.TLabel").pack(anchor="w")
        var = tk.StringVar(value="plain")
        for key in sorted(ph.FORMATS):
            _, ext, hint = ph.FORMATS[key]
            ttk.Radiobutton(frm, text=f"{key}  ({hint})", value=key, variable=var).pack(
                anchor="w", pady=2)

        def go():
            key = var.get()
            _, ext, _h = ph.FORMATS[key]
            path = filedialog.asksaveasfilename(defaultextension=ext, parent=win)
            if path:
                with open(path, "w") as f:
                    f.write(ph.render(rows, key) + "\n")
                self.lbl_log.configure(text=f"exported {len(rows)} as {key} → {path}")
            win.destroy()

        bar = ttk.Frame(frm)
        bar.pack(anchor="e", pady=(14, 0))
        ttk.Button(bar, text="Export", style="Go.TButton", command=go).pack(side="left")
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left", padx=8)

    def _popup(self, event):
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if self.tree.selection():
            self.menu.tk_popup(event.x_root, event.y_root)

    def _drop(self):
        gone = {self.tree.item(i, "values")[0] for i in self.tree.selection()}
        self.results = [r for r in self.results if r.proxy not in gone]
        self._repaint()
        self.lbl_log.configure(text=f"removed {len(gone)}")

    def copy(self, uri: bool = False):
        sel = self.tree.selection()
        picked = ([r for r in self._shown()
                   if r.proxy in {self.tree.item(i, "values")[0] for i in sel}] if sel
                  else self._shown())
        rows = [r.proxy for r in self._fresh(picked)]
        if not rows:
            self.lbl_log.configure(text="nothing left alive to copy")
            return
        if uri:
            rows = [f"socks5://{p}" for p in rows]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(rows))
        self.lbl_log.configure(text=f"{len(rows)} proxies copied to clipboard")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    sys.exit(main())
