#!/usr/bin/env python3
"""
WoW WTF Profile Sync Tool
Supports WoW 3.3.5a (WotLK) – browse your WTF folder and sync
character settings across accounts, realms, and characters.

Default profile: UTENSILE / AzerothCore / Utensile
"""

import os
import sys
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading

# ─── Defaults ────────────────────────────────────────────────────────────────
# Auto-detect WTF next to this script (works wherever you place it).
# Falls back to cwd if the folder doesn't exist yet.
_SCRIPT_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
_CANDIDATE  = _SCRIPT_DIR / "WTF"
DEFAULT_WTF = str(_CANDIDATE if _CANDIDATE.is_dir() else _SCRIPT_DIR)

DEFAULT_ACCT  = "UTENSILE"
DEFAULT_REALM = "AzerothCore"
DEFAULT_CHAR  = "Utensile"

# ─── What can be copied ───────────────────────────────────────────────────────
# Each entry: (level, filename, label)
#   level="char"  → WTF/Account/ACCT/REALM/CHAR/<filename>
#   level="acct"  → WTF/Account/ACCT/<filename>  (shared across all chars on that account)
SYNC_ITEMS = {
    "savedvars":   ("char", "SavedVariables",       "Addon SavedVariables  (.lua)"),
    "keybindings": ("char", "bindings-cache.wtf",   "Keybindings"),
    "macros":      ("char", "macros-cache.txt",     "Macros"),
    "layout":      ("char", "layout-local.txt",     "UI Layout"),
    "addons":      ("char", "AddOns.txt",           "Enabled Addons list"),
    "config":      ("char", "config.wtf",           "Character config.wtf"),
    "acct_config": ("acct", "config.wtf",           "Account config.wtf  (ActionBars, UI options)"),
    "acct_sv":     ("acct", "SavedVariables",       "Account SavedVariables  (.lua)"),
}

# ─── Colors / fonts ──────────────────────────────────────────────────────────
BG      = "#0e0f11"
BG2     = "#16181d"
BG3     = "#1f2229"
BORDER  = "#2d3040"
GOLD    = "#c8a84b"
GOLD2   = "#f0d080"
TEXT    = "#d4c9b0"
MUTED   = "#6e7080"
GREEN   = "#4caf7d"
RED     = "#e05c5c"
BLUE    = "#5b8dd9"
WHITE   = "#eae4d5"

import platform
_OS = platform.system()   # "Windows" | "Darwin" | "Linux"

if _OS == "Windows":
    FONT_TITLE = ("Georgia",   16, "bold")
    FONT_HEAD  = ("Georgia",   11, "bold")
    FONT_MONO  = ("Consolas",   9)
    FONT_BODY  = ("Segoe UI",   9)
    FONT_SMALL = ("Segoe UI",   8)
elif _OS == "Darwin":
    FONT_TITLE = ("Georgia",   16, "bold")
    FONT_HEAD  = ("Georgia",   11, "bold")
    FONT_MONO  = ("Menlo",      9)
    FONT_BODY  = ("Helvetica",  9)
    FONT_SMALL = ("Helvetica",  8)
else:                       # Linux
    FONT_TITLE = ("serif",     16, "bold")
    FONT_HEAD  = ("serif",     11, "bold")
    FONT_MONO  = ("monospace",  9)
    FONT_BODY  = ("sans-serif", 9)
    FONT_SMALL = ("sans-serif", 8)


# ─── Helper: scan WTF ────────────────────────────────────────────────────────
def scan_wtf(wtf_root: str) -> dict:
    """
    Returns nested dict:
      { account: { realm: [char, ...], ... }, ... }
    """
    result = {}
    acct_root = Path(wtf_root) / "Account"
    if not acct_root.is_dir():
        return result
    for acct in sorted(acct_root.iterdir()):
        if not acct.is_dir() or acct.name.startswith("."):
            continue
        result[acct.name] = {}
        for realm in sorted(acct.iterdir()):
            if not realm.is_dir() or realm.name in ("SavedVariables",) or realm.name.startswith("."):
                continue
            chars = []
            for char in sorted(realm.iterdir()):
                if char.is_dir() and not char.name.startswith("."):
                    chars.append(char.name)
            if chars:
                result[acct.name][realm.name] = chars
    return result


def char_path(wtf_root, account, realm, char):
    return Path(wtf_root) / "Account" / account / realm / char


def get_primary_monitor_geometry(fallback_w, fallback_h):
    """
    Return (width, height, x, y) of the primary monitor.
    winfo_screenwidth/height spans the whole virtual desktop on multi-monitor
    Linux/X11 setups, so we query the OS directly to get both size AND position.
    """
    import re

    if _OS == "Linux":
        try:
            import subprocess
            out = subprocess.check_output(
                ["xrandr", "--current"], text=True, stderr=subprocess.DEVNULL
            )
            # Prefer the monitor flagged as primary
            for line in out.splitlines():
                if " connected primary" in line:
                    m = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
                    if m:
                        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            # Fall back to first connected monitor
            for line in out.splitlines():
                if " connected" in line:
                    m = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
                    if m:
                        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        except Exception:
            pass

    elif _OS == "Windows":
        try:
            import ctypes
            u = ctypes.windll.user32
            # Primary monitor on Windows is always anchored at virtual-desktop origin (0, 0)
            w = u.GetSystemMetrics(0)
            h = u.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return w, h, 0, 0
        except Exception:
            pass

    # macOS: tkinter already returns just the primary monitor — no fix needed.
    return fallback_w, fallback_h, 0, 0


# ─── Main App ────────────────────────────────────────────────────────────────
class WTFSyncApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WoW WTF Profile Sync  ·  3.3.5a")
        self.configure(bg=BG)
        sw, sh, mx, my = get_primary_monitor_geometry(
            self.winfo_screenwidth(), self.winfo_screenheight()
        )
        w, h = sw // 2, sh // 2
        x    = mx + sw // 4   # centre within the primary monitor
        y    = my + sh // 4
        self.minsize(640, 420)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # State
        self.wtf_path   = tk.StringVar(value=DEFAULT_WTF)
        self.tree_data  = {}
        self.source_var = tk.StringVar(value="")   # "ACCT|REALM|CHAR"
        self.sync_vars  = {k: tk.BooleanVar(value=(k != "macros")) for k in SYNC_ITEMS}
        self.target_vars = {}   # "ACCT|REALM|CHAR" -> BooleanVar
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self._apply_styles()
        self.refresh_tree()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar ──
        hdr = tk.Frame(self, bg=BG, pady=0)
        hdr.pack(fill="x")
        tk.Frame(hdr, bg=GOLD, height=2).pack(fill="x")
        inner = tk.Frame(hdr, bg=BG, padx=18, pady=10)
        inner.pack(fill="x")
        tk.Label(inner, text="⚔  WTF Profile Sync", font=FONT_TITLE,
                 fg=GOLD2, bg=BG).pack(side="left")
        tk.Label(inner, text="World of Warcraft 3.3.5a", font=FONT_SMALL,
                 fg=MUTED, bg=BG).pack(side="left", padx=(12,0))

        # ── Path bar ──
        path_bar = tk.Frame(self, bg=BG2, padx=14, pady=8)
        path_bar.pack(fill="x")
        tk.Label(path_bar, text="WTF Root:", font=FONT_BODY, fg=MUTED, bg=BG2).pack(side="left")
        path_entry = tk.Entry(path_bar, textvariable=self.wtf_path, font=FONT_MONO,
                              bg=BG3, fg=TEXT, insertbackground=GOLD,
                              relief="flat", bd=0, width=55)
        path_entry.pack(side="left", padx=(8, 6), ipady=4)
        self._btn(path_bar, "Browse…", self._browse_wtf).pack(side="left", padx=4)
        self._btn(path_bar, "↺  Refresh", self.refresh_tree, accent=True).pack(side="left", padx=4)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Main 3-column layout ──
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=0, pady=0)
        main.columnconfigure(0, weight=3, minsize=260)
        main.columnconfigure(1, weight=0)
        main.columnconfigure(2, weight=5, minsize=380)
        main.rowconfigure(0, weight=1)

        # LEFT: tree
        left = tk.Frame(main, bg=BG2, bd=0)
        left.grid(row=0, column=0, sticky="nsew")
        self._build_tree_panel(left)

        # Divider
        tk.Frame(main, bg=BORDER, width=1).grid(row=0, column=1, sticky="ns")

        # RIGHT: controls
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=2, sticky="nsew")
        right.rowconfigure(1, weight=1)
        self._build_right_panel(right)

        # ── Status bar ──
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        status = tk.Frame(self, bg=BG2, padx=14, pady=6)
        status.pack(fill="x")
        tk.Label(status, textvariable=self.status_var, font=FONT_SMALL,
                 fg=MUTED, bg=BG2, anchor="w").pack(side="left")

    def _build_tree_panel(self, parent):
        hdr = tk.Frame(parent, bg=BG2, padx=12, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Characters", font=FONT_HEAD, fg=GOLD, bg=BG2).pack(side="left")
        tk.Label(hdr, text="(click = set source)", font=FONT_SMALL, fg=MUTED, bg=BG2).pack(side="left", padx=8)

        frame = tk.Frame(parent, bg=BG2)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.tag_configure("account", foreground=GOLD2)
        self.tree.tag_configure("realm",   foreground=BLUE)
        self.tree.tag_configure("char",    foreground=TEXT)
        self.tree.tag_configure("default", foreground=GREEN)

    def _build_right_panel(self, parent):
        # ── Source ──
        src_frame = tk.Frame(parent, bg=BG3, padx=16, pady=12)
        src_frame.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(src_frame, text="SOURCE  (copy from)", font=FONT_HEAD,
                 fg=GOLD, bg=BG3).pack(anchor="w")
        self.src_label = tk.Label(src_frame, text="— not selected —",
                                  font=FONT_MONO, fg=MUTED, bg=BG3, anchor="w")
        self.src_label.pack(fill="x", pady=(4, 0))
        self._btn(src_frame, "Use default (UTENSILE/AzerothCore/Utensile)",
                  self._set_default_source).pack(anchor="w", pady=(8, 0))

        # ── Sync options ──
        opt_outer = tk.Frame(parent, bg=BG, padx=12, pady=0)
        opt_outer.pack(fill="x", pady=(10, 0))
        tk.Label(opt_outer, text="WHAT TO COPY", font=FONT_HEAD, fg=GOLD, bg=BG).pack(anchor="w")
        opts = tk.Frame(opt_outer, bg=BG)
        opts.pack(fill="x", pady=(6, 0))
        col = 0
        for i, (key, (level, fname, label)) in enumerate(SYNC_ITEMS.items()):
            cb = tk.Checkbutton(opts, text=label, variable=self.sync_vars[key],
                                font=FONT_BODY, fg=TEXT, bg=BG,
                                activebackground=BG, activeforeground=GOLD2,
                                selectcolor=BG3, relief="flat", bd=0,
                                highlightthickness=0)
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 20), pady=2)

        # ── Targets ──
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(10, 0))
        tgt_hdr = tk.Frame(parent, bg=BG, padx=12, pady=8)
        tgt_hdr.pack(fill="x")
        tk.Label(tgt_hdr, text="TARGETS  (copy to)", font=FONT_HEAD,
                 fg=GOLD, bg=BG).pack(side="left")
        self._btn(tgt_hdr, "All",  lambda: self._toggle_all_targets(True),  small=True).pack(side="right", padx=2)
        self._btn(tgt_hdr, "None", lambda: self._toggle_all_targets(False), small=True).pack(side="right", padx=2)

        # Scrollable target list
        tgt_frame = tk.Frame(parent, bg=BG, padx=12)
        tgt_frame.pack(fill="both", expand=True, pady=(0, 8))

        canvas = tk.Canvas(tgt_frame, bg=BG, bd=0, highlightthickness=0)
        tgt_vsb = ttk.Scrollbar(tgt_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=tgt_vsb.set)
        tgt_vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self.tgt_inner = tk.Frame(canvas, bg=BG)
        self._tgt_window = canvas.create_window((0, 0), window=self.tgt_inner, anchor="nw")
        self.tgt_inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            self._tgt_window, width=e.width))
        self._canvas = canvas

        # ── Action buttons ──
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12)
        action = tk.Frame(parent, bg=BG, padx=12, pady=10)
        action.pack(fill="x")
        self._btn(action, "🌍  SYNC TO ALL CHARACTERS",
                  self._do_copy_all, accent=True, big=True).pack(side="left")
        self._btn(action, "⚡  Selected only",
                  self._do_copy, big=True).pack(side="left", padx=8)
        self._btn(action, "Preview", self._preview).pack(side="left", padx=4)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, accent=False, small=False, big=False):
        fg   = BG  if accent else TEXT
        bg   = GOLD if accent else BG3
        abg  = GOLD2 if accent else BORDER
        pad  = (6, 3) if small else (16, 6) if big else (10, 5)
        fnt  = (FONT_BODY[0], 8) if small else (FONT_BODY[0], 10, "bold") if big else FONT_BODY
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg=fg, activebackground=abg, activeforeground=BG,
                      font=fnt, relief="flat", bd=0,
                      padx=pad[0], pady=pad[1], cursor="hand2")
        return b

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                         background=BG2, foreground=TEXT,
                         fieldbackground=BG2, borderwidth=0,
                         font=FONT_BODY, rowheight=22)
        style.configure("Treeview.Heading", background=BG3, foreground=GOLD, font=FONT_HEAD)
        style.map("Treeview", background=[("selected", "#2a3050")],
                               foreground=[("selected", GOLD2)])
        style.configure("Vertical.TScrollbar",
                         background=BG3, troughcolor=BG2, arrowcolor=MUTED,
                         borderwidth=0, relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", BORDER)])

    # ── Tree management ───────────────────────────────────────────────────────
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_data = scan_wtf(self.wtf_path.get())
        if not self.tree_data:
            self.tree.insert("", "end", text="  ⚠  No characters found", tags=("muted",))
            self.status_var.set(f"No WTF structure found at: {self.wtf_path.get()}")
            self._build_target_list()
            return

        total = 0
        for acct, realms in self.tree_data.items():
            acct_id = self.tree.insert("", "end", text=f"🔑  {acct}",
                                        open=True, tags=("account",))
            for realm, chars in realms.items():
                realm_id = self.tree.insert(acct_id, "end", text=f"🌍  {realm}",
                                             open=True, tags=("realm",))
                for char in chars:
                    is_default = (acct == DEFAULT_ACCT and
                                  realm == DEFAULT_REALM and
                                  char == DEFAULT_CHAR)
                    tag   = "default" if is_default else "char"
                    label = f"{'★  ' if is_default else '   '}{char}"
                    self.tree.insert(realm_id, "end", text=label,
                                     iid=f"{acct}|{realm}|{char}", tags=(tag,))
                    total += 1

        # Auto-select default
        def_key = f"{DEFAULT_ACCT}|{DEFAULT_REALM}|{DEFAULT_CHAR}"
        if def_key in self.tree.get_children("") or self._iid_exists(def_key):
            self._select_source(DEFAULT_ACCT, DEFAULT_REALM, DEFAULT_CHAR)

        self._build_target_list()
        self.status_var.set(f"Loaded {total} character(s) across "
                            f"{sum(len(r) for r in self.tree_data.values())} realm(s).")

    def _iid_exists(self, iid):
        try:
            self.tree.item(iid)
            return True
        except tk.TclError:
            return False

    def _on_tree_select(self, _event):
        sel = self.tree.focus()
        if "|" in sel:
            acct, realm, char = sel.split("|")
            self._select_source(acct, realm, char)

    def _set_default_source(self):
        self._select_source(DEFAULT_ACCT, DEFAULT_REALM, DEFAULT_CHAR)
        if self._iid_exists(f"{DEFAULT_ACCT}|{DEFAULT_REALM}|{DEFAULT_CHAR}"):
            self.tree.focus(f"{DEFAULT_ACCT}|{DEFAULT_REALM}|{DEFAULT_CHAR}")
            self.tree.selection_set(f"{DEFAULT_ACCT}|{DEFAULT_REALM}|{DEFAULT_CHAR}")

    def _select_source(self, acct, realm, char):
        key = f"{acct}|{realm}|{char}"
        self.source_var.set(key)
        path = char_path(self.wtf_path.get(), acct, realm, char)
        exists = path.is_dir()
        colour = GREEN if exists else RED
        self.src_label.config(
            text=f"{acct}  /  {realm}  /  {char}{'  ✓' if exists else '  ✗ (not found)'}",
            fg=colour)
        self._build_target_list()

    # ── Target list ───────────────────────────────────────────────────────────
    def _build_target_list(self):
        for w in self.tgt_inner.winfo_children():
            w.destroy()
        self.target_vars.clear()

        source = self.source_var.get()
        row = 0
        for acct, realms in self.tree_data.items():
            for realm, chars in realms.items():
                for char in chars:
                    key = f"{acct}|{realm}|{char}"
                    if key == source:
                        continue
                    var = tk.BooleanVar(value=False)
                    self.target_vars[key] = var
                    frm = tk.Frame(self.tgt_inner, bg=BG)
                    frm.grid(row=row, column=0, sticky="ew", pady=1)
                    self.tgt_inner.columnconfigure(0, weight=1)
                    cb = tk.Checkbutton(frm, text=f"{acct}  /  {realm}  /  {char}",
                                        variable=var, font=FONT_BODY,
                                        fg=TEXT, bg=BG, selectcolor=BG3,
                                        activebackground=BG, activeforeground=GOLD2,
                                        relief="flat", bd=0, highlightthickness=0,
                                        anchor="w")
                    cb.pack(fill="x")
                    row += 1

        if row == 0:
            tk.Label(self.tgt_inner, text="No other characters found.",
                     font=FONT_SMALL, fg=MUTED, bg=BG).pack(anchor="w")

    def _toggle_all_targets(self, state):
        for var in self.target_vars.values():
            var.set(state)

    # ── Preview ───────────────────────────────────────────────────────────────
    def _preview(self):
        lines = self._build_plan()
        if lines is None:
            return
        if not lines:
            messagebox.showinfo("Preview", "Nothing to copy (no items/targets selected).")
            return
        win = tk.Toplevel(self, bg=BG)
        win.title("Copy Preview")
        win.geometry("640x480")
        txt = tk.Text(win, bg=BG2, fg=TEXT, font=FONT_MONO,
                      relief="flat", padx=10, pady=10)
        txt.pack(fill="both", expand=True)
        txt.insert("end", "\n".join(lines))
        txt.config(state="disabled")

    # ── Copy logic ────────────────────────────────────────────────────────────
    def _build_plan(self):
        """Returns list of description strings, or None on validation failure."""
        src = self.source_var.get()
        if not src:
            messagebox.showwarning("No Source", "Please select a source character first.")
            return None

        targets = [k for k, v in self.target_vars.items() if v.get()]
        if not targets:
            messagebox.showwarning("No Targets", "Please select at least one target character.")
            return None

        items_to_copy = [(key, level, fname) for key, (level, fname, _) in SYNC_ITEMS.items()
                         if self.sync_vars[key].get()]
        if not items_to_copy:
            messagebox.showwarning("Nothing Selected", "Please select at least one item type to copy.")
            return None

        acct_s, realm_s, char_s = src.split("|")
        wtf = self.wtf_path.get()
        src_char_root = char_path(wtf, acct_s, realm_s, char_s)
        src_acct_root = Path(wtf) / "Account" / acct_s
        lines = [f"SOURCE: {src}", f"CHAR:   {src_char_root}", ""]
        for tgt in targets:
            acct_t, realm_t, char_t = tgt.split("|")
            tgt_char_root = char_path(wtf, acct_t, realm_t, char_t)
            tgt_acct_root = Path(wtf) / "Account" / acct_t
            lines.append(f"→ TARGET: {tgt}")
            for key, level, fname in items_to_copy:
                src_item = (src_acct_root if level == "acct" else src_char_root) / fname
                tgt_item = (tgt_acct_root if level == "acct" else tgt_char_root) / fname
                tag = "[acct]" if level == "acct" else "[char]"
                exists = "✓" if src_item.exists() else "✗ (missing in source)"
                lines.append(f"    {tag} {fname:30s}  {exists}")
            lines.append("")
        return lines

    def _do_copy(self):
        src = self.source_var.get()
        if not src:
            messagebox.showwarning("No Source", "Please select a source character first.")
            return
        targets = [k for k, v in self.target_vars.items() if v.get()]
        if not targets:
            messagebox.showwarning("No Targets", "Please select at least one target character.")
            return
        items_to_copy = [(key, level, fname) for key, (level, fname, _) in SYNC_ITEMS.items()
                         if self.sync_vars[key].get()]
        if not items_to_copy:
            messagebox.showwarning("Nothing Selected", "Please select at least one item type to copy.")
            return

        # Confirmation
        msg = (f"Copy from:\n  {src.replace('|', ' / ')}\n\n"
               f"To {len(targets)} target(s):\n" +
               "\n".join(f"  {t.replace('|', ' / ')}" for t in targets) +
               f"\n\nItems: {', '.join(fname for _, _, fname in items_to_copy)}\n\n"
               "Continue?")
        if not messagebox.askyesno("Confirm Copy", msg):
            return

        def _run():
            self.status_var.set("Copying…")
            acct_s, realm_s, char_s = src.split("|")
            wtf = self.wtf_path.get()
            src_char_root = char_path(wtf, acct_s, realm_s, char_s)
            src_acct_root = Path(wtf) / "Account" / acct_s
            errors, done = [], 0
            for tgt in targets:
                acct_t, realm_t, char_t = tgt.split("|")
                tgt_char_root = char_path(wtf, acct_t, realm_t, char_t)
                tgt_char_root.mkdir(parents=True, exist_ok=True)
                tgt_acct_root = Path(wtf) / "Account" / acct_t
                tgt_acct_root.mkdir(parents=True, exist_ok=True)
                for key, level, fname in items_to_copy:
                    src_item = (src_acct_root if level == "acct" else src_char_root) / fname
                    tgt_item = (tgt_acct_root if level == "acct" else tgt_char_root) / fname
                    if not src_item.exists():
                        continue
                    try:
                        if src_item.is_dir():
                            if tgt_item.exists():
                                shutil.rmtree(tgt_item)
                            shutil.copytree(src_item, tgt_item)
                        else:
                            shutil.copy2(src_item, tgt_item)
                        done += 1
                    except Exception as e:
                        errors.append(f"{tgt}/{fname}: {e}")

            if errors:
                self.status_var.set(f"Done with {len(errors)} error(s). See details.")
                messagebox.showerror("Errors", "\n".join(errors))
            else:
                self.status_var.set(f"✓ Copied {done} item(s) to {len(targets)} character(s).")
                messagebox.showinfo("Done", f"Successfully copied {done} item(s) to {len(targets)} character(s).")

        threading.Thread(target=_run, daemon=True).start()

    def _do_copy_all(self):
        src = self.source_var.get()
        if not src:
            messagebox.showwarning("No Source", "Please select a source character first.")
            return
        items_to_copy = [(key, level, fname) for key, (level, fname, _) in SYNC_ITEMS.items()
                         if self.sync_vars[key].get()]
        if not items_to_copy:
            messagebox.showwarning("Nothing Selected", "Please select at least one item type to copy.")
            return

        # Every character except the source
        all_targets = list(self.target_vars.keys())
        if not all_targets:
            messagebox.showwarning("No Targets", "No other characters found to sync to.")
            return

        count = len(all_targets)
        msg = (f"Sync from:\n  {src.replace('|', ' / ')}\n\n"
               f"To ALL {count} other character(s) — every account, every realm.\n\n"
               f"Items: {', '.join(fname for _, _, fname in items_to_copy)}\n\n"
               "⚠  This will overwrite existing settings. Continue?")
        if not messagebox.askyesno("Confirm Sync All", msg, icon="warning"):
            return

        def _run():
            self.status_var.set(f"Syncing to all {count} characters…")
            acct_s, realm_s, char_s = src.split("|")
            wtf = self.wtf_path.get()
            src_char_root = char_path(wtf, acct_s, realm_s, char_s)
            src_acct_root = Path(wtf) / "Account" / acct_s
            errors, done = [], 0
            for tgt in all_targets:
                acct_t, realm_t, char_t = tgt.split("|")
                tgt_char_root = char_path(wtf, acct_t, realm_t, char_t)
                tgt_char_root.mkdir(parents=True, exist_ok=True)
                tgt_acct_root = Path(wtf) / "Account" / acct_t
                tgt_acct_root.mkdir(parents=True, exist_ok=True)
                for key, level, fname in items_to_copy:
                    src_item = (src_acct_root if level == "acct" else src_char_root) / fname
                    tgt_item = (tgt_acct_root if level == "acct" else tgt_char_root) / fname
                    if not src_item.exists():
                        continue
                    try:
                        if src_item.is_dir():
                            if tgt_item.exists():
                                shutil.rmtree(tgt_item)
                            shutil.copytree(src_item, tgt_item)
                        else:
                            shutil.copy2(src_item, tgt_item)
                        done += 1
                    except Exception as e:
                        errors.append(f"{tgt}/{fname}: {e}")

            if errors:
                self.status_var.set(f"Sync done with {len(errors)} error(s).")
                messagebox.showerror("Errors", "\n".join(errors))
            else:
                self.status_var.set(f"✓ Synced {done} item(s) across {count} character(s).")
                messagebox.showinfo("Sync Complete",
                                    f"✓ Synced to all {count} character(s)!\n({done} item(s) copied)")

        threading.Thread(target=_run, daemon=True).start()

    def _browse_wtf(self):
        d = filedialog.askdirectory(title="Select WTF folder",
                                    initialdir=self.wtf_path.get())
        if d:
            self.wtf_path.set(d)
            self.refresh_tree()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = WTFSyncApp()
    app.mainloop()
