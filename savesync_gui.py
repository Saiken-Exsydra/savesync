"""
SaveSync GUI — CustomTkinter frontend for SaveSync.
Imports all logic from savesync.py — never modifies it.

Dependencies:
    pip install customtkinter
"""

import os
import sys
import json
import threading
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

# ---------------------------------------------------------------
# Import everything from savesync.py (the logic layer)
# ---------------------------------------------------------------
import savesync as ss

# ---------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

# Colour palette
COL_BG_DARK    = "#1a1a2e"
COL_BG_CARD    = "#16213e"
COL_BG_SIDEBAR = "#0f3460"
COL_ACCENT     = "#3b82f6"
COL_ACCENT_HVR = "#2563eb"
COL_SUCCESS    = "#22c55e"
COL_WARNING    = "#f59e0b"
COL_ERROR      = "#ef4444"
COL_TEXT       = "#e2e8f0"
COL_TEXT_DIM   = "#94a3b8"
COL_CARD_HOVER = "#1e3a5f"

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_HEAD   = ("Segoe UI", 15, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_MONO   = ("Consolas", 11)


# ---------------------------------------------------------------
# Helper: ensure_manifest_ready (reimplemented — the def line is
# missing in savesync.py but the body exists)
# ---------------------------------------------------------------
def ensure_manifest_ready(silent=False) -> bool:
    """Check if manifest and index are available."""
    if ss.MANIFEST_INDEX.exists():
        return True
    if not ss.MANIFEST_FILE.exists():
        if not ss.download_manifest(silent=True):
            return False
    if not ss.MANIFEST_INDEX.exists():
        if not ss.build_manifest_index(silent=True):
            return False
    return True


# ---------------------------------------------------------------
# Threaded runner — runs func in a thread, calls on_done(result)
# on the main thread via widget.after()
# ---------------------------------------------------------------
def run_in_thread(widget, func, on_done=None, on_error=None):
    """Execute *func* in a daemon thread.  When it finishes, schedule
    *on_done(result)* or *on_error(exception)* on the main thread."""
    def _worker():
        try:
            result = func()
            if on_done:
                widget.after(0, lambda: on_done(result))
        except Exception as e:
            if on_error:
                widget.after(0, lambda: on_error(e))
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


# ===============================================================
#  MAIN APPLICATION
# ===============================================================

class SaveSyncApp(ctk.CTk):
    """Root window — two-panel layout with sidebar navigation."""

    def __init__(self):
        super().__init__()
        self.title("SaveSync")
        self.geometry("980x680")
        self.minsize(880, 580)

        # ── State ──────────────────────────────────────────────
        self.watcher: ss.GameWatcher | None = None
        self.watcher_running = False
        self.active_nav: str = ""

        # ── Grid: sidebar (col 0, fixed) | content (col 1, expand)
        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)   # status bar

        # ── Sidebar ───────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # ── Content area ──────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # ── Status bar ────────────────────────────────────────
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self.statusbar.grid(row=1, column=1, sticky="ew")
        self.statusbar.grid_propagate(False)
        self._build_statusbar()

        # ── Show games panel by default ───────────────────────
        self.show_panel("games")

        # ── Background: check manifest update ─────────────────
        threading.Thread(target=ss.check_manifest_update_silently, daemon=True).start()

        # ── Periodic status refresh ───────────────────────────
        self._refresh_status()

    # -----------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------
    def _build_sidebar(self):
        # Logo / title
        logo = ctk.CTkLabel(self.sidebar, text="SaveSync",
                            font=("Segoe UI", 22, "bold"),
                            text_color=COL_ACCENT)
        logo.pack(pady=(24, 4))
        sub = ctk.CTkLabel(self.sidebar, text="Game Save Backup Manager",
                           font=FONT_SMALL, text_color=COL_TEXT_DIM)
        sub.pack(pady=(0, 20))

        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=COL_TEXT_DIM)
        sep.pack(fill="x", padx=16, pady=(0, 12))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("games",     "Games"),
            ("backup",    "Backup Now"),
            ("restore",   "Restore"),
            ("watcher",   "Watcher"),
            ("settings",  "Settings"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {label}", anchor="w",
                font=FONT_BODY, height=38, corner_radius=8,
                fg_color="transparent", text_color=COL_TEXT,
                hover_color=COL_ACCENT_HVR,
                command=lambda k=key: self.show_panel(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn

        # Watcher status dot (updated periodically)
        self.watcher_dot = ctk.CTkLabel(self.sidebar, text="",
                                        font=FONT_SMALL, text_color=COL_TEXT_DIM)
        self.watcher_dot.pack(side="bottom", pady=(0, 12))

    def _highlight_nav(self, key: str):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=COL_ACCENT, text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=COL_TEXT)

    # -----------------------------------------------------------
    # Status bar
    # -----------------------------------------------------------
    def _build_statusbar(self):
        self.lbl_status_backup = ctk.CTkLabel(
            self.statusbar, text="", font=FONT_SMALL, text_color=COL_TEXT_DIM)
        self.lbl_status_backup.pack(side="left", padx=12)

        self.lbl_status_watcher = ctk.CTkLabel(
            self.statusbar, text="Watcher: stopped", font=FONT_SMALL,
            text_color=COL_TEXT_DIM)
        self.lbl_status_watcher.pack(side="right", padx=12)

        self.lbl_status_update = ctk.CTkLabel(
            self.statusbar, text="", font=FONT_SMALL, text_color=COL_WARNING)
        self.lbl_status_update.pack(side="right", padx=12)

    def _refresh_status(self):
        """Periodically update the status bar."""
        # Last backup timestamp
        cfg = ss.load_config()
        games = cfg.get("games", [])
        timestamps = [g.get("backup_timestamp", "") for g in games if g.get("backup_timestamp")]
        if timestamps:
            latest = max(timestamps)
            self.lbl_status_backup.configure(text=f"Last backup: {ss.fmt_ts(latest)}")
        else:
            self.lbl_status_backup.configure(text="No backups yet")

        # Watcher state
        if self.watcher_running:
            self.lbl_status_watcher.configure(text="Watcher: running", text_color=COL_SUCCESS)
            self.watcher_dot.configure(text="● Watcher active", text_color=COL_SUCCESS)
        else:
            self.lbl_status_watcher.configure(text="Watcher: stopped", text_color=COL_TEXT_DIM)
            self.watcher_dot.configure(text="○ Watcher stopped", text_color=COL_TEXT_DIM)

        # DB update available?
        meta = ss._load_manifest_meta()
        if meta.get("update_available"):
            self.lbl_status_update.configure(text="★ DB update available")
        else:
            self.lbl_status_update.configure(text="")

        self.after(5000, self._refresh_status)

    # -----------------------------------------------------------
    # Panel switching
    # -----------------------------------------------------------
    def show_panel(self, name: str):
        """Destroy current content children and build the requested panel."""
        self.active_nav = name
        self._highlight_nav(name)
        for w in self.content.winfo_children():
            w.destroy()

        builders = {
            "games":    self._panel_games,
            "backup":   self._panel_backup,
            "restore":  self._panel_restore,
            "watcher":  self._panel_watcher,
            "settings": self._panel_settings,
        }
        builder = builders.get(name)
        if builder:
            builder()

    # ===============================================================
    #  PANEL: Games
    # ===============================================================
    def _panel_games(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        # Header row
        hdr = ctk.CTkFrame(frame, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hdr, text="My Games", font=FONT_TITLE).pack(side="left")
        ctk.CTkButton(hdr, text="+ Add Game", width=120, font=FONT_BODY,
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       command=self._open_add_game_dialog).pack(side="right")

        # Scrollable game list
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        cfg = ss.load_config()
        games = cfg.get("games", [])

        if not games:
            ctk.CTkLabel(scroll, text="No games configured yet.\nClick '+ Add Game' to get started.",
                         font=FONT_BODY, text_color=COL_TEXT_DIM).pack(pady=40)
            return

        for g in games:
            self._game_card(scroll, g)

    def _game_card(self, parent, game: dict):
        """Render a single game card."""
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=1,
                            border_color=COL_TEXT_DIM)
        card.pack(fill="x", pady=4, padx=2)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        # Name
        ctk.CTkLabel(inner, text=game["name"], font=FONT_HEAD).pack(anchor="w")

        # Destinations
        dests = []
        if game.get("drive_folder"): dests.append("Drive")
        if game.get("archive_path"): dests.append(".7z")
        if game.get("local_copy"):   dests.append("Local")
        dest_str = " · ".join(dests) if dests else "No destination"

        # Last backup
        ts = game.get("backup_timestamp", "")
        ts_str = ss.fmt_ts(ts) if ts else "never"

        info = f"Backup to: {dest_str}   |   Last: {ts_str}"
        ctk.CTkLabel(inner, text=info, font=FONT_SMALL,
                     text_color=COL_TEXT_DIM).pack(anchor="w", pady=(2, 0))

        # Save path
        ctk.CTkLabel(inner, text=game.get("save_path", ""),
                     font=FONT_MONO, text_color=COL_TEXT_DIM).pack(anchor="w", pady=(2, 0))

        # Watcher info
        if game.get("exe_name"):
            triggers = []
            if game.get("trigger_launch"): triggers.append("on launch")
            if game.get("trigger_close"):  triggers.append("on close")
            iv = game.get("interval_min", 0)
            if iv: triggers.append(f"every {iv} min")
            trig_str = ", ".join(triggers) if triggers else "manual only"
            ctk.CTkLabel(inner, text=f"Watches: {game['exe_name']}  ({trig_str})",
                         font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="w", pady=(2, 0))

        # Remove button
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="e", pady=(6, 0))
        ctk.CTkButton(btn_row, text="Remove", width=80, height=28,
                       font=FONT_SMALL, fg_color=COL_ERROR,
                       hover_color="#dc2626",
                       command=lambda g=game: self._remove_game(g)).pack(side="right")
        ctk.CTkButton(btn_row, text="Backup", width=80, height=28,
                       font=FONT_SMALL, fg_color=COL_ACCENT,
                       hover_color=COL_ACCENT_HVR,
                       command=lambda g=game: self._quick_backup(g)).pack(side="right", padx=(0, 6))

    def _remove_game(self, game: dict):
        if not messagebox.askyesno("Remove Game",
                                   f"Remove '{game['name']}' from SaveSync?\n\n"
                                   "Your save files and backups are NOT deleted."):
            return
        cfg = ss.load_config()
        cfg["games"] = [g for g in cfg["games"] if g["name"] != game["name"]]
        ss.save_config(cfg)
        ss.log.info(f"Removed game: {game['name']}")
        self.show_panel("games")

    def _quick_backup(self, game: dict):
        """Run a backup for a single game in a thread."""
        win = ctk.CTkToplevel(self)
        win.title(f"Backing up {game['name']}")
        win.geometry("460x200")
        win.resizable(False, False)
        win.grab_set()
        lbl = ctk.CTkLabel(win, text=f"Backing up {game['name']}...",
                           font=FONT_BODY)
        lbl.pack(pady=20)
        prog = ctk.CTkProgressBar(win, width=380)
        prog.pack(pady=10)
        prog.configure(mode="indeterminate")
        prog.start()
        log_box = ctk.CTkTextbox(win, width=380, height=60, font=FONT_MONO,
                                  state="disabled")
        log_box.pack(pady=10)

        def _do():
            return ss.run_backup(game, reason="manual (GUI)", silent=True)

        def _done(ok):
            prog.stop()
            if ok:
                lbl.configure(text=f"✓ Backup complete for {game['name']}", text_color=COL_SUCCESS)
            else:
                lbl.configure(text=f"✗ Backup failed for {game['name']}", text_color=COL_ERROR)
            self._refresh_status()
            win.after(2000, win.destroy)
            # Reload the config so timestamps update
            if self.active_nav == "games":
                self.after(2100, lambda: self.show_panel("games"))

        def _err(e):
            prog.stop()
            lbl.configure(text=f"✗ Error: {e}", text_color=COL_ERROR)

        run_in_thread(self, _do, _done, _err)

    # ===============================================================
    #  ADD GAME DIALOG (6-step wizard as CTkToplevel)
    # ===============================================================
    def _open_add_game_dialog(self):
        AddGameWizard(self)

    # ===============================================================
    #  PANEL: Backup Now
    # ===============================================================
    def _panel_backup(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Backup Now", font=FONT_TITLE).pack(anchor="w", pady=(0, 12))

        cfg = ss.load_config()
        games = cfg.get("games", [])

        if not games:
            ctk.CTkLabel(frame, text="No games configured yet.",
                         font=FONT_BODY, text_color=COL_TEXT_DIM).pack(pady=40)
            return

        ctk.CTkLabel(frame, text="Select a game and click Run to back up immediately.",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w", pady=(0, 8))

        # Dropdown
        self._backup_game_var = ctk.StringVar(value=games[0]["name"])
        dropdown = ctk.CTkOptionMenu(frame, values=[g["name"] for g in games],
                                      variable=self._backup_game_var,
                                      font=FONT_BODY, width=360)
        dropdown.pack(anchor="w", pady=(0, 12))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(anchor="w")
        self._backup_run_btn = ctk.CTkButton(
            btn_row, text="Run Backup", font=FONT_BODY, width=140,
            fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
            command=self._run_backup_panel)
        self._backup_run_btn.pack(side="left")

        # Progress bar
        self._backup_progress = ctk.CTkProgressBar(frame, width=500)
        self._backup_progress.pack(anchor="w", pady=(16, 4))
        self._backup_progress.set(0)

        # Log text
        self._backup_log = ctk.CTkTextbox(frame, font=FONT_MONO, height=260)
        self._backup_log.pack(fill="both", expand=True, pady=(4, 0))
        self._backup_log.configure(state="disabled")

    def _run_backup_panel(self):
        name = self._backup_game_var.get()
        cfg = ss.load_config()
        game = next((g for g in cfg["games"] if g["name"] == name), None)
        if not game:
            return

        self._backup_run_btn.configure(state="disabled", text="Running...")
        self._backup_progress.configure(mode="indeterminate")
        self._backup_progress.start()
        self._backup_log.configure(state="normal")
        self._backup_log.delete("1.0", "end")
        self._backup_log.insert("end", f"Starting backup for {name}...\n")
        self._backup_log.configure(state="disabled")

        def _do():
            return ss.run_backup(game, reason="manual (GUI)", silent=True)

        def _done(ok):
            self._backup_progress.stop()
            self._backup_progress.configure(mode="determinate")
            self._backup_progress.set(1.0 if ok else 0)
            self._backup_log.configure(state="normal")
            if ok:
                self._backup_log.insert("end", f"\n✓ Backup complete for {name}.\n")
            else:
                self._backup_log.insert("end", f"\n✗ Backup failed. Check savesync.log.\n")
            self._backup_log.configure(state="disabled")
            self._backup_run_btn.configure(state="normal", text="Run Backup")
            self._refresh_status()

        def _err(e):
            self._backup_progress.stop()
            self._backup_progress.configure(mode="determinate")
            self._backup_progress.set(0)
            self._backup_log.configure(state="normal")
            self._backup_log.insert("end", f"\n✗ Error: {e}\n")
            self._backup_log.configure(state="disabled")
            self._backup_run_btn.configure(state="normal", text="Run Backup")

        run_in_thread(self, _do, _done, _err)

    # ===============================================================
    #  PANEL: Restore from Drive
    # ===============================================================
    def _panel_restore(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Restore from Drive", font=FONT_TITLE).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(frame, text="Lists game folders from your Google Drive SaveSync folder.",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w", pady=(0, 12))

        self._restore_list_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self._restore_list_frame.pack(fill="both", expand=True)

        self._restore_status = ctk.CTkLabel(frame, text="", font=FONT_SMALL,
                                            text_color=COL_TEXT_DIM)
        self._restore_status.pack(anchor="w", pady=(4, 0))

        # Load drive folders in thread
        loading = ctk.CTkLabel(self._restore_list_frame, text="Connecting to Google Drive...",
                               font=FONT_BODY, text_color=COL_TEXT_DIM)
        loading.pack(pady=40)

        def _fetch():
            service = ss.get_drive_service()
            folders = ss.list_drive_game_folders(service)
            return service, folders

        def _done(result):
            service, folders = result
            loading.destroy()
            if not folders:
                ctk.CTkLabel(self._restore_list_frame,
                             text="No game folders found in SaveSync on Drive.",
                             font=FONT_BODY, text_color=COL_TEXT_DIM).pack(pady=40)
                return
            for folder_name, folder_id in folders:
                self._restore_card(self._restore_list_frame, service, folder_name, folder_id)

        def _err(e):
            loading.configure(text=f"Could not connect to Drive: {e}", text_color=COL_ERROR)

        run_in_thread(self, _fetch, _done, _err)

    def _restore_card(self, parent, service, folder_name: str, folder_id: str):
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=1,
                            border_color=COL_TEXT_DIM)
        card.pack(fill="x", pady=4, padx=2)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(inner, text=folder_name, font=FONT_HEAD).pack(anchor="w")

        # Try fetching timestamp
        try:
            dcfg = ss.fetch_game_config_from_drive(service, folder_id)
            ts = dcfg.get("backup_timestamp", "") if dcfg else ""
            if ts:
                ctk.CTkLabel(inner, text=f"Last backup: {ss.fmt_ts(ts)}",
                             font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="w")
        except Exception:
            pass

        ctk.CTkButton(inner, text="Restore", width=100, height=28,
                       font=FONT_SMALL, fg_color=COL_ACCENT,
                       hover_color=COL_ACCENT_HVR,
                       command=lambda fn=folder_name, fi=folder_id, svc=service:
                           self._do_restore(svc, fn, fi)).pack(anchor="e", pady=(4, 0))

    def _do_restore(self, service, folder_name, folder_id):
        """Perform a restore with progress dialog."""
        # Determine restore path
        cfg = ss.load_config()
        matched = next((g for g in cfg["games"] if g["name"] == folder_name), None)
        dcfg = None
        try:
            dcfg = ss.fetch_game_config_from_drive(service, folder_id)
        except Exception:
            pass

        if matched:
            default_path = matched["save_path"]
        elif dcfg and dcfg.get("save_path"):
            default_path = dcfg["save_path"]
        else:
            default_path = ""

        # Ask user for path
        path = filedialog.askdirectory(title=f"Restore path for {folder_name}",
                                       initialdir=default_path or None)
        if not path:
            return

        if not messagebox.askyesno("Confirm Restore",
                                   f"Restore '{folder_name}' to:\n{path}\n\n"
                                   "Current local saves will be snapshot first."):
            return

        # Progress dialog
        win = ctk.CTkToplevel(self)
        win.title(f"Restoring {folder_name}")
        win.geometry("500x180")
        win.resizable(False, False)
        win.grab_set()
        lbl = ctk.CTkLabel(win, text=f"Restoring {folder_name}...", font=FONT_BODY)
        lbl.pack(pady=20)
        prog = ctk.CTkProgressBar(win, width=420)
        prog.pack(pady=10)
        prog.configure(mode="indeterminate")
        prog.start()

        def _do():
            import py7zr
            save_files = ss.list_drive_save_files(service, folder_id)
            if not save_files:
                raise RuntimeError("No save files found on Drive.")

            local_save_path = Path(path)

            # Snapshot existing saves
            if local_save_path.exists():
                existing = [f for f in local_save_path.rglob("*") if f.is_file()]
                if existing:
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    snap_dir = ss.BASE_DIR / "restore_snapshots"
                    snap_dir.mkdir(exist_ok=True)
                    safe_name = folder_name.replace(" ", "_")
                    snapshot = snap_dir / f"{safe_name}_before_restore_{ts}.7z"
                    with py7zr.SevenZipFile(snapshot, "w") as zf:
                        for f in existing:
                            zf.write(f, arcname=f.name)

            # Download files
            for f in save_files:
                dest = local_save_path / f["name"]
                ss.download_file_from_drive(service, f["id"], dest)

            # Auto-import if not already configured
            if not matched and dcfg:
                dcfg["save_path"] = path
                local_cfg = ss.load_config()
                local_cfg["games"].append(dcfg)
                ss.save_config(local_cfg)

            return len(save_files)

        def _done(count):
            prog.stop()
            lbl.configure(text=f"✓ Restored {count} file(s) to {path}",
                          text_color=COL_SUCCESS)
            win.after(2500, win.destroy)

        def _err(e):
            prog.stop()
            lbl.configure(text=f"✗ Error: {e}", text_color=COL_ERROR)

        run_in_thread(self, _do, _done, _err)

    # ===============================================================
    #  PANEL: Watcher
    # ===============================================================
    def _panel_watcher(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Watcher", font=FONT_TITLE).pack(anchor="w", pady=(0, 6))

        desc = ("The watcher runs in the background and monitors your registered games. "
                "When it detects a game opening or closing, it backs up your saves automatically.")
        ctk.CTkLabel(frame, text=desc, font=FONT_BODY, text_color=COL_TEXT_DIM,
                     wraplength=600, justify="left").pack(anchor="w", pady=(0, 16))

        # Start / Stop toggle
        self._watcher_btn = ctk.CTkButton(
            frame, text="Start Watcher", font=FONT_BODY, width=180, height=40,
            fg_color=COL_SUCCESS if not self.watcher_running else COL_ERROR,
            hover_color="#16a34a" if not self.watcher_running else "#dc2626",
            command=self._toggle_watcher)
        self._watcher_btn.pack(anchor="w", pady=(0, 12))
        self._update_watcher_btn()

        # Status dot
        self._watcher_status_lbl = ctk.CTkLabel(
            frame, text="● Stopped" if not self.watcher_running else "● Running",
            font=FONT_BODY,
            text_color=COL_ERROR if not self.watcher_running else COL_SUCCESS)
        self._watcher_status_lbl.pack(anchor="w", pady=(0, 16))

        # Watched processes list
        cfg = ss.load_config()
        games = cfg.get("games", [])
        watchable = [g for g in games if g.get("exe_name")]

        if watchable:
            ctk.CTkLabel(frame, text="Watched processes:", font=FONT_HEAD).pack(anchor="w", pady=(8, 4))
            for g in watchable:
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(anchor="w", padx=8, pady=1)
                ctk.CTkLabel(row, text=f"• {g['name']}",
                             font=FONT_BODY).pack(side="left")
                ctk.CTkLabel(row, text=f"  ({g.get('exe_name', '')})",
                             font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(side="left")
        else:
            ctk.CTkLabel(frame, text="No games have a process name configured for watching.",
                         font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w", pady=8)

        # Separator
        ctk.CTkFrame(frame, height=1, fg_color=COL_TEXT_DIM).pack(fill="x", pady=16)

        # Startup task section
        ctk.CTkLabel(frame, text="Windows Startup Task", font=FONT_HEAD).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(frame, text="Install or remove the Windows Task Scheduler entry so the watcher starts automatically at login.",
                     font=FONT_BODY, text_color=COL_TEXT_DIM, wraplength=600,
                     justify="left").pack(anchor="w", pady=(0, 8))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(anchor="w")
        ctk.CTkButton(btn_row, text="Install Startup Task", font=FONT_BODY, width=180,
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       command=lambda: self._manage_startup_task("install")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Remove Startup Task", font=FONT_BODY, width=180,
                       fg_color=COL_ERROR, hover_color="#dc2626",
                       command=lambda: self._manage_startup_task("remove")).pack(side="left")

    def _update_watcher_btn(self):
        if self.watcher_running:
            self._watcher_btn.configure(text="Stop Watcher", fg_color=COL_ERROR,
                                        hover_color="#dc2626")
        else:
            self._watcher_btn.configure(text="Start Watcher", fg_color=COL_SUCCESS,
                                        hover_color="#16a34a")

    def _toggle_watcher(self):
        if self.watcher_running:
            # Stop
            if self.watcher:
                self.watcher.stop()
                self.watcher = None
            self.watcher_running = False
        else:
            # Start
            cfg = ss.load_config()
            games = cfg.get("games", [])
            watchable = [g for g in games if g.get("exe_name")]
            if not watchable:
                messagebox.showwarning("No Games", "No games have a process name set for watching.")
                return
            self.watcher = ss.GameWatcher(games)
            self.watcher.start()
            self.watcher_running = True
            # Also fire manifest update check
            threading.Thread(target=ss._watcher_check_manifest_update, daemon=True).start()

        self._update_watcher_btn()
        if hasattr(self, '_watcher_status_lbl'):
            if self.watcher_running:
                self._watcher_status_lbl.configure(text="● Running", text_color=COL_SUCCESS)
            else:
                self._watcher_status_lbl.configure(text="● Stopped", text_color=COL_ERROR)
        self._refresh_status()

    def _manage_startup_task(self, mode: str):
        """Install or remove the Windows startup task."""
        import platform
        import subprocess

        if platform.system() != "Windows":
            messagebox.showinfo("Not Available", "This feature is only available on Windows.")
            return

        task_name = "SaveSyncWatcher"
        py_path = Path(sys.executable)
        pythonw = py_path.parent / "pythonw.exe"
        if not pythonw.exists():
            pythonw = py_path
        script_path = Path(ss.__file__).resolve()

        if mode == "remove":
            check = subprocess.run(["schtasks", "/query", "/tn", task_name],
                                   capture_output=True)
            if check.returncode != 0:
                messagebox.showinfo("Not Installed", "No startup task is currently installed.")
                return
            if not messagebox.askyesno("Confirm", "Remove the SaveSync startup task?"):
                return
            result = subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                messagebox.showinfo("Done", "Startup task removed successfully.")
            else:
                messagebox.showerror("Error", f"Failed to remove task:\n{result.stderr.strip()}")
        else:
            # Install
            check = subprocess.run(["schtasks", "/query", "/tn", task_name],
                                   capture_output=True)
            if check.returncode == 0:
                if not messagebox.askyesno("Update", "A startup task already exists. Update it?"):
                    return
                subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"],
                               capture_output=True)

            if not messagebox.askyesno("Confirm",
                                       f"Install SaveSync watcher as a Windows startup task?\n\n"
                                       f"Script: {script_path}\nRuntime: {pythonw}"):
                return

            cmd = [
                "schtasks", "/create",
                "/tn", task_name,
                "/tr", f'"{pythonw}" "{script_path}" --watch',
                "/sc", "ONLOGON",
                "/rl", "HIGHEST",
                "/f",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                messagebox.showinfo("Done", "Startup task installed. The watcher will start automatically at login.")
            else:
                messagebox.showerror("Error",
                                     f"Failed to install task:\n{result.stderr.strip()}\n\n"
                                     "Try running SaveSync as Administrator.")

    # ===============================================================
    #  PANEL: Settings
    # ===============================================================
    def _panel_settings(self):
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(frame, text="Settings", font=FONT_TITLE).pack(anchor="w", pady=(0, 16))

        # --- Google Drive Setup ---
        self._settings_section(frame, "Google Drive Setup",
                               "Connect SaveSync to your Google account for cloud backups.",
                               "Connect / Authenticate", self._settings_drive_setup)

        # --- Game Database ---
        meta = ss._load_manifest_meta()
        age = ss.manifest_db_age()
        idx_count = 0
        if ss.MANIFEST_INDEX.exists():
            try:
                idx = json.loads(ss.MANIFEST_INDEX.read_text(encoding="utf-8"))
                idx_count = len(idx)
            except Exception:
                pass

        db_desc = f"Ludusavi community database — {idx_count:,} games indexed, {age}."
        if meta.get("update_available"):
            db_desc += "\n★ A newer version is available!"

        self._settings_section(frame, "Game Database", db_desc,
                               "Download / Update", self._settings_download_db)

        # --- Health Check ---
        self._settings_section(frame, "Health Check",
                               "Scan all games and verify save paths, Drive folders, and archives.",
                               "Run Health Check", self._settings_health_check)

    def _settings_section(self, parent, title, desc, btn_text, btn_cmd):
        sec = ctk.CTkFrame(parent, corner_radius=10, border_width=1,
                           border_color=COL_TEXT_DIM)
        sec.pack(fill="x", pady=6)
        inner = ctk.CTkFrame(sec, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(inner, text=title, font=FONT_HEAD).pack(anchor="w")
        ctk.CTkLabel(inner, text=desc, font=FONT_SMALL,
                     text_color=COL_TEXT_DIM, wraplength=560,
                     justify="left").pack(anchor="w", pady=(2, 6))
        ctk.CTkButton(inner, text=btn_text, font=FONT_BODY, width=200,
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       command=btn_cmd).pack(anchor="w")

    def _settings_drive_setup(self):
        if not ss.GDRIVE_AVAILABLE:
            messagebox.showwarning("Missing Libraries",
                                   "Google API libraries not installed.\n\n"
                                   "Run: pip install google-auth google-auth-oauthlib google-api-python-client")
            return
        if not ss.CREDS_FILE.exists():
            messagebox.showwarning("Missing Credentials",
                                   f"Credentials file not found:\n{ss.CREDS_FILE}\n\n"
                                   "See README for setup instructions.")
            return

        # Run OAuth in thread
        win = ctk.CTkToplevel(self)
        win.title("Google Drive Setup")
        win.geometry("420x140")
        win.resizable(False, False)
        win.grab_set()
        lbl = ctk.CTkLabel(win, text="Opening browser for authentication...", font=FONT_BODY)
        lbl.pack(pady=30)

        def _do():
            service = ss.get_drive_service()
            about = service.about().get(fields="user").execute()
            return about["user"]["emailAddress"]

        def _done(email):
            lbl.configure(text=f"✓ Authenticated as: {email}", text_color=COL_SUCCESS)
            win.after(2500, win.destroy)

        def _err(e):
            lbl.configure(text=f"✗ Error: {e}", text_color=COL_ERROR)

        run_in_thread(self, _do, _done, _err)

    def _settings_download_db(self):
        win = ctk.CTkToplevel(self)
        win.title("Game Database")
        win.geometry("500x200")
        win.resizable(False, False)
        win.grab_set()
        lbl = ctk.CTkLabel(win, text="Downloading Ludusavi database...", font=FONT_BODY)
        lbl.pack(pady=20)
        prog = ctk.CTkProgressBar(win, width=420)
        prog.pack(pady=10)
        prog.configure(mode="indeterminate")
        prog.start()
        detail = ctk.CTkLabel(win, text="This may take a moment on slow connections.",
                              font=FONT_SMALL, text_color=COL_TEXT_DIM)
        detail.pack(pady=8)

        def _do():
            ok = ss.download_manifest(silent=True)
            if ok:
                ss.build_manifest_index(silent=True)
            return ok

        def _done(ok):
            prog.stop()
            if ok:
                idx_count = 0
                if ss.MANIFEST_INDEX.exists():
                    try:
                        idx = json.loads(ss.MANIFEST_INDEX.read_text(encoding="utf-8"))
                        idx_count = len(idx)
                    except Exception:
                        pass
                lbl.configure(text=f"✓ Database downloaded — {idx_count:,} games indexed.",
                              text_color=COL_SUCCESS)
                detail.configure(text="")
            else:
                lbl.configure(text="✗ Download failed.", text_color=COL_ERROR)
            win.after(2500, win.destroy)
            if self.active_nav == "settings":
                self.after(2600, lambda: self.show_panel("settings"))

        def _err(e):
            prog.stop()
            lbl.configure(text=f"✗ Error: {e}", text_color=COL_ERROR)

        run_in_thread(self, _do, _done, _err)

    def _settings_health_check(self):
        HealthCheckDialog(self)


# ===============================================================
#  HEALTH CHECK DIALOG
# ===============================================================

class HealthCheckDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Health Check")
        self.geometry("650x500")
        self.resizable(True, True)
        self.grab_set()

        self.results = ctk.CTkTextbox(self, font=FONT_MONO)
        self.results.pack(fill="both", expand=True, padx=16, pady=16)
        self.results.configure(state="disabled")

        self._run()

    def _log(self, text):
        self.results.configure(state="normal")
        self.results.insert("end", text + "\n")
        self.results.see("end")
        self.results.configure(state="disabled")

    def _run(self):
        def _do():
            cfg = ss.load_config()
            games = cfg.get("games", [])
            if not games:
                self.after(0, lambda: self._log("No games configured."))
                return

            # Try connecting to Drive once
            drive_svc = None
            if any(g.get("drive_folder") for g in games) and ss.GDRIVE_AVAILABLE:
                self.after(0, lambda: self._log("Connecting to Google Drive..."))
                try:
                    drive_svc = ss.get_drive_service()
                    self.after(0, lambda: self._log("Connected.\n"))
                except Exception as e:
                    self.after(0, lambda: self._log(f"Could not connect: {e}\n"))

            all_ok = True
            for game in games:
                name = game["name"]
                self.after(0, lambda n=name: self._log(f"━━━ {n} ━━━"))

                # Local check
                sp = game.get("save_path", "")
                local_path = Path(sp)
                if not sp:
                    self.after(0, lambda: self._log("  Local: ✗ No save path configured"))
                    all_ok = False
                elif not local_path.exists():
                    self.after(0, lambda p=sp: self._log(f"  Local: ✗ Path not found: {p}"))
                    all_ok = False
                else:
                    files = [f for f in local_path.rglob("*") if f.is_file()] if local_path.is_dir() else [local_path]
                    if not files:
                        self.after(0, lambda: self._log("  Local: ⚠ Folder exists but empty"))
                        all_ok = False
                    else:
                        total_kb = sum(f.stat().st_size for f in files) // 1024
                        self.after(0, lambda n=len(files), kb=total_kb:
                                   self._log(f"  Local: ✓ {n} file(s) ({kb} KB)"))

                # Drive check
                if game.get("drive_folder"):
                    if drive_svc:
                        try:
                            parts = [p for p in game["drive_folder"].replace("\\", "/").split("/") if p]
                            parent_id = "root"
                            found = True
                            for part in parts:
                                q = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
                                     f"and '{parent_id}' in parents and trashed=false")
                                res = drive_svc.files().list(q=q, fields="files(id)").execute()
                                hits = res.get("files", [])
                                if not hits:
                                    found = False
                                    break
                                parent_id = hits[0]["id"]
                            if found:
                                q2 = (f"'{parent_id}' in parents and trashed=false "
                                      f"and name != '_savesync_game_config.json' "
                                      f"and mimeType != 'application/vnd.google-apps.folder'")
                                res2 = drive_svc.files().list(q=q2, fields="files(id,name,size)").execute()
                                df = res2.get("files", [])
                                if df:
                                    total_kb = sum(int(f.get("size", 0)) for f in df) // 1024
                                    self.after(0, lambda n=len(df), kb=total_kb:
                                               self._log(f"  Drive: ✓ {n} file(s) ({kb} KB)"))
                                else:
                                    self.after(0, lambda: self._log("  Drive: ⚠ Folder empty"))
                                    all_ok = False
                            else:
                                self.after(0, lambda: self._log("  Drive: ⚠ Folder not found"))
                                all_ok = False
                        except Exception as e:
                            self.after(0, lambda e=e: self._log(f"  Drive: ✗ Error: {e}"))
                            all_ok = False
                    else:
                        self.after(0, lambda: self._log("  Drive: ✗ Not connected"))
                        all_ok = False

                self.after(0, lambda: self._log(""))

            if all_ok:
                self.after(0, lambda: self._log("All checks passed."))
            else:
                self.after(0, lambda: self._log("Some issues found — review above."))

        threading.Thread(target=_do, daemon=True).start()


# ===============================================================
#  ADD GAME WIZARD (CTkToplevel, 6 steps with Next/Back)
# ===============================================================

class AddGameWizard(ctk.CTkToplevel):
    def __init__(self, master: SaveSyncApp):
        super().__init__(master)
        self.app = master
        self.title("Add a Game")
        self.geometry("620x520")
        self.resizable(False, False)
        self.grab_set()

        self.game = dict(ss.GAME_DEFAULTS)
        self.step = 0

        # Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=16)

        # Navigation buttons at bottom
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.nav_frame.pack(fill="x", padx=20, pady=(0, 16))

        self.btn_back = ctk.CTkButton(self.nav_frame, text="← Back", width=100,
                                       font=FONT_BODY, fg_color="gray30",
                                       command=self._go_back)
        self.btn_back.pack(side="left")

        self.btn_next = ctk.CTkButton(self.nav_frame, text="Next →", width=100,
                                       font=FONT_BODY, fg_color=COL_ACCENT,
                                       hover_color=COL_ACCENT_HVR,
                                       command=self._go_next)
        self.btn_next.pack(side="right")

        self._show_step()

    def _clear_container(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _show_step(self):
        self._clear_container()
        self.btn_back.configure(state="normal" if self.step > 0 else "disabled")

        steps = [
            self._step_name,
            self._step_save_path,
            self._step_exe_path,
            self._step_destinations,
            self._step_triggers,
            self._step_confirm,
        ]

        # Step header
        titles = ["Game Name", "Save-File Location", "Game Launcher",
                  "Backup Destinations", "Trigger Settings", "Review & Confirm"]
        hdr = ctk.CTkFrame(self.container, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hdr, text=f"Step {self.step + 1} of 6 — {titles[self.step]}",
                     font=FONT_HEAD).pack(anchor="w")
        ctk.CTkFrame(self.container, height=1, fg_color=COL_TEXT_DIM).pack(fill="x", pady=(0, 12))

        if self.step < len(steps):
            steps[self.step]()

        # Update next button text
        if self.step == 5:
            self.btn_next.configure(text="Save ✓")
        else:
            self.btn_next.configure(text="Next →")

    # ── Step 0: Game Name ─────────────────────────────────────
    def _step_name(self):
        ctk.CTkLabel(self.container, text="What is the name of the game?",
                     font=FONT_BODY).pack(anchor="w", pady=(8, 4))
        self.entry_name = ctk.CTkEntry(self.container, font=FONT_BODY, width=400,
                                        placeholder_text="e.g. Hollow Knight")
        self.entry_name.pack(anchor="w", pady=(0, 8))
        if self.game["name"]:
            self.entry_name.insert(0, self.game["name"])

    # ── Step 1: Save Path ─────────────────────────────────────
    def _step_save_path(self):
        ctk.CTkLabel(self.container, text=f"Game: {self.game['name']}",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w")

        # Manifest search results
        self._manifest_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self._manifest_frame.pack(fill="both", expand=True, pady=(8, 0))

        self._save_path_var = ctk.StringVar(value=self.game.get("save_path", ""))

        # Search manifest
        self._search_manifest()

        # Manual entry at bottom
        manual = ctk.CTkFrame(self.container, fg_color="transparent")
        manual.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(manual, text="Save path:", font=FONT_BODY).pack(anchor="w")
        row = ctk.CTkFrame(manual, fg_color="transparent")
        row.pack(fill="x")
        self.entry_save_path = ctk.CTkEntry(row, font=FONT_MONO, width=400,
                                             textvariable=self._save_path_var)
        self.entry_save_path.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Browse", width=80, font=FONT_SMALL,
                       command=self._browse_save_path).pack(side="left")

    def _search_manifest(self):
        for w in self._manifest_frame.winfo_children():
            w.destroy()

        if not ensure_manifest_ready(silent=True):
            ctk.CTkLabel(self._manifest_frame,
                         text="Game database not available. Enter path manually.",
                         font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="w")
            return

        exact, similar = ss.search_manifest_split(self.game["name"])

        if exact:
            ename, epaths = exact
            ctk.CTkLabel(self._manifest_frame,
                         text=f"✓ Exact match found: {ename}",
                         font=FONT_BODY, text_color=COL_SUCCESS).pack(anchor="w", pady=(0, 4))
            for p in epaths:
                btn = ctk.CTkButton(self._manifest_frame, text=p,
                                    font=FONT_MONO, anchor="w",
                                    fg_color="gray25", hover_color="gray35",
                                    command=lambda path=p: self._select_manifest_path(path))
                btn.pack(fill="x", pady=1)
        elif similar:
            ctk.CTkLabel(self._manifest_frame,
                         text="No exact match. Similar games:",
                         font=FONT_BODY, text_color=COL_WARNING).pack(anchor="w", pady=(0, 4))
            scroll = ctk.CTkScrollableFrame(self._manifest_frame, height=180,
                                            fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            for sname, spaths in similar:
                ctk.CTkLabel(scroll, text=sname, font=FONT_BODY).pack(anchor="w", pady=(4, 0))
                for p in spaths[:2]:
                    btn = ctk.CTkButton(scroll, text=p, font=FONT_MONO, anchor="w",
                                        fg_color="gray25", hover_color="gray35",
                                        command=lambda path=p: self._select_manifest_path(path))
                    btn.pack(fill="x", pady=1)
        else:
            ctk.CTkLabel(self._manifest_frame,
                         text="No matches found in database. Enter path manually.",
                         font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="w")

    def _select_manifest_path(self, path: str):
        # Resolve and validate
        result = ss.resolve_and_validate_path(path)
        if result["candidates"]:
            # Show candidate picker
            self._show_candidates(result["candidates"])
        else:
            self._save_path_var.set(result["resolved"])

    def _show_candidates(self, candidates):
        win = ctk.CTkToplevel(self)
        win.title("Select Path")
        win.geometry("500x300")
        win.grab_set()
        ctk.CTkLabel(win, text="Multiple folders found. Select one:",
                     font=FONT_BODY).pack(pady=12)
        for c in candidates:
            ctk.CTkButton(win, text=c, font=FONT_MONO, anchor="w",
                          fg_color="gray25", hover_color="gray35",
                          command=lambda p=c: [self._save_path_var.set(p),
                                               win.destroy()]).pack(fill="x", padx=16, pady=2)

    def _browse_save_path(self):
        path = filedialog.askdirectory(title="Select save folder")
        if path:
            self._save_path_var.set(path)

    # ── Step 2: Exe Path ──────────────────────────────────────
    def _step_exe_path(self):
        ctk.CTkLabel(self.container, text=f"Game: {self.game['name']}",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w")
        ctk.CTkLabel(self.container,
                     text="Provide the path to the file that launches your game.\n"
                          "This enables the watcher to detect when the game runs.\n"
                          "Leave blank to skip.",
                     font=FONT_BODY, wraplength=560, justify="left").pack(anchor="w", pady=(8, 8))

        row = ctk.CTkFrame(self.container, fg_color="transparent")
        row.pack(fill="x")
        self.entry_exe = ctk.CTkEntry(row, font=FONT_MONO, width=420,
                                       placeholder_text="e.g. D:\\Games\\HollowKnight\\hollow_knight.exe")
        self.entry_exe.pack(side="left", padx=(0, 8))
        if self.game.get("exe_path"):
            self.entry_exe.insert(0, self.game["exe_path"])
        ctk.CTkButton(row, text="Browse", width=80, font=FONT_SMALL,
                       command=self._browse_exe).pack(side="left")

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            title="Select game launcher",
            filetypes=[("Executables", "*.exe *.bat *.cmd"), ("All files", "*.*")])
        if path:
            self.entry_exe.delete(0, "end")
            self.entry_exe.insert(0, path)

    # ── Step 3: Destinations ──────────────────────────────────
    def _step_destinations(self):
        ctk.CTkLabel(self.container, text=f"Game: {self.game['name']}",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w")
        ctk.CTkLabel(self.container,
                     text="Where should backups be stored? At least one is required.\n"
                          "Leave blank to skip a destination.",
                     font=FONT_BODY, wraplength=560, justify="left").pack(anchor="w", pady=(8, 8))

        ctk.CTkLabel(self.container, text="Google Drive folder:", font=FONT_BODY).pack(anchor="w", pady=(4, 0))
        self.entry_drive = ctk.CTkEntry(self.container, font=FONT_MONO, width=500,
                                         placeholder_text=f"e.g. SaveSync/{self.game['name']}")
        self.entry_drive.pack(anchor="w", pady=(0, 8))
        if self.game.get("drive_folder"):
            self.entry_drive.insert(0, self.game["drive_folder"])

        ctk.CTkLabel(self.container, text="Local .7z archive path:", font=FONT_BODY).pack(anchor="w", pady=(4, 0))
        row7z = ctk.CTkFrame(self.container, fg_color="transparent")
        row7z.pack(fill="x", pady=(0, 8))
        self.entry_archive = ctk.CTkEntry(row7z, font=FONT_MONO, width=420,
                                           placeholder_text="e.g. D:/Backups/mygame.7z")
        self.entry_archive.pack(side="left", padx=(0, 8))
        if self.game.get("archive_path"):
            self.entry_archive.insert(0, self.game["archive_path"])
        ctk.CTkButton(row7z, text="Browse", width=80, font=FONT_SMALL,
                       command=lambda: self._browse_file(self.entry_archive, "7z")).pack(side="left")

        ctk.CTkLabel(self.container, text="Local folder copy:", font=FONT_BODY).pack(anchor="w", pady=(4, 0))
        row_lc = ctk.CTkFrame(self.container, fg_color="transparent")
        row_lc.pack(fill="x", pady=(0, 8))
        self.entry_local = ctk.CTkEntry(row_lc, font=FONT_MONO, width=420)
        self.entry_local.pack(side="left", padx=(0, 8))
        if self.game.get("local_copy"):
            self.entry_local.insert(0, self.game["local_copy"])
        ctk.CTkButton(row_lc, text="Browse", width=80, font=FONT_SMALL,
                       command=lambda: self._browse_dir(self.entry_local)).pack(side="left")

    def _browse_file(self, entry, ext):
        path = filedialog.asksaveasfilename(
            title="Select archive path",
            defaultextension=f".{ext}",
            filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _browse_dir(self, entry):
        path = filedialog.askdirectory(title="Select folder")
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    # ── Step 4: Triggers ──────────────────────────────────────
    def _step_triggers(self):
        ctk.CTkLabel(self.container, text=f"Game: {self.game['name']}",
                     font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w")

        has_exe = bool(self.game.get("exe_path"))

        if has_exe:
            ctk.CTkLabel(self.container,
                         text="When should SaveSync back up automatically?",
                         font=FONT_BODY).pack(anchor="w", pady=(8, 8))

            self.var_trigger_launch = ctk.BooleanVar(value=self.game.get("trigger_launch", True))
            ctk.CTkCheckBox(self.container, text="Backup when game launches",
                            font=FONT_BODY, variable=self.var_trigger_launch).pack(anchor="w", pady=2)

            self.var_trigger_close = ctk.BooleanVar(value=self.game.get("trigger_close", True))
            ctk.CTkCheckBox(self.container, text="Backup when game closes",
                            font=FONT_BODY, variable=self.var_trigger_close).pack(anchor="w", pady=2)

            ctk.CTkLabel(self.container,
                         text="Backup interval (minutes, 0 = off):",
                         font=FONT_BODY).pack(anchor="w", pady=(12, 0))
            self.entry_interval = ctk.CTkEntry(self.container, font=FONT_BODY, width=80)
            self.entry_interval.pack(anchor="w", pady=(0, 8))
            self.entry_interval.insert(0, str(self.game.get("interval_min", 0)))
        else:
            self.var_trigger_launch = ctk.BooleanVar(value=False)
            self.var_trigger_close = ctk.BooleanVar(value=False)
            ctk.CTkLabel(self.container,
                         text="No launcher set — triggers are disabled.\n"
                              "You can still back up manually.",
                         font=FONT_BODY, text_color=COL_TEXT_DIM).pack(anchor="w", pady=8)

        ctk.CTkLabel(self.container,
                     text="Max .7z snapshots to keep (older deleted):",
                     font=FONT_BODY).pack(anchor="w", pady=(12, 0))
        self.entry_max_backups = ctk.CTkEntry(self.container, font=FONT_BODY, width=80)
        self.entry_max_backups.pack(anchor="w")
        self.entry_max_backups.insert(0, str(self.game.get("max_backups", 10)))

    # ── Step 5: Confirm ───────────────────────────────────────
    def _step_confirm(self):
        g = self.game
        ctk.CTkLabel(self.container, text="Review your settings:",
                     font=FONT_BODY).pack(anchor="w", pady=(0, 8))

        info_frame = ctk.CTkFrame(self.container, corner_radius=8)
        info_frame.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(info_frame, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        fields = [
            ("Name",        g.get("name", "")),
            ("Save path",   g.get("save_path", "")),
            ("Launcher",    g.get("exe_path", "") or "(not set)"),
            ("Drive",       g.get("drive_folder", "") or "(skip)"),
            ("Archive",     g.get("archive_path", "") or "(skip)"),
            ("Local copy",  g.get("local_copy", "") or "(skip)"),
        ]

        if g.get("exe_path"):
            trigs = []
            if g.get("trigger_launch"): trigs.append("on launch")
            if g.get("trigger_close"):  trigs.append("on close")
            if g.get("interval_min", 0) > 0: trigs.append(f"every {g['interval_min']} min")
            fields.append(("Triggers", ", ".join(trigs) if trigs else "none"))

        fields.append(("Max backups", str(g.get("max_backups", 10))))

        for label, value in fields:
            row = ctk.CTkFrame(inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{label}:", font=FONT_BODY, width=100,
                         anchor="e").pack(side="left", padx=(0, 8))
            ctk.CTkLabel(row, text=value, font=FONT_MONO,
                         text_color=COL_TEXT_DIM).pack(side="left")

    # ── Navigation ────────────────────────────────────────────
    def _go_back(self):
        if self.step > 0:
            self.step -= 1
            self._show_step()

    def _go_next(self):
        # Collect data from current step before advancing
        if self.step == 0:
            name = self.entry_name.get().strip()
            if not name:
                messagebox.showwarning("Missing", "Please enter a game name.")
                return
            self.game["name"] = name

        elif self.step == 1:
            sp = self._save_path_var.get().strip()
            if not sp:
                messagebox.showwarning("Missing", "Please enter or select a save path.")
                return
            self.game["save_path"] = sp

        elif self.step == 2:
            exe = self.entry_exe.get().strip()
            exe = ss.strip_path_quotes(exe)
            self.game["exe_path"] = exe
            self.game["exe_name"] = Path(exe).name if exe else ""

        elif self.step == 3:
            drive = self.entry_drive.get().strip()
            archive = self.entry_archive.get().strip()
            local = self.entry_local.get().strip()
            if not drive and not archive and not local:
                messagebox.showwarning("Missing", "At least one backup destination is required.")
                return
            self.game["drive_folder"] = drive
            self.game["archive_path"] = archive
            self.game["local_copy"] = local

        elif self.step == 4:
            self.game["trigger_launch"] = self.var_trigger_launch.get()
            self.game["trigger_close"] = self.var_trigger_close.get()
            if self.game.get("exe_path") and hasattr(self, 'entry_interval'):
                iv = self.entry_interval.get().strip()
                self.game["interval_min"] = int(iv) if iv.isdigit() else 0
            else:
                self.game["interval_min"] = 0
            mx = self.entry_max_backups.get().strip()
            self.game["max_backups"] = int(mx) if mx.isdigit() else 10

        elif self.step == 5:
            # Save!
            self._save_game()
            return

        self.step += 1
        self._show_step()

    def _save_game(self):
        cfg = ss.load_config()
        cfg["games"].append(self.game)
        ss.save_config(cfg)
        ss.log.info(f"Added game: {self.game['name']}")

        # Write launcher .bat if exe_path set
        if self.game.get("exe_path"):
            try:
                ss.write_launcher(self.game)
            except Exception:
                pass

        messagebox.showinfo("Success", f"'{self.game['name']}' added to SaveSync!")
        self.destroy()
        self.app.show_panel("games")


# ===============================================================
#  ENTRY POINT
# ===============================================================

if __name__ == "__main__":
    app = SaveSyncApp()
    app.mainloop()
