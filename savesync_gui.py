"""
SaveSync GUI — CustomTkinter frontend for SaveSync.
Imports all logic from savesync.py — never modifies it.

Dependencies:
    pip install customtkinter pystray Pillow requests
"""

import os
import sys
import json
import threading
import datetime
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path


import customtkinter as ctk

# System tray support
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError as _e:
    TRAY_AVAILABLE = False

# HTTP requests for SteamGridDB
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ---------------------------------------------------------------
# Import everything from savesync.py (the logic layer)
# ---------------------------------------------------------------
import savesync as ss


# ---------------------------------------------------------------
# Tray icon helper — generates a simple icon in memory
# ---------------------------------------------------------------
def _create_tray_icon_image():
    """Create a 64x64 SaveSync tray icon (blue circle with white S)."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Blue circle
    draw.ellipse([4, 4, 60, 60], fill=(59, 130, 246, 255))
    # White "S" — drawn as two arcs
    draw.arc([18, 12, 46, 36], start=0, end=180, fill="white", width=4)
    draw.arc([18, 28, 46, 52], start=180, end=360, fill="white", width=4)
    draw.line([18, 24, 46, 24], fill="white", width=0)  # just connecting
    return img

# ---------------------------------------------------------------
# Appearance
# ---------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colour palette — refined dark navy theme
COL_BG_DARK    = "#0d111e"     # unified app background
COL_BG_CARD    = "#141928"     # card surface — slightly lighter than bg
COL_BG_SIDEBAR = "#0d111e"     # sidebar — same base as content
COL_ACCENT     = "#6c63ff"     # primary purple
COL_ACCENT_HVR = "#5a52e0"     # purple hover
COL_SUCCESS    = "#4ade80"     # green
COL_WARNING    = "#f59e0b"     # amber
COL_ERROR      = "#ef4444"     # red
COL_TEXT       = "#f0f0f0"     # primary text
COL_TEXT_DIM   = "#6b7280"     # secondary text
COL_TEXT_MID   = "#9ca3af"     # mid-brightness text
COL_CARD_HOVER = "#1e2d45"
COL_BORDER     = "#1e2540"     # default card border
COL_BADGE_DRIVE_BG = "#1a2545"
COL_BADGE_DRIVE_FG = "#6aaff5"
COL_BADGE_7Z_BG    = "#2a2200"
COL_BADGE_7Z_FG    = "#f5c542"
COL_BADGE_AUTO_BG  = "#0a2010"
COL_BADGE_AUTO_FG  = "#4ade80"
COL_BTN_GHOST  = "#1a2035"     # ghost button background

FONT_TITLE  = ("Segoe UI", 17, "bold")
FONT_HEAD   = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_TINY   = ("Segoe UI", 10)
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
# Thumbnail manager — SteamGridDB covers, cached locally
# ---------------------------------------------------------------
STEAMGRIDDB_API_KEY = "eef436c06c902672e16d69ba375c0cb7"
THUMB_CACHE_DIR = ss.BASE_DIR / "thumbnail_cache"
THUMB_SIZE = (220, 300)        # portrait 2:3 ratio — matches game cover art
THUMB_CACHE_VERSION = "2"      # bump when endpoint or size changes → clears old cache


class ThumbnailManager:
    """Fetches and caches game cover thumbnails from SteamGridDB.

    Cache structure:
        thumbnail_cache/
            index.json        — maps game name → {sgdb_id, thumb_url, filename}
            <hash>.png        — downloaded thumbnail files
    """

    _INDEX_FILE = THUMB_CACHE_DIR / "index.json"
    _lock = threading.Lock()

    def __init__(self):
        THUMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()
        # If cache version changed (new endpoint/size), nuke stale files
        if self._index.get("__version__") != THUMB_CACHE_VERSION:
            for f in THUMB_CACHE_DIR.glob("*.png"):
                try: f.unlink()
                except Exception: pass
            self._index = {"__version__": THUMB_CACHE_VERSION}
            self._save_index()
        self._ctk_cache = {}  # str -> ctk.CTkImage

    # ── Index persistence ─────────────────────────────────────
    def _load_index(self) -> dict:
        if self._INDEX_FILE.exists():
            try:
                return json.loads(self._INDEX_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        try:
            self._INDEX_FILE.write_text(
                json.dumps(self._index, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────
    def get_thumbnail(self, game_name: str):
        """Return a CTkImage for the game if cached on disk, else None.
        Loads the saved PNG, normalises it to a clean RGB canvas, and
        wraps it in CTkImage.  Returns None on any failure so the caller
        can fall back to a pure-CTk placeholder (no PIL/DIB risk)."""
        if game_name in self._ctk_cache:
            return self._ctk_cache[game_name]

        entry = self._index.get(game_name)
        if not entry:
            return None
        filepath = THUMB_CACHE_DIR / entry.get("filename", "")
        if not filepath.exists():
            return None

        try:
            raw = Image.open(filepath)
            raw.load()                           # force full decode
            # Paste onto a guaranteed-clean RGB canvas of the right size.
            # This strips embedded profiles, unusual modes, APNG frames, etc.
            canvas = Image.new("RGB", THUMB_SIZE, (20, 20, 40))
            src = self._fit_cover(raw.convert("RGB"), THUMB_SIZE)
            canvas.paste(src)
            ctk_img = ctk.CTkImage(light_image=canvas, dark_image=canvas,
                                   size=THUMB_SIZE)
            self._ctk_cache[game_name] = ctk_img
            return ctk_img
        except Exception:
            return None

    # ── Placeholder helpers (no PIL — pure CTk widgets) ───────────
    def placeholder_color(self, game_name: str) -> str:
        """Return a deterministic dark hex colour string for this game."""
        h = hashlib.md5(game_name.encode()).hexdigest()
        b = int(h[:2], 16)
        r = 30 + (b % 60)
        g = 20 + ((b * 3) % 50)
        bl = 60 + ((b * 7) % 100)
        return f"#{r:02x}{g:02x}{bl:02x}"

    def placeholder_initials(self, game_name: str) -> str:
        """Return up to 2 initials for the game name."""
        words = game_name.split()
        initials = ""
        for word in words:
            ch = next((c for c in word if c.isalnum()), None)
            if ch:
                initials += ch.upper()
            if len(initials) >= 2:
                break
        return initials or "?"

    def fetch_thumbnail(self, game_name: str) -> bool:
        """Fetch from SteamGridDB and cache locally.  Blocking — call from thread.
        Returns True if a thumbnail was downloaded (or already cached)."""
        if not REQUESTS_AVAILABLE:
            ss.log.warning("ThumbnailManager: 'requests' not installed — cannot fetch thumbnails")
            return False

        with self._lock:
            # Already cached?
            entry = self._index.get(game_name)
            if entry and (THUMB_CACHE_DIR / entry.get("filename", "")).exists():
                return True

        try:
            headers = {"Authorization": f"Bearer {STEAMGRIDDB_API_KEY}"}

            # Step 1: search for the game
            search_url = (
                f"https://www.steamgriddb.com/api/v2/search/autocomplete/"
                f"{_requests.utils.quote(game_name)}"
            )
            resp = _requests.get(search_url, headers=headers, timeout=10)
            if resp.status_code == 401:
                ss.log.error("SGDB: API key rejected (401) — check STEAMGRIDDB_API_KEY in savesync_gui.py")
                return False
            if resp.status_code != 200:
                ss.log.warning(f"SGDB search HTTP {resp.status_code} for '{game_name}'")
                return False
            data = resp.json()
            games = data.get("data", [])
            if not games:
                ss.log.info(f"SGDB: no match found for '{game_name}' — try a shorter/common name")
                return False
            sgdb_id = games[0]["id"]
            ss.log.debug(f"SGDB: found id={sgdb_id} for '{game_name}'")

            # Step 2: try portrait grids (600x900) first, fall back to any grid
            grids_portrait_url = (
                f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_id}"
                f"?dimensions=600x900"
            )
            resp2 = _requests.get(grids_portrait_url, headers=headers, timeout=10)
            grids = []
            if resp2.status_code == 200:
                grids = resp2.json().get("data", [])

            if not grids:
                # Fallback: any grid dimensions
                grids_any_url = f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_id}"
                resp2b = _requests.get(grids_any_url, headers=headers, timeout=10)
                if resp2b.status_code != 200:
                    ss.log.warning(f"SGDB grids HTTP {resp2b.status_code} for '{game_name}' (id={sgdb_id})")
                    return False
                grids = resp2b.json().get("data", [])

            if not grids:
                ss.log.info(f"SGDB: no grid art found for '{game_name}' (id={sgdb_id})")
                return False

            thumb_url = grids[0].get("thumb") or grids[0].get("url", "")
            if not thumb_url:
                ss.log.warning(f"SGDB: grid entry has no url for '{game_name}'")
                return False

            # Step 3: download the thumbnail image
            img_resp = _requests.get(thumb_url, timeout=15)
            if img_resp.status_code != 200:
                return False

            # Determine filename from hash of the game name
            name_hash = hashlib.md5(game_name.encode("utf-8")).hexdigest()[:12]
            # Detect extension from Content-Type or URL
            ct = img_resp.headers.get("Content-Type", "")
            if "png" in ct or thumb_url.endswith(".png"):
                ext = "png"
            elif "webp" in ct or thumb_url.endswith(".webp"):
                ext = "webp"
            else:
                ext = "jpg"
            filename = f"{name_hash}.{ext}"
            filepath = THUMB_CACHE_DIR / filename

            filepath.write_bytes(img_resp.content)

            # Convert to PNG if not already (ensures PIL can always open it)
            if ext != "png":
                try:
                    pil_img = Image.open(filepath).convert("RGB")
                    png_name = f"{name_hash}.png"
                    png_path = THUMB_CACHE_DIR / png_name
                    pil_img.save(png_path, "PNG")
                    filepath.unlink(missing_ok=True)
                    filename = png_name
                except Exception:
                    pass  # keep original format

            # Update index
            with self._lock:
                self._index[game_name] = {
                    "sgdb_id": sgdb_id,
                    "thumb_url": thumb_url,
                    "filename": filename,
                }
                # Clear the CTkImage cache so it gets re-built from new file
                self._ctk_cache.pop(game_name, None)
                self._save_index()

            return True

        except Exception as _e:
            ss.log.error(f"SGDB fetch_thumbnail exception for '{game_name}': {_e}", exc_info=True)
            return False

    def prefetch_all(self, game_names):
        """Fetch thumbnails for all games that are not cached yet.  Blocking."""
        for name in game_names:
            entry = self._index.get(name)
            if entry and (THUMB_CACHE_DIR / entry.get("filename", "")).exists():
                continue
            self.fetch_thumbnail(name)

    def invalidate(self, game_name: str):
        """Remove cached thumbnail for a game (e.g. when renamed)."""
        with self._lock:
            entry = self._index.pop(game_name, None)
            self._ctk_cache.pop(game_name, None)
            self._ctk_cache.pop(f"__placeholder__{game_name}", None)
            if entry:
                fp = THUMB_CACHE_DIR / entry.get("filename", "")
                fp.unlink(missing_ok=True)
                self._save_index()

    # ── Internal helpers ──────────────────────────────────────
    @staticmethod
    def _fit_cover(img: Image.Image, target_size: tuple) -> Image.Image:
        """Resize and center-crop to fill target_size exactly."""
        tw, th = target_size
        iw, ih = img.size
        # Scale to cover
        scale = max(tw / iw, th / ih)
        new_w, new_h = int(iw * scale), int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Center crop
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        img = img.crop((left, top, left + tw, top + th))
        return img


# Singleton instance — created once, shared across the app
_thumb_mgr = ThumbnailManager()


def _relative_time(iso_ts: str) -> str:
    """Convert an ISO timestamp to a human-readable relative time like '2h ago'."""
    if not iso_ts:
        return "never"
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return "unknown"


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
        self.watcher = None  # type: ss.GameWatcher or None
        self.watcher_running = False
        self.active_nav: str = ""
        self._tray_icon = None
        self._really_quit = False   # True only when user picks "Quit" from tray
        self._start_minimized = "--minimized" in sys.argv

        # ── Intercept window close → minimize to tray ─────────
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Grid: sidebar (col 0, fixed) | content (col 1, expand)
        self.grid_columnconfigure(0, weight=0, minsize=200)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)   # status bar

        # ── Sidebar ───────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                     fg_color=COL_BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        # ── Content area ──────────────────────────────────────
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=COL_BG_DARK)
        self.content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        # ── Status bar ────────────────────────────────────────
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0,
                                       fg_color=COL_BG_DARK)
        self.statusbar.grid(row=1, column=1, sticky="ew")
        self.statusbar.grid_propagate(False)
        self._build_statusbar()

        # ── Show games panel by default ───────────────────────
        self.show_panel("games")

        # ── Background: check manifest update ─────────────────
        threading.Thread(target=ss.check_manifest_update_silently, daemon=True).start()

        # ── Background: prefetch thumbnails for all games ─────
        self._prefetch_thumbnails()

        # ── Periodic status refresh ───────────────────────────
        self._refresh_status()

        # ── --minimized: auto-start watcher and hide to tray ──
        if self._start_minimized:
            self.after(200, self._auto_start_minimized)
        else:
            # Explicitly ensure the window is visible and on top
            self.deiconify()
            self.lift()
            self.focus_force()

    # -----------------------------------------------------------
    # System tray (minimize-to-tray on close)
    # -----------------------------------------------------------
    def _auto_start_minimized(self):
        """Called on startup when --minimized is passed.
        Starts the watcher automatically, hides to tray, and runs a health check."""
        # Start the watcher
        cfg = ss.load_config()
        games = cfg.get("games", [])
        watchable = [g for g in games if g.get("exe_name")]
        if watchable:
            self.watcher = ss.GameWatcher(games)
            self.watcher.start()
            self.watcher_running = True
            threading.Thread(target=ss._watcher_check_manifest_update, daemon=True).start()
            ss.log.info("SaveSync started minimized — watcher running.")
        else:
            ss.log.info("SaveSync started minimized — no watchable games found.")

        # Hide to tray
        if TRAY_AVAILABLE:
            self.withdraw()
            self._start_tray_icon()
        else:
            # No tray available — just iconify (minimize to taskbar)
            self.iconify()

        # Run startup health check in background
        threading.Thread(target=self._startup_health_check, daemon=True).start()

    def _startup_health_check(self):
        """Background integrity/sync check run on minimized startup.
        Compares local vs Drive timestamps for all games with Drive folders.
        Sends a Windows notification with the result."""
        try:
            cfg = ss.load_config()
            games = cfg.get("games", [])
            if not games:
                ss.notify("SaveSync", "No games configured.")
                return

            drive_games = [g for g in games if g.get("drive_folder") and ss.GDRIVE_AVAILABLE]
            issues = []
            synced_count = 0

            if drive_games:
                try:
                    svc = ss.get_drive_service()
                except Exception as e:
                    ss.notify("SaveSync Health Check",
                              f"Could not connect to Google Drive: {e}")
                    return

                for game in drive_games:
                    try:
                        # Navigate to Drive folder
                        parts = [p for p in game["drive_folder"].replace("\\", "/").split("/") if p]
                        parent_id = "root"
                        found = True
                        for part in parts:
                            q = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
                                 f"and '{parent_id}' in parents and trashed=false")
                            res = svc.files().list(q=q, fields="files(id)").execute()
                            hits = res.get("files", [])
                            if not hits:
                                found = False
                                break
                            parent_id = hits[0]["id"]

                        if not found:
                            issues.append(f"{game['name']}: Drive folder not found")
                            continue

                        # Compare timestamps
                        dcfg = ss.fetch_game_config_from_drive(svc, parent_id)
                        drive_ts = dcfg.get("backup_timestamp", "") if dcfg else ""
                        local_ts = game.get("backup_timestamp", "")

                        if not drive_ts and not local_ts:
                            issues.append(f"{game['name']}: no backups found")
                            continue

                        if not drive_ts or not local_ts:
                            issues.append(f"{game['name']}: out of sync (missing timestamp)")
                            continue

                        from datetime import datetime as _dt, timezone as _tz
                        try:
                            local_dt = _dt.fromisoformat(local_ts.replace("Z", "+00:00"))
                        except Exception:
                            local_dt = _dt.min.replace(tzinfo=_tz.utc)
                        try:
                            drive_dt = _dt.fromisoformat(drive_ts.replace("Z", "+00:00"))
                        except Exception:
                            drive_dt = _dt.min.replace(tzinfo=_tz.utc)

                        if local_dt != drive_dt:
                            direction = "local is newer" if local_dt > drive_dt else "Drive is newer"
                            issues.append(f"{game['name']}: desynchronized ({direction})")
                        else:
                            synced_count += 1

                    except Exception as e:
                        issues.append(f"{game['name']}: check failed ({e})")

            # Also verify local save paths exist
            for game in games:
                sp = game.get("save_path", "")
                if sp and not Path(sp).exists():
                    issues.append(f"{game['name']}: save path not found")

            # Send notification
            if not issues:
                total = len(games)
                ss.notify("SaveSync",
                          f"All {total} game(s) fully synchronized. Watcher is running.")
            else:
                issue_list = "\n".join(f"• {i}" for i in issues[:5])
                extra = f"\n(+{len(issues) - 5} more)" if len(issues) > 5 else ""
                ss.notify("SaveSync — Issues Found",
                          f"Desynchronization found:\n{issue_list}{extra}\n\n"
                          f"Open SaveSync to diagnose.")

            ss.log.info(f"Startup health check complete: {synced_count} synced, "
                        f"{len(issues)} issue(s)")

        except Exception as e:
            ss.log.error(f"Startup health check failed: {e}")

    # -----------------------------------------------------------
    # Thumbnail prefetching
    # -----------------------------------------------------------
    def _prefetch_thumbnails(self):
        """Fetch thumbnails for all configured games in the background.
        When done, refresh the games panel if it's currently visible."""
        cfg = ss.load_config()
        game_names = [g["name"] for g in cfg.get("games", [])]
        if not game_names:
            return

        def _worker():
            _thumb_mgr.prefetch_all(game_names)
            # After fetching, refresh the panel on the main thread.
            # Use try/except because .after() can fail if called before
            # mainloop starts or after the window is destroyed.
            try:
                self.after(100, self._refresh_games_if_active)
            except RuntimeError:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_games_if_active(self):
        """Rebuild the games panel (thumbnails updated) and re-show if active."""
        self._invalidate_panel("games")
        if self.active_nav == "games":
            self.show_panel("games")

    def _on_close(self):
        """When user clicks X: hide to tray instead of quitting."""
        if TRAY_AVAILABLE:
            self.withdraw()          # hide the window
            self._start_tray_icon()  # show tray icon
        else:
            # No tray support — if watcher is running, warn
            if self.watcher_running:
                if messagebox.askyesno(
                    "Watcher Running",
                    "The watcher is still running. If you close the window "
                    "the watcher will stop.\n\n"
                    "Install pystray and Pillow to enable minimize-to-tray.\n\n"
                    "Close anyway?"):
                    self._force_quit()
                return
            self._force_quit()

    def _force_quit(self):
        """Actually destroy the app and exit."""
        self._really_quit = True
        if self.watcher:
            self.watcher.stop()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self.destroy()

    def _start_tray_icon(self):
        """Create and show the system tray icon (runs in its own thread)."""
        if self._tray_icon is not None:
            return  # already showing

        def on_show(icon, item):
            # Schedule UI restore on the main thread
            self.after(0, self._restore_from_tray)

        def on_quit(icon, item):
            icon.stop()
            self._tray_icon = None
            self.after(0, self._force_quit)

        menu = pystray.Menu(
            pystray.MenuItem("Show SaveSync", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )
        icon_image = _create_tray_icon_image()
        status = "running" if self.watcher_running else "stopped"
        self._tray_icon = pystray.Icon(
            "SaveSync", icon_image,
            f"SaveSync — Watcher {status}",
            menu,
        )
        # pystray.Icon.run() blocks, so run it in a daemon thread
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _restore_from_tray(self):
        """Bring the window back from the system tray."""
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.deiconify()   # show the window
        self.lift()        # bring to front
        self.focus_force()

    # -----------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------
    def _build_sidebar(self):
        # Logo / title — centred
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(20, 24))
        ctk.CTkLabel(logo_frame, text="SaveSync",
                     font=("Segoe UI", 18, "bold"),
                     text_color=COL_ACCENT).pack(anchor="center")
        ctk.CTkLabel(logo_frame, text="Game Save Manager",
                     font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="center", pady=(2, 0))

        self.nav_buttons = {}  # str -> ctk.CTkButton
        nav_items = [
            ("games",    "Games"),
            ("watcher",  "Watcher"),
            ("settings", "Settings"),
        ]
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="center",
                font=("Segoe UI", 15, "bold"), height=48, corner_radius=8,
                fg_color="transparent", text_color=COL_TEXT_MID,
                hover_color="#1a2245",
                command=lambda k=key: self.show_panel(k),
            )
            btn.pack(fill="x", pady=2, padx=10)
            self.nav_buttons[key] = btn

    def _highlight_nav(self, key: str):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color="#1e2a50", text_color=COL_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=COL_TEXT_MID)

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
        else:
            self.lbl_status_watcher.configure(text="Watcher: stopped", text_color=COL_TEXT_DIM)

        # DB update available?
        meta = ss._load_manifest_meta()
        if meta.get("update_available"):
            self.lbl_status_update.configure(text="★ DB update available")
        else:
            self.lbl_status_update.configure(text="")

        self.after(5000, self._refresh_status)

    # -----------------------------------------------------------
    # Panel switching — cached so switching tabs is instant
    # -----------------------------------------------------------
    def show_panel(self, name: str):
        """Show a panel by name.  Panels are built once and cached;
        switching between them is O(1) — no widget rebuild."""
        if not hasattr(self, "_panel_cache"):
            self._panel_cache = {}

        self.active_nav = name
        self._highlight_nav(name)

        # Hide every cached panel
        for frame in self._panel_cache.values():
            try:
                frame.pack_forget()
            except Exception:
                pass

        # If cached (and not stale), just re-pack it
        if name in self._panel_cache:
            try:
                self._panel_cache[name].pack(fill="both", expand=True)
                return
            except Exception:
                del self._panel_cache[name]  # stale; fall through to rebuild

        # Build fresh
        builders = {
            "games":    self._panel_games,
            "watcher":  self._panel_watcher,
            "settings": self._panel_settings,
        }
        builder = builders.get(name)
        if builder:
            try:
                builder()
            except Exception as e:
                ss.log.error(f"Panel '{name}' failed to render: {e}", exc_info=True)
                err_frame = ctk.CTkFrame(self.content, fg_color="transparent")
                err_frame.pack(fill="both", expand=True)
                ctk.CTkLabel(err_frame,
                             text=f"Error loading panel '{name}':\n{e}",
                             font=FONT_BODY, text_color=COL_ERROR
                             ).pack(padx=20, pady=40)
                self._panel_cache[name] = err_frame
                return

        # Stash whichever frame was just packed into self.content
        children = [w for w in self.content.winfo_children()
                    if str(w.winfo_manager()) == "pack"]
        if children:
            self._panel_cache[name] = children[-1]

    def _invalidate_panel(self, name: str):
        """Mark a panel as stale so it is rebuilt on next visit."""
        if not hasattr(self, "_panel_cache"):
            return
        old = self._panel_cache.pop(name, None)
        if old:
            try:
                old.destroy()
            except Exception:
                pass

    # ===============================================================
    #  PANEL: Games
    # ===============================================================
    # ── Grid helper: wrap cards into rows ────────────────────
    CARD_WIDTH  = 220   # px per card (matches mockup minmax)
    CARD_GAP    = 16    # px gap between cards

    def _panel_games(self):
        # Outer wrapper fills the content area
        wrapper = ctk.CTkFrame(self.content, fg_color="transparent")
        wrapper.pack(fill="both", expand=True)

        # ── Top bar: title + action buttons ─────────────────
        topbar = ctk.CTkFrame(wrapper, fg_color="transparent", height=52)
        topbar.pack(fill="x", padx=24, pady=(16, 0))
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="My Games", font=FONT_TITLE,
                     text_color=COL_TEXT).pack(side="left", anchor="w")

        btn_row = ctk.CTkFrame(topbar, fg_color="transparent")
        btn_row.pack(side="right", anchor="e")
        ctk.CTkButton(btn_row, text="Add from Drive", width=130, height=32,
                       font=("Segoe UI", 12, "bold"),
                       fg_color=COL_BTN_GHOST, hover_color="#222a42",
                       text_color=COL_TEXT_MID, corner_radius=8,
                       command=self._add_from_drive).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="+ Add Game", width=110, height=32,
                       font=("Segoe UI", 12, "bold"),
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       text_color="#ffffff", corner_radius=8,
                       command=self._open_add_game_dialog).pack(side="left")

        # ── Scrollable grid area ────────────────────────────
        scroll = ctk.CTkScrollableFrame(
            wrapper, fg_color="transparent",
            scrollbar_fg_color=COL_BG_DARK,             # track blends into bg
            scrollbar_button_color="#4a5580",           # clearly visible thumb
            scrollbar_button_hover_color=COL_ACCENT,    # purple on hover
        )
        scroll.pack(fill="both", expand=True, padx=24, pady=(16, 8))

        cfg = ss.load_config()
        games = cfg.get("games", [])

        if not games:
            ctk.CTkLabel(scroll, text="No games configured yet.\nClick '+ Add Game' to get started.",
                         font=FONT_BODY, text_color=COL_TEXT_DIM).pack(pady=40)
            return

        # Store scroll reference so we can re-layout on resize
        self._games_scroll = scroll
        self._games_list = games
        self._grid_cols = 0  # force fresh layout

        # Build cards into a grid via a frame that re-flows
        self._grid_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._grid_frame.pack(fill="x")

        self._lay_out_game_grid()

        # Re-layout when the scroll area resizes
        scroll.bind("<Configure>", lambda e: self._lay_out_game_grid())

        # CTkScrollableFrame only enables scrolling when its canvas scrollregion
        # is larger than the visible area.  The scrollregion is set via
        # <Configure> on the inner frame, but that event may not fire after we
        # populate the grid (timing).  Force a scrollregion refresh so CTk sees
        # the true content height, enables the mouse wheel, and shows the thumb.
        def _force_scrollregion():
            try:
                scroll.update_idletasks()
                canvas = scroll._parent_canvas
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass
        scroll.after(300, _force_scrollregion)

    def _lay_out_game_grid(self):
        """(Re-)arrange game cards in a responsive grid inside _grid_frame."""
        frame = self._grid_frame
        games = self._games_list

        # Determine number of columns from available width
        try:
            avail = self._games_scroll.winfo_width()
        except Exception:
            avail = 700
        if avail < 100:
            avail = 700  # first render fallback

        cols = max(1, (avail + self.CARD_GAP) // (self.CARD_WIDTH + self.CARD_GAP))

        # Only rebuild if column count changed (or first time)
        if hasattr(self, "_grid_cols") and self._grid_cols == cols:
            return
        self._grid_cols = cols

        # Clear existing children
        for w in frame.winfo_children():
            w.destroy()

        # Columns share space equally; cards keep natural width (sticky="n")
        for c in range(cols):
            frame.grid_columnconfigure(c, weight=1)

        # Place cards — sticky="n" keeps card at its natural width, centred in cell
        for idx, game in enumerate(games):
            r, c = divmod(idx, cols)
            card = self._game_card(frame, game)
            card.grid(row=r, column=c, padx=self.CARD_GAP // 2,
                      pady=self.CARD_GAP // 2, sticky="n")

        # After rebuilding cards, force scrollregion update + reset to top
        if hasattr(self, "_games_scroll"):
            def _refresh_scroll():
                try:
                    scroll = self._games_scroll
                    scroll.update_idletasks()
                    canvas = scroll._parent_canvas
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    canvas.yview_moveto(0.0)
                except Exception:
                    pass
            frame.after(100, _refresh_scroll)

    def _game_card(self, parent, game: dict) -> ctk.CTkFrame:
        """Render a single game card — vertical layout matching the mockup:
        thumbnail (top, 3:2) → name → relative time → badges → action buttons."""
        card = ctk.CTkFrame(parent, corner_radius=12, border_width=1,
                            fg_color=COL_BG_CARD,
                            border_color=COL_BORDER)
        # Hover effect — bind to card and all children so every pixel triggers it
        def _on_enter(e):
            card.configure(border_color=COL_ACCENT)

        def _on_leave(e):
            # Only deactivate when the mouse truly leaves the card boundary
            wx, wy = card.winfo_rootx(), card.winfo_rooty()
            ww, wh = card.winfo_width(), card.winfo_height()
            mx, my = card.winfo_pointerx(), card.winfo_pointery()
            if not (wx <= mx < wx + ww and wy <= my < wy + wh):
                card.configure(border_color=COL_BORDER)

        def _bind_hover(widget):
            widget.bind("<Enter>", _on_enter, add="+")
            widget.bind("<Leave>", _on_leave, add="+")
            for child in widget.winfo_children():
                _bind_hover(child)

        # Defer until card is fully built so all children exist
        card.after(0, lambda: _bind_hover(card))

        # ── Thumbnail area (full card width, fixed height = 3:2) ──
        thumb_img = _thumb_mgr.get_thumbnail(game["name"])
        if thumb_img is not None:
            # Real cover art — let CTkImage define size (220×146), centred in card
            ctk.CTkLabel(card, text="", image=thumb_img,
                         corner_radius=0).pack(pady=0)
        else:
            # Pure-CTk placeholder — fixed size matches THUMB_SIZE, no PIL/DIB risk
            ph_color = _thumb_mgr.placeholder_color(game["name"])
            initials = _thumb_mgr.placeholder_initials(game["name"])
            ph_frame = ctk.CTkFrame(card, fg_color=ph_color,
                                    width=THUMB_SIZE[0], height=THUMB_SIZE[1],
                                    corner_radius=0)
            ph_frame.pack(pady=0)
            ph_frame.pack_propagate(False)
            ctk.CTkLabel(ph_frame, text=initials,
                         font=("Segoe UI", 30, "bold"),
                         text_color="#ffffff",
                         fg_color="transparent").pack(expand=True)

        # ── Info section (padded) ───────────────────────────
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=12, pady=(10, 12))

        # Game name (truncated)
        ctk.CTkLabel(info, text=game["name"], font=FONT_HEAD,
                     text_color=COL_TEXT, anchor="w").pack(fill="x")

        # Relative time
        ts = game.get("backup_timestamp", "")
        rel = _relative_time(ts)
        time_frame = ctk.CTkFrame(info, fg_color="transparent")
        time_frame.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(time_frame, text="Last sync ", font=FONT_TINY,
                     text_color=COL_TEXT_DIM, anchor="w").pack(side="left")
        ctk.CTkLabel(time_frame, text=rel, font=FONT_TINY,
                     text_color=COL_SUCCESS, anchor="w").pack(side="left")

        # ── Badges row ──────────────────────────────────────
        badge_row = ctk.CTkFrame(info, fg_color="transparent")
        badge_row.pack(fill="x", pady=(8, 0))

        def _badge(parent_fr, text, bg, fg):
            b = ctk.CTkLabel(parent_fr, text=text, font=("Segoe UI", 10, "bold"),
                             fg_color=bg, text_color=fg, corner_radius=4,
                             width=0, height=20)
            b.pack(side="left", padx=(0, 5))

        if game.get("drive_folder"):
            _badge(badge_row, "Drive", COL_BADGE_DRIVE_BG, COL_BADGE_DRIVE_FG)
        if game.get("archive_path"):
            _badge(badge_row, ".7z", COL_BADGE_7Z_BG, COL_BADGE_7Z_FG)

        # Trigger badge
        iv = game.get("interval_min", 0)
        if iv:
            _badge(badge_row, f"{iv} min", COL_BADGE_AUTO_BG, COL_BADGE_AUTO_FG)
        elif game.get("trigger_close"):
            _badge(badge_row, "on close", COL_BADGE_AUTO_BG, COL_BADGE_AUTO_FG)
        elif game.get("trigger_launch"):
            _badge(badge_row, "on launch", COL_BADGE_AUTO_BG, COL_BADGE_AUTO_FG)

        # ── Action buttons row — always exactly 2 buttons ───
        btn_row = ctk.CTkFrame(info, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        # Primary button: Sync (if Drive) or Backup (otherwise)
        if game.get("drive_folder") and ss.GDRIVE_AVAILABLE:
            ctk.CTkButton(btn_row, text="Sync", height=30,
                          font=("Segoe UI", 11, "bold"),
                          fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                          text_color="#ffffff", corner_radius=6,
                          command=lambda g=game: self._sync_game(g)
                          ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        else:
            ctk.CTkButton(btn_row, text="Backup", height=30,
                          font=("Segoe UI", 11, "bold"),
                          fg_color=COL_BTN_GHOST, hover_color="#222a42",
                          text_color=COL_TEXT_MID, corner_radius=6,
                          command=lambda g=game: self._quick_backup(g)
                          ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        # ··· menu button — fixed width, always visible
        more_btn = ctk.CTkButton(btn_row, text="···", width=36, height=30,
                                 font=("Segoe UI", 13, "bold"),
                                 fg_color=COL_BTN_GHOST, hover_color="#222a42",
                                 text_color=COL_TEXT_MID, corner_radius=6,
                                 command=lambda g=game, b=None: None)
        more_btn.pack(side="left")
        more_btn.configure(
            command=lambda g=game, mb=more_btn: self._show_card_menu(g, mb)
        )

        return card

    def _show_card_menu(self, game: dict, anchor_widget):
        """Dropdown from the ··· button: Backup, Edit, Remove."""
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 11),
                       bg="#1a2035", fg=COL_TEXT, activebackground=COL_ACCENT,
                       activeforeground="#ffffff", relief="flat", bd=0)
        menu.add_command(label="  Backup now  ",
                         command=lambda: self._quick_backup(game))
        menu.add_command(label="  Edit  ",
                         command=lambda: self._edit_game(game))
        menu.add_separator()
        menu.add_command(label="  Remove  ",
                         command=lambda: self._remove_game(game))
        # Position the menu below the ··· button
        try:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
            menu.tk_popup(x, y)
        except Exception:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _remove_game(self, game: dict):
        if not messagebox.askyesno(
            "Remove Game",
            f"Remove '{game['name']}' from SaveSync?\n\n"
            "This only removes the game from your local list.\n"
            "Your save files on disk and backups on Google Drive are NOT deleted.\n\n"
            "If you later use 'Add from Drive', the game will be "
            "automatically re-added to your list."):
            return
        cfg = ss.load_config()
        cfg["games"] = [g for g in cfg["games"] if g["name"] != game["name"]]
        ss.save_config(cfg)
        ss.log.info(f"Removed game: {game['name']}")
        self._invalidate_panel("games")
        self.show_panel("games")

    def _edit_game(self, game: dict):
        """Open the Edit Game dialog."""
        EditGameDialog(self, game)

    def _quick_backup(self, game: dict):
        """Open the full backup dialog for a game."""
        BackupDialog(self, game)

    # -----------------------------------------------------------
    # Sync — compare local vs Drive timestamps, auto-sync
    # -----------------------------------------------------------
    def _sync_game(self, game: dict):
        """Compare local backup_timestamp vs Drive, sync in the appropriate direction."""
        win = ctk.CTkToplevel(self)
        win.title(f"Sync — {game['name']}")
        win.geometry("520x320")
        win.resizable(False, True)
        win.grab_set()

        lbl = ctk.CTkLabel(win, text=f"Syncing: {game['name']}", font=FONT_HEAD)
        lbl.pack(anchor="w", padx=20, pady=(16, 4))

        status_lbl = ctk.CTkLabel(win, text="Comparing local and Drive timestamps...",
                                   font=FONT_BODY, text_color=COL_TEXT_DIM)
        status_lbl.pack(anchor="w", padx=20, pady=(0, 8))

        prog = ctk.CTkProgressBar(win, width=460)
        prog.pack(padx=20, pady=(0, 8))
        prog.configure(mode="indeterminate")
        prog.start()

        log_box = ctk.CTkTextbox(win, font=FONT_MONO, height=140)
        log_box.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        log_box.configure(state="disabled")

        close_btn = ctk.CTkButton(win, text="Close", font=FONT_BODY, width=100,
                                   fg_color="gray30", hover_color="gray40",
                                   command=win.destroy)

        def _log(text):
            log_box.configure(state="normal")
            log_box.insert("end", text + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        def _do():
            svc = ss.get_drive_service()

            # Navigate to the Drive folder
            parts = [p for p in game["drive_folder"].replace("\\", "/").split("/") if p]
            parent_id = "root"
            found = True
            for part in parts:
                q = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
                     f"and '{parent_id}' in parents and trashed=false")
                res = svc.files().list(q=q, fields="files(id)").execute()
                hits = res.get("files", [])
                if not hits:
                    found = False
                    break
                parent_id = hits[0]["id"]

            if not found:
                return "no_drive", None

            # Get Drive config
            dcfg = ss.fetch_game_config_from_drive(svc, parent_id)
            drive_ts = dcfg.get("backup_timestamp", "") if dcfg else ""
            local_ts = game.get("backup_timestamp", "")

            win.after(0, lambda: _log(f"Local timestamp:  {ss.fmt_ts(local_ts) if local_ts else 'none'}"))
            win.after(0, lambda: _log(f"Drive timestamp:  {ss.fmt_ts(drive_ts) if drive_ts else 'none'}"))

            if not drive_ts and not local_ts:
                return "no_data", None

            if not drive_ts:
                # No Drive backup yet — push local to Drive
                return "local_newer", svc
            if not local_ts:
                # No local backup yet — pull from Drive
                return "drive_newer", (svc, parent_id)

            # Compare timestamps
            from datetime import datetime, timezone
            try:
                local_dt = datetime.fromisoformat(local_ts.replace("Z", "+00:00"))
            except Exception:
                local_dt = datetime.min.replace(tzinfo=timezone.utc)
            try:
                drive_dt = datetime.fromisoformat(drive_ts.replace("Z", "+00:00"))
            except Exception:
                drive_dt = datetime.min.replace(tzinfo=timezone.utc)

            if local_dt > drive_dt:
                return "local_newer", svc
            elif drive_dt > local_dt:
                return "drive_newer", (svc, parent_id)
            else:
                return "in_sync", None

        def _done(result):
            direction, ctx = result
            prog.stop()
            prog.configure(mode="determinate")

            if direction == "no_drive":
                prog.set(0)
                status_lbl.configure(text="Drive folder not found for this game.",
                                     text_color=COL_ERROR)
                win.after(0, lambda: _log("\n✗ No Drive folder found. Run a backup first."))
                close_btn.pack(pady=(0, 12))
                return

            if direction == "no_data":
                prog.set(0)
                status_lbl.configure(text="No timestamp data available.",
                                     text_color=COL_WARNING)
                win.after(0, lambda: _log("\n⚠ Neither local nor Drive has a backup timestamp."))
                close_btn.pack(pady=(0, 12))
                return

            if direction == "in_sync":
                prog.set(1.0)
                status_lbl.configure(text="✓ Already in sync — no action needed.",
                                     text_color=COL_SUCCESS)
                win.after(0, lambda: _log("\n✓ Local and Drive are identical."))
                close_btn.pack(pady=(0, 12))
                return

            if direction == "local_newer":
                svc = ctx
                status_lbl.configure(text="Local is newer — uploading to Drive...",
                                     text_color=COL_ACCENT)
                prog.configure(mode="indeterminate")
                prog.start()
                win.after(0, lambda: _log("\n→ Local saves are newer. Backing up to Drive..."))

                def _upload():
                    files = ss.collect_save_files(game)
                    if not files:
                        raise RuntimeError("No local save files found.")
                    ts = ss.backup_to_drive(game, files, silent=True)
                    if ts:
                        cfg = ss.load_config()
                        for g in cfg["games"]:
                            if g["name"] == game["name"]:
                                g["backup_timestamp"] = ts
                                break
                        ss.save_config(cfg)
                        game["backup_timestamp"] = ts
                    return len(files)

                def _upload_done(count):
                    prog.stop()
                    prog.configure(mode="determinate")
                    prog.set(1.0)
                    status_lbl.configure(
                        text=f"✓ Synced — uploaded {count} file(s) to Drive.",
                        text_color=COL_SUCCESS)
                    win.after(0, lambda: _log(f"  ✓ Uploaded {count} file(s) to Drive."))
                    close_btn.pack(pady=(0, 12))

                def _upload_err(e):
                    prog.stop()
                    prog.set(0)
                    status_lbl.configure(text=f"✗ Upload failed: {e}", text_color=COL_ERROR)
                    win.after(0, lambda: _log(f"  ✗ Error: {e}"))
                    close_btn.pack(pady=(0, 12))

                run_in_thread(self, _upload, _upload_done, _upload_err)
                return

            if direction == "drive_newer":
                svc, folder_id = ctx
                status_lbl.configure(text="Drive is newer — downloading to local...",
                                     text_color=COL_ACCENT)
                prog.configure(mode="indeterminate")
                prog.start()
                win.after(0, lambda: _log("\n→ Drive saves are newer. Downloading..."))

                def _download():
                    save_files = ss.list_drive_save_files(svc, folder_id)
                    if not save_files:
                        raise RuntimeError("No save files found on Drive.")

                    local_save_path = Path(game["save_path"])

                    # Snapshot existing local saves before overwriting
                    if local_save_path.exists():
                        existing = [f for f in local_save_path.rglob("*") if f.is_file()]
                        if existing:
                            import py7zr
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_name = game["name"].replace(" ", "_")
                            snap_dir = ss.BASE_DIR / "restore_snapshots" / safe_name
                            snap_dir.mkdir(parents=True, exist_ok=True)
                            snapshot = snap_dir / f"before_sync_{ts}.7z"
                            with py7zr.SevenZipFile(snapshot, "w") as zf:
                                for f in existing:
                                    zf.write(f, arcname=f.name)

                    # Download from Drive
                    local_save_path.mkdir(parents=True, exist_ok=True)
                    for f in save_files:
                        dest = local_save_path / f["name"]
                        ss.download_file_from_drive(svc, f["id"], dest)

                    # Update local timestamp to match Drive
                    dcfg = ss.fetch_game_config_from_drive(svc, folder_id)
                    if dcfg and dcfg.get("backup_timestamp"):
                        cfg = ss.load_config()
                        for g in cfg["games"]:
                            if g["name"] == game["name"]:
                                g["backup_timestamp"] = dcfg["backup_timestamp"]
                                break
                        ss.save_config(cfg)
                        game["backup_timestamp"] = dcfg["backup_timestamp"]

                    return len(save_files)

                def _download_done(count):
                    prog.stop()
                    prog.configure(mode="determinate")
                    prog.set(1.0)
                    status_lbl.configure(
                        text=f"✓ Synced — downloaded {count} file(s) from Drive.",
                        text_color=COL_SUCCESS)
                    win.after(0, lambda: _log(f"  ✓ Downloaded {count} file(s) from Drive."))
                    close_btn.pack(pady=(0, 12))

                def _download_err(e):
                    prog.stop()
                    prog.set(0)
                    status_lbl.configure(text=f"✗ Download failed: {e}", text_color=COL_ERROR)
                    win.after(0, lambda: _log(f"  ✗ Error: {e}"))
                    close_btn.pack(pady=(0, 12))

                run_in_thread(self, _download, _download_done, _download_err)
                return

        def _err(e):
            prog.stop()
            status_lbl.configure(text=f"✗ Sync failed: {e}", text_color=COL_ERROR)
            win.after(0, lambda: _log(f"\n✗ Error: {e}"))
            close_btn.pack(pady=(0, 12))

        # When dialog closes, refresh games panel
        def _on_close():
            win.destroy()
            if self.active_nav == "games":
                self._invalidate_panel("games")
                self.show_panel("games")
        win.protocol("WM_DELETE_WINDOW", _on_close)

        run_in_thread(self, _do, _done, _err)

    # -----------------------------------------------------------
    # Add from Drive — list ALL games on Drive, let user re-add
    # -----------------------------------------------------------
    def _add_from_drive(self):
        """List all game folders on Drive with individual Add buttons and Add All."""
        if not ss.GDRIVE_AVAILABLE:
            messagebox.showwarning("Missing Libraries",
                                   "Google API libraries not installed.\n\n"
                                   "Run: pip install google-auth google-auth-oauthlib google-api-python-client")
            return

        win = ctk.CTkToplevel(self)
        win.title("Add from Drive")
        win.geometry("600x500")
        win.resizable(True, True)
        win.grab_set()

        lbl = ctk.CTkLabel(win, text="Connecting to Google Drive...", font=FONT_BODY)
        lbl.pack(pady=(16, 8))
        prog = ctk.CTkProgressBar(win, width=520)
        prog.pack(pady=(0, 8))
        prog.configure(mode="indeterminate")
        prog.start()

        # Button row (Add All + Close) — populated after loading
        top_btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        top_btn_frame.pack(fill="x", padx=16, pady=(0, 4))

        content_frame = ctk.CTkScrollableFrame(win, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        close_btn = ctk.CTkButton(win, text="Close", font=FONT_BODY, width=100,
                                   fg_color="gray30", hover_color="gray40",
                                   command=win.destroy)

        def _do():
            service = ss.get_drive_service()
            folders = ss.list_drive_game_folders(service)
            cfg = ss.load_config()
            local_names = {g["name"] for g in cfg.get("games", [])}

            all_games = []
            for folder_name, folder_id in folders:
                dcfg = None
                try:
                    dcfg = ss.fetch_game_config_from_drive(service, folder_id)
                except Exception:
                    pass
                is_local = folder_name in local_names
                all_games.append((folder_name, folder_id, dcfg, is_local))

            return service, all_games

        def _done(result):
            service, all_games = result
            prog.stop()
            prog.pack_forget()

            if not all_games:
                lbl.configure(text="No game folders found on Drive.",
                              text_color=COL_TEXT_DIM)
                close_btn.pack(pady=(0, 12))
                return

            missing = [g for g in all_games if not g[3]]
            lbl.configure(
                text=f"Found {len(all_games)} game(s) on Drive "
                     f"({len(missing)} not in local list):")

            # "Add All Missing" button
            if missing:
                def _add_all():
                    if not messagebox.askyesno(
                        "Confirm Add All",
                        f"Re-add {len(missing)} game(s) from Drive?\n\n"
                        "Each game's config and save files will be downloaded.\n"
                        "Existing local saves will be snapshot first.",
                        parent=win):
                        return
                    add_all_btn.configure(state="disabled", text="Adding...")
                    self._add_all_from_drive(service, missing, win)

                add_all_btn = ctk.CTkButton(
                    top_btn_frame, text=f"Add All Missing ({len(missing)})",
                    width=200, font=FONT_BODY,
                    fg_color="#7c3aed", hover_color="#6d28d9",
                    command=_add_all)
                add_all_btn.pack(side="left", padx=(0, 8))

            # Build cards for every Drive game
            card_widgets = {}
            for folder_name, folder_id, dcfg, is_local in all_games:
                card = ctk.CTkFrame(content_frame, corner_radius=8, border_width=1,
                                    border_color=COL_TEXT_DIM)
                card.pack(fill="x", pady=4)
                inner = ctk.CTkFrame(card, fg_color="transparent")
                inner.pack(fill="x", padx=12, pady=8)

                # Title row with local status badge
                title_row = ctk.CTkFrame(inner, fg_color="transparent")
                title_row.pack(fill="x")
                ctk.CTkLabel(title_row, text=folder_name, font=FONT_HEAD).pack(side="left")
                if is_local:
                    ctk.CTkLabel(title_row, text="  ✓ In local list",
                                 font=FONT_SMALL, text_color=COL_SUCCESS).pack(side="left")

                # Info
                if dcfg:
                    ts = dcfg.get("backup_timestamp", "")
                    sp = dcfg.get("save_path", "")
                    if ts:
                        ctk.CTkLabel(inner, text=f"Last backup: {ss.fmt_ts(ts)}",
                                     font=FONT_SMALL, text_color=COL_TEXT_DIM).pack(anchor="w")
                    if sp:
                        ctk.CTkLabel(inner, text=f"Save path: {sp}",
                                     font=FONT_MONO, text_color=COL_TEXT_DIM).pack(anchor="w")

                if not is_local:
                    ctk.CTkButton(
                        inner, text="Add", width=80, height=28,
                        font=FONT_SMALL, fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                        command=lambda fn=folder_name, fi=folder_id, dc=dcfg, svc=service, c=card:
                            self._restore_and_add(svc, fn, fi, dc, c, win)
                    ).pack(anchor="e", pady=(4, 0))
                card_widgets[folder_name] = card

            close_btn.pack(pady=(0, 12))

        def _err(e):
            prog.stop()
            lbl.configure(text=f"✗ Could not connect to Drive: {e}", text_color=COL_ERROR)
            close_btn.pack(pady=(0, 12))

        run_in_thread(self, _do, _done, _err)

    def _add_all_from_drive(self, service, missing_games, parent_win):
        """Add all missing games from Drive in sequence (background thread)."""
        def _do():
            results = []
            errors = []
            for folder_name, folder_id, dcfg, _ in missing_games:
                try:
                    # Determine restore path
                    restore_path = ""
                    if dcfg and dcfg.get("save_path"):
                        restore_path = dcfg["save_path"]

                    if not restore_path:
                        # Skip games with no known save path in batch mode
                        errors.append(f"{folder_name}: no save path in config — skipped (add manually)")
                        continue

                    save_files = ss.list_drive_save_files(service, folder_id)
                    if not save_files:
                        errors.append(f"{folder_name}: no save files on Drive")
                        continue

                    local_save_path = Path(restore_path)

                    # Snapshot existing local saves
                    if local_save_path.exists():
                        existing = [f for f in local_save_path.rglob("*") if f.is_file()]
                        if existing:
                            import py7zr
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_name = folder_name.replace(" ", "_")
                            snap_dir = ss.BASE_DIR / "restore_snapshots" / safe_name
                            snap_dir.mkdir(parents=True, exist_ok=True)
                            snapshot = snap_dir / f"before_restore_{ts}.7z"
                            with py7zr.SevenZipFile(snapshot, "w") as zf:
                                for f in existing:
                                    zf.write(f, arcname=f.name)

                    # Download files
                    local_save_path.mkdir(parents=True, exist_ok=True)
                    for f in save_files:
                        dest = local_save_path / f["name"]
                        ss.download_file_from_drive(service, f["id"], dest)

                    # Add to local config
                    if dcfg:
                        game_entry = dict(dcfg)
                        game_entry["save_path"] = restore_path
                    else:
                        game_entry = dict(ss.GAME_DEFAULTS)
                        game_entry["name"] = folder_name
                        game_entry["save_path"] = restore_path
                        game_entry["drive_folder"] = f"SaveSync/{folder_name}"

                    cfg = ss.load_config()
                    if not any(g["name"] == folder_name for g in cfg["games"]):
                        cfg["games"].append(game_entry)
                        ss.save_config(cfg)

                    results.append(folder_name)
                except Exception as e:
                    errors.append(f"{folder_name}: {e}")

            return results, errors

        def _done(result):
            ok_list, err_list = result

            # Restart watcher to pick up new games
            _, is_running, wcount = self._restart_watcher()

            msg = ""
            if ok_list:
                msg += f"✓ Successfully added {len(ok_list)} game(s):\n"
                msg += "\n".join(f"  • {n}" for n in ok_list)
            if err_list:
                if msg:
                    msg += "\n\n"
                msg += f"⚠ {len(err_list)} issue(s):\n"
                msg += "\n".join(f"  • {e}" for e in err_list)

            if is_running:
                msg += f"\n\nWatcher restarted — monitoring {wcount} game(s)."

            messagebox.showinfo("Add All Complete", msg, parent=parent_win)
            parent_win.destroy()
            self._invalidate_panel("games")
            self.show_panel("games")

        def _err(e):
            messagebox.showerror("Error", f"Add all failed:\n{e}", parent=parent_win)

        run_in_thread(self, _do, _done, _err)

    def _restore_and_add(self, service, folder_name, folder_id, dcfg, card_widget, parent_win):
        """Restore a single game from Drive and add it to the local config."""
        # Determine restore path
        if dcfg and dcfg.get("save_path"):
            default_path = dcfg["save_path"]
        else:
            default_path = ""

        # Confirm with user
        msg = f"Add '{folder_name}' from Google Drive?\n\n"
        if default_path:
            msg += f"Save files will be downloaded to:\n{default_path}\n\n"
        msg += ("The game will be added to your local list with its save files.\n"
                "Any existing local saves will be snapshot to .7z first.")

        if not messagebox.askyesno("Confirm Add", msg, parent=parent_win):
            return

        # If no save path in config, ask user
        restore_path = default_path
        if not restore_path:
            restore_path = filedialog.askdirectory(
                title=f"Select restore folder for {folder_name}",
                parent=parent_win)
            if not restore_path:
                return

        # Disable the card button
        for w in card_widget.winfo_children():
            for btn in w.winfo_children():
                if isinstance(btn, ctk.CTkButton):
                    btn.configure(state="disabled", text="Adding...")

        def _do():
            save_files = ss.list_drive_save_files(service, folder_id)
            if not save_files:
                raise RuntimeError("No save files found on Drive for this game.")

            local_save_path = Path(restore_path)

            # Snapshot existing local saves
            if local_save_path.exists():
                existing = [f for f in local_save_path.rglob("*") if f.is_file()]
                if existing:
                    import py7zr
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = folder_name.replace(" ", "_")
                    snap_dir = ss.BASE_DIR / "restore_snapshots" / safe_name
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    snapshot = snap_dir / f"before_restore_{ts}.7z"
                    with py7zr.SevenZipFile(snapshot, "w") as zf:
                        for f in existing:
                            zf.write(f, arcname=f.name)

            # Download files
            local_save_path.mkdir(parents=True, exist_ok=True)
            for f in save_files:
                dest = local_save_path / f["name"]
                ss.download_file_from_drive(service, f["id"], dest)

            # Add to local config
            if dcfg:
                game_entry = dict(dcfg)
                game_entry["save_path"] = restore_path
            else:
                game_entry = dict(ss.GAME_DEFAULTS)
                game_entry["name"] = folder_name
                game_entry["save_path"] = restore_path
                game_entry["drive_folder"] = f"SaveSync/{folder_name}"

            cfg = ss.load_config()
            # Avoid duplicates
            if not any(g["name"] == folder_name for g in cfg["games"]):
                cfg["games"].append(game_entry)
                ss.save_config(cfg)

            return len(save_files)

        def _done(count):
            # Restart watcher to pick up the new game
            _, is_running, wcount = self._restart_watcher()
            watcher_txt = ""
            if is_running:
                watcher_txt = f"  Watcher restarted ({wcount} game(s))."

            # Update the card to show success
            for w in card_widget.winfo_children():
                w.destroy()
            done_lbl = ctk.CTkLabel(card_widget,
                                    text=f"✓ {folder_name} — added with {count} file(s).{watcher_txt}",
                                    font=FONT_BODY, text_color=COL_SUCCESS)
            done_lbl.pack(padx=12, pady=8)
            # Refresh games panel when dialog closes
            def _on_parent_close():
                parent_win.destroy()
                self._invalidate_panel("games")
                self.show_panel("games")
            parent_win.protocol("WM_DELETE_WINDOW", _on_parent_close)

        def _err(e):
            for w in card_widget.winfo_children():
                for btn in w.winfo_children():
                    if isinstance(btn, ctk.CTkButton):
                        btn.configure(state="normal", text="Add")
            messagebox.showerror("Error", f"Restore failed:\n{e}", parent=parent_win)

        run_in_thread(self, _do, _done, _err)

    # ===============================================================
    #  ADD GAME DIALOG (6-step wizard as CTkToplevel)
    # ===============================================================
    def _open_add_game_dialog(self):
        AddGameWizard(self)

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
                    safe_name = folder_name.replace(" ", "_")
                    snap_dir = ss.BASE_DIR / "restore_snapshots" / safe_name
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    snapshot = snap_dir / f"before_restore_{ts}.7z"
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

        # Startup section
        ctk.CTkLabel(frame, text="Start with Windows", font=FONT_HEAD).pack(anchor="w", pady=(0, 6))

        # Check if startup entry exists
        startup_exists = self._startup_vbs_path().exists()
        startup_status = "✓ Installed — SaveSync will start with Windows" if startup_exists \
            else "Not installed — SaveSync does not start with Windows"
        status_color = COL_SUCCESS if startup_exists else COL_TEXT_DIM

        ctk.CTkLabel(frame, text=startup_status, font=FONT_BODY,
                     text_color=status_color).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text="Adds SaveSync to your Windows Startup folder. "
                     "It will launch minimized to the system tray with the watcher running.",
                     font=FONT_SMALL, text_color=COL_TEXT_DIM, wraplength=600,
                     justify="left").pack(anchor="w", pady=(0, 8))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(anchor="w")
        if not startup_exists:
            ctk.CTkButton(btn_row, text="Add to Startup", font=FONT_BODY, width=180,
                           fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                           command=lambda: self._manage_startup("install")).pack(side="left", padx=(0, 8))
        else:
            ctk.CTkButton(btn_row, text="Remove from Startup", font=FONT_BODY, width=180,
                           fg_color=COL_ERROR, hover_color="#dc2626",
                           command=lambda: self._manage_startup("remove")).pack(side="left")

    def _update_watcher_btn(self):
        if self.watcher_running:
            self._watcher_btn.configure(text="Stop Watcher", fg_color=COL_ERROR,
                                        hover_color="#dc2626")
        else:
            self._watcher_btn.configure(text="Start Watcher", fg_color=COL_SUCCESS,
                                        hover_color="#16a34a")

    def _restart_watcher(self):
        """Stop and restart the watcher with the latest config.
        Returns (was_running, is_running, watchable_count)."""
        was_running = self.watcher_running
        # Stop current watcher if running
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        self.watcher_running = False

        # Restart with fresh config
        cfg = ss.load_config()
        games = cfg.get("games", [])
        watchable = [g for g in games if g.get("exe_name")]
        if watchable:
            self.watcher = ss.GameWatcher(games)
            self.watcher.start()
            self.watcher_running = True
            threading.Thread(target=ss._watcher_check_manifest_update, daemon=True).start()

        self._refresh_status()
        return was_running, self.watcher_running, len(watchable)

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

    @staticmethod
    def _startup_vbs_path() -> Path:
        """Path to the .vbs launcher in the Windows Startup folder."""
        startup_folder = Path(os.environ.get("APPDATA", "")) / \
            "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return startup_folder / "SaveSync.vbs"

    def _manage_startup(self, mode: str):
        """Add or remove SaveSync from the Windows Startup folder."""
        import platform
        if platform.system() != "Windows":
            messagebox.showinfo("Not Available", "This feature is only available on Windows.")
            return

        vbs_path = self._startup_vbs_path()
        startup_folder = vbs_path.parent

        if mode == "remove":
            if not vbs_path.exists():
                messagebox.showinfo("Not Installed",
                                    "SaveSync is not in the Startup folder.")
                return
            if not messagebox.askyesno("Confirm",
                                       "Remove SaveSync from Windows Startup?\n\n"
                                       "SaveSync will no longer start automatically when you log in."):
                return
            try:
                vbs_path.unlink()
                messagebox.showinfo("Done", "SaveSync removed from Startup folder.")
                ss.log.info("Startup entry removed.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not remove startup entry:\n{e}")
        else:
            # Install
            py_path = Path(sys.executable)
            pythonw = py_path.parent / "pythonw.exe"
            if not pythonw.exists():
                pythonw = py_path
            gui_script = Path(__file__).resolve()
            work_dir = gui_script.parent

            if vbs_path.exists():
                if not messagebox.askyesno("Update",
                                           "SaveSync is already in the Startup folder.\n"
                                           "Update it with the current paths?"):
                    return

            # Build a .vbs launcher that starts pythonw minimized
            # WScript.Shell Run: 0 = hidden window, false = don't wait
            vbs_content = (
                f'Set WshShell = CreateObject("WScript.Shell")\n'
                f'WshShell.CurrentDirectory = "{work_dir}"\n'
                f'WshShell.Run """{pythonw}"" ""{gui_script}"" --minimized", 0, False\n'
            )

            if not messagebox.askyesno(
                "Confirm",
                f"Add SaveSync to Windows Startup?\n\n"
                f"When you log into Windows, SaveSync will start minimized\n"
                f"in the system tray with the watcher running.\n\n"
                f"Double-click the tray icon to open the full window.\n\n"
                f"File: {vbs_path}"):
                return

            try:
                startup_folder.mkdir(parents=True, exist_ok=True)
                vbs_path.write_text(vbs_content, encoding="utf-8")
                messagebox.showinfo("Done",
                    "SaveSync added to Startup folder.\n\n"
                    "Next time you log into Windows, SaveSync will start\n"
                    "minimized in the system tray with the watcher active.\n\n"
                    "Double-click the tray icon to open the full window.")
                ss.log.info(f"Startup entry installed: {vbs_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create startup entry:\n{e}")

        # Refresh the watcher panel to update the status
        if self.active_nav == "watcher":
            self.show_panel("watcher")

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

        # --- Game Database (custom section with two buttons) ---
        self._settings_db_section(frame)

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

    def _settings_db_section(self, parent):
        """Custom Game Database section with Download/Update + Search buttons."""
        sec = ctk.CTkFrame(parent, corner_radius=10, border_width=1,
                           border_color=COL_TEXT_DIM)
        sec.pack(fill="x", pady=6)
        inner = ctk.CTkFrame(sec, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(inner, text="Game Database", font=FONT_HEAD).pack(anchor="w")

        # Build info text
        meta = ss._load_manifest_meta()
        age = ss.manifest_db_age()
        idx_count = 0
        if ss.MANIFEST_INDEX.exists():
            try:
                idx = json.loads(ss.MANIFEST_INDEX.read_text(encoding="utf-8"))
                idx_count = len(idx)
            except Exception:
                pass

        if ss.MANIFEST_FILE.exists():
            desc = f"Ludusavi community database — {idx_count:,} games indexed, {age}."
            downloaded_at = meta.get("downloaded_at", "")
            if downloaded_at:
                desc += f"\nDownloaded: {ss.fmt_ts(downloaded_at)}"
            if meta.get("update_available"):
                desc += "\n★ A newer version is available on GitHub!"
        else:
            desc = "The Ludusavi database has not been downloaded yet.\nClick 'Download / Update' to get it (~15–50 MB, one-time)."

        ctk.CTkLabel(inner, text=desc, font=FONT_SMALL,
                     text_color=COL_TEXT_DIM, wraplength=560,
                     justify="left").pack(anchor="w", pady=(2, 6))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w")
        ctk.CTkButton(btn_row, text="Download / Update", font=FONT_BODY, width=180,
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       command=self._settings_download_db).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Search Database", font=FONT_BODY, width=160,
                       fg_color="gray30", hover_color="gray40",
                       command=self._settings_search_db).pack(side="left")

    def _settings_download_db(self):
        """Smart download dialog — checks version first, shows step-by-step feedback."""
        win = ctk.CTkToplevel(self)
        win.title("Game Database")
        win.geometry("560x320")
        win.resizable(False, False)
        win.grab_set()

        lbl = ctk.CTkLabel(win, text="Checking database status...", font=FONT_BODY)
        lbl.pack(pady=(20, 8))

        prog = ctk.CTkProgressBar(win, width=480)
        prog.pack(pady=(0, 8))
        prog.set(0)

        detail = ctk.CTkLabel(win, text="", font=FONT_SMALL, text_color=COL_TEXT_DIM,
                              wraplength=500, justify="left")
        detail.pack(pady=(0, 4))

        extra = ctk.CTkLabel(win, text="", font=FONT_SMALL, text_color=COL_TEXT_DIM,
                             wraplength=500, justify="left")
        extra.pack(pady=(0, 8))

        close_btn = ctk.CTkButton(win, text="Close", font=FONT_BODY, width=100,
                                   fg_color="gray30", hover_color="gray40",
                                   command=win.destroy)
        close_btn.pack(pady=(8, 12))
        close_btn.pack_forget()  # hidden initially

        def _show_close():
            close_btn.pack(pady=(8, 12))

        def _update_ui(label_text=None, label_color=None, detail_text=None,
                       extra_text=None, progress_val=None, progress_mode=None):
            if label_text is not None:
                lbl.configure(text=label_text)
            if label_color is not None:
                lbl.configure(text_color=label_color)
            if detail_text is not None:
                detail.configure(text=detail_text)
            if extra_text is not None:
                extra.configure(text=extra_text)
            if progress_val is not None:
                try:
                    prog.stop()
                except Exception:
                    pass
                prog.configure(mode="determinate")
                prog.set(progress_val)
            if progress_mode == "indeterminate":
                prog.configure(mode="indeterminate")
                prog.start()

        def _do():
            meta = ss._load_manifest_meta()
            has_file = ss.MANIFEST_FILE.exists()
            has_index = ss.MANIFEST_INDEX.exists()
            downloaded_at = meta.get("downloaded_at", "")

            # ── Step 1: Check if file exists at all ───────────
            if not has_file:
                win.after(0, lambda: _update_ui(
                    label_text="Database not downloaded yet.",
                    detail_text="Downloading from GitHub... this may take a moment.",
                    progress_mode="indeterminate"))
                ok = ss.download_manifest(silent=True)
                if not ok:
                    win.after(0, lambda: _update_ui(
                        label_text="✗ Download failed.",
                        label_color=COL_ERROR,
                        detail_text="Check your internet connection and try again.",
                        progress_val=0))
                    win.after(0, _show_close)
                    return
                win.after(0, lambda: _update_ui(
                    label_text="✓ Database downloaded.",
                    label_color=COL_SUCCESS,
                    detail_text="Now indexing...",
                    progress_val=0.6,
                    progress_mode="indeterminate"))
                ss.build_manifest_index(silent=True)
                idx_count = self._get_index_count()
                win.after(0, lambda: _update_ui(
                    label_text=f"✓ Database ready — {idx_count:,} games indexed.",
                    label_color=COL_SUCCESS,
                    detail_text=f"Downloaded: {ss.fmt_ts(ss._load_manifest_meta().get('downloaded_at', ''))}",
                    extra_text="",
                    progress_val=1.0))
                win.after(0, _show_close)
                return

            # ── Step 2: File exists — check for updates ───────
            win.after(0, lambda: _update_ui(
                label_text="Database found locally. Checking for updates...",
                detail_text=f"Current version downloaded: {ss.fmt_ts(downloaded_at)}" if downloaded_at else "",
                progress_mode="indeterminate"))

            update_available = False
            try:
                update_available = ss.check_manifest_update_available()
            except Exception:
                pass

            if not update_available:
                # Already up to date
                idx_count = self._get_index_count()
                needs_index = not has_index or idx_count == 0

                if needs_index:
                    win.after(0, lambda: _update_ui(
                        label_text="✓ Database is up to date.",
                        label_color=COL_SUCCESS,
                        detail_text=f"Downloaded: {ss.fmt_ts(downloaded_at)}\n"
                                    f"Index needs rebuilding — indexing now...",
                        progress_val=0.5,
                        progress_mode="indeterminate"))
                    ss.build_manifest_index(silent=True)
                    idx_count = self._get_index_count()
                    win.after(0, lambda: _update_ui(
                        label_text=f"✓ Database is up to date — {idx_count:,} games indexed.",
                        label_color=COL_SUCCESS,
                        detail_text=f"Downloaded: {ss.fmt_ts(downloaded_at)}\n"
                                    f"Index: ✓ {idx_count:,} games",
                        extra_text="No update needed. You have the latest version.",
                        progress_val=1.0))
                else:
                    win.after(0, lambda: _update_ui(
                        label_text=f"✓ Database is up to date — {idx_count:,} games indexed.",
                        label_color=COL_SUCCESS,
                        detail_text=f"Downloaded: {ss.fmt_ts(downloaded_at)}\n"
                                    f"Index: ✓ {idx_count:,} games",
                        extra_text="No update needed. You have the latest version.",
                        progress_val=1.0))
                win.after(0, _show_close)
                return

            # ── Step 3: Update available — ask user ───────────
            idx_count = self._get_index_count()
            win.after(0, lambda: _update_ui(
                label_text="★ A newer version is available!",
                label_color=COL_WARNING,
                detail_text=f"Your version: {ss.fmt_ts(downloaded_at)}\n"
                            f"Index: {idx_count:,} games",
                extra_text="",
                progress_val=0))

            # Ask on main thread
            answer = [None]
            event = threading.Event()
            def _ask():
                answer[0] = messagebox.askyesno(
                    "Update Available",
                    "A newer version of the game database is available on GitHub.\n\n"
                    f"Your current version: {ss.fmt_ts(downloaded_at)}\n\n"
                    "Download the updated version now?\n"
                    "(This will replace your current database and rebuild the index.)",
                    parent=win)
                event.set()
            win.after(0, _ask)
            event.wait()

            if not answer[0]:
                win.after(0, lambda: _update_ui(
                    label_text=f"Database unchanged — {idx_count:,} games indexed.",
                    label_color=COL_TEXT,
                    detail_text=f"Downloaded: {ss.fmt_ts(downloaded_at)}",
                    extra_text="Update skipped.",
                    progress_val=0))
                win.after(0, _show_close)
                return

            # ── Step 4: Download update ───────────────────────
            win.after(0, lambda: _update_ui(
                label_text="Downloading updated database...",
                detail_text="Please wait, this may take a moment on slow connections.",
                extra_text="",
                progress_mode="indeterminate"))

            ok = ss.download_manifest(silent=True)
            if not ok:
                win.after(0, lambda: _update_ui(
                    label_text="✗ Download failed.",
                    label_color=COL_ERROR,
                    detail_text="Check your internet connection and try again.",
                    progress_val=0))
                win.after(0, _show_close)
                return

            # ── Step 5: Rebuild index ─────────────────────────
            new_meta = ss._load_manifest_meta()
            win.after(0, lambda: _update_ui(
                label_text="✓ Database downloaded. Indexing...",
                label_color=COL_SUCCESS,
                detail_text=f"New version: {ss.fmt_ts(new_meta.get('downloaded_at', ''))}",
                progress_val=0.7,
                progress_mode="indeterminate"))

            ss.build_manifest_index(silent=True)
            idx_count = self._get_index_count()

            win.after(0, lambda: _update_ui(
                label_text=f"✓ Database updated — {idx_count:,} games indexed.",
                label_color=COL_SUCCESS,
                detail_text=f"Downloaded: {ss.fmt_ts(new_meta.get('downloaded_at', ''))}\n"
                            f"Index: ✓ {idx_count:,} games",
                extra_text="Update complete!",
                progress_val=1.0))
            win.after(0, _show_close)

        # Refresh settings panel when dialog closes
        def _on_close():
            win.destroy()
            if self.active_nav == "settings":
                self.show_panel("settings")
        win.protocol("WM_DELETE_WINDOW", _on_close)

        threading.Thread(target=_do, daemon=True).start()

    def _get_index_count(self) -> int:
        if ss.MANIFEST_INDEX.exists():
            try:
                idx = json.loads(ss.MANIFEST_INDEX.read_text(encoding="utf-8"))
                return len(idx)
            except Exception:
                pass
        return 0

    def _settings_search_db(self):
        """Open a search dialog to look up a game's save location in the database."""
        if not ensure_manifest_ready(silent=True):
            messagebox.showinfo("Database Not Ready",
                                "The game database has not been downloaded or indexed yet.\n\n"
                                "Click 'Download / Update' first.")
            return

        win = ctk.CTkToplevel(self)
        win.title("Search Game Database")
        win.geometry("620x450")
        win.resizable(True, True)
        win.grab_set()

        ctk.CTkLabel(win, text="Search for a game's save location:",
                     font=FONT_BODY).pack(anchor="w", padx=16, pady=(16, 4))

        search_frame = ctk.CTkFrame(win, fg_color="transparent")
        search_frame.pack(fill="x", padx=16)

        entry = ctk.CTkEntry(search_frame, font=FONT_BODY, width=400,
                              placeholder_text="e.g. Hollow Knight")
        entry.pack(side="left", padx=(0, 8))

        results_box = ctk.CTkTextbox(win, font=FONT_MONO, height=320)
        results_box.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        results_box.configure(state="disabled")

        def _search():
            query = entry.get().strip()
            if not query:
                return
            exact, similar = ss.search_manifest_split(query)

            results_box.configure(state="normal")
            results_box.delete("1.0", "end")

            if exact:
                ename, epaths = exact
                results_box.insert("end", f"Exact match: {ename}\n")
                results_box.insert("end", "─" * 50 + "\n")
                for p in epaths:
                    note = "  [wildcard — check in Explorer]" if "*" in p else ""
                    results_box.insert("end", f"  → {p}{note}\n")
                results_box.insert("end", "\n")

            if similar:
                if exact:
                    results_box.insert("end", "Other similar games:\n")
                else:
                    results_box.insert("end", f"No exact match for '{query}'.\n\n")
                    results_box.insert("end", "Similar games found:\n")
                results_box.insert("end", "─" * 50 + "\n")
                for sname, spaths in similar:
                    results_box.insert("end", f"\n  {sname}\n")
                    for p in spaths:
                        note = "  [wildcard]" if "*" in p else ""
                        results_box.insert("end", f"    → {p}{note}\n")

            if not exact and not similar:
                results_box.insert("end", f"No results found for '{query}'.\n\n"
                                          "Try a shorter name or check spelling.")

            results_box.configure(state="disabled")

        ctk.CTkButton(search_frame, text="Search", font=FONT_BODY, width=100,
                       fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
                       command=_search).pack(side="left")

        # Allow Enter key to trigger search
        entry.bind("<Return>", lambda e: _search())
        entry.focus_set()

    def _settings_health_check(self):
        HealthCheckDialog(self)


# ===============================================================
#  BACKUP DIALOG — opened from game card "Backup" button
# ===============================================================

class BackupDialog(ctk.CTkToplevel):
    """Full backup dialog for a single game.
    Shows current Drive and local backup status, then lets the user
    choose: backup to Drive, create local snapshot, or both."""

    def __init__(self, master: SaveSyncApp, game: dict):
        super().__init__(master)
        self.app = master
        self.game = game
        self.title(f"Backup — {game['name']}")
        self.geometry("580x520")
        self.resizable(False, True)
        self.grab_set()

        # ── Header ────────────────────────────────────────────
        ctk.CTkLabel(self, text=f"Backup: {game['name']}", font=FONT_TITLE).pack(
            anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(self, text=game.get("save_path", ""), font=FONT_MONO,
                     text_color=COL_TEXT_DIM).pack(anchor="w", padx=20, pady=(0, 8))

        sep = ctk.CTkFrame(self, height=1, fg_color=COL_TEXT_DIM)
        sep.pack(fill="x", padx=20, pady=(0, 8))

        # ── Status area (populated async) ─────────────────────
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.lbl_drive_status = ctk.CTkLabel(
            self.status_frame, text="Google Drive:  checking...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_drive_status.pack(anchor="w", pady=2)

        self.lbl_local_status = ctk.CTkLabel(
            self.status_frame, text="Local snapshots:  checking...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_local_status.pack(anchor="w", pady=2)

        self.lbl_save_files = ctk.CTkLabel(
            self.status_frame, text="Save files:  scanning...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_save_files.pack(anchor="w", pady=2)

        sep2 = ctk.CTkFrame(self, height=1, fg_color=COL_TEXT_DIM)
        sep2.pack(fill="x", padx=20, pady=8)

        # ── Action buttons ────────────────────────────────────
        ctk.CTkLabel(self, text="Choose a backup action:", font=FONT_HEAD).pack(
            anchor="w", padx=20, pady=(0, 8))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)

        self.btn_drive = ctk.CTkButton(
            btn_frame, text="Backup to Google Drive", font=FONT_BODY,
            width=240, height=38, fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
            command=lambda: self._run("drive"))
        self.btn_drive.pack(anchor="w", pady=3)

        self.btn_local = ctk.CTkButton(
            btn_frame, text="Create Local Snapshot (.7z)", font=FONT_BODY,
            width=240, height=38, fg_color="gray30", hover_color="gray40",
            command=lambda: self._run("local"))
        self.btn_local.pack(anchor="w", pady=3)

        self.btn_both = ctk.CTkButton(
            btn_frame, text="Both — Drive + Local Snapshot", font=FONT_BODY,
            width=240, height=38, fg_color="#7c3aed", hover_color="#6d28d9",
            command=lambda: self._run("both"))
        self.btn_both.pack(anchor="w", pady=3)

        sep3 = ctk.CTkFrame(self, height=1, fg_color=COL_TEXT_DIM)
        sep3.pack(fill="x", padx=20, pady=8)

        # ── Progress / log area ───────────────────────────────
        self.lbl_progress = ctk.CTkLabel(self, text="", font=FONT_BODY)
        self.lbl_progress.pack(anchor="w", padx=20)

        self.prog = ctk.CTkProgressBar(self, width=500)
        self.prog.pack(padx=20, pady=(4, 4))
        self.prog.set(0)
        self.prog.pack_forget()  # hidden until running

        self.log_box = ctk.CTkTextbox(self, font=FONT_MONO, height=100)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.log_box.configure(state="disabled")
        self.log_box.pack_forget()  # hidden until running

        # ── Local snapshot path (remembered for the session) ──
        self._local_snapshot_path: str = ""

        # ── Populate status in background ─────────────────────
        self._load_status()

    # -----------------------------------------------------------
    # Load current backup status
    # -----------------------------------------------------------
    def _load_status(self):
        game = self.game

        # Save files count (synchronous, fast)
        files = ss.collect_save_files(game)
        if files:
            total_kb = sum(f.stat().st_size for f in files) // 1024
            self.lbl_save_files.configure(
                text=f"Save files:  ✓ {len(files)} file(s), {total_kb} KB",
                text_color=COL_SUCCESS)
        else:
            self.lbl_save_files.configure(
                text="Save files:  ✗ No save files found at configured path",
                text_color=COL_ERROR)
            # Disable backup buttons if no files
            self.btn_drive.configure(state="disabled")
            self.btn_local.configure(state="disabled")
            self.btn_both.configure(state="disabled")

        # Local .7z snapshots
        if game.get("archive_path"):
            archive_dir = Path(game["archive_path"]).parent
            archive_stem = Path(game["archive_path"]).stem
            if archive_dir.exists():
                snaps = sorted(archive_dir.glob(archive_stem + "_*.7z"))
                if snaps:
                    latest = snaps[-1]
                    self.lbl_local_status.configure(
                        text=f"Local snapshots:  ✓ {len(snaps)} snapshot(s), latest: {latest.name}",
                        text_color=COL_SUCCESS)
                else:
                    self.lbl_local_status.configure(
                        text="Local snapshots:  No snapshots created yet",
                        text_color=COL_TEXT_DIM)
            else:
                self.lbl_local_status.configure(
                    text="Local snapshots:  Archive folder does not exist (will be created)",
                    text_color=COL_TEXT_DIM)
        else:
            self.lbl_local_status.configure(
                text="Local snapshots:  No archive path configured (you can create one below)",
                text_color=COL_TEXT_DIM)

        # Drive status (async — needs network)
        if game.get("drive_folder") and ss.GDRIVE_AVAILABLE:
            def _check_drive():
                try:
                    svc = ss.get_drive_service()
                    parts = [p for p in game["drive_folder"].replace("\\", "/").split("/") if p]
                    parent_id = "root"
                    found = True
                    for part in parts:
                        q = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
                             f"and '{parent_id}' in parents and trashed=false")
                        res = svc.files().list(q=q, fields="files(id)").execute()
                        hits = res.get("files", [])
                        if not hits:
                            found = False
                            break
                        parent_id = hits[0]["id"]

                    if not found:
                        return "none", ""

                    dcfg = ss.fetch_game_config_from_drive(svc, parent_id)
                    ts = dcfg.get("backup_timestamp", "") if dcfg else ""
                    # Count files
                    q2 = (f"'{parent_id}' in parents and trashed=false "
                          f"and name != '_savesync_game_config.json' "
                          f"and mimeType != 'application/vnd.google-apps.folder'")
                    res2 = svc.files().list(q=q2, fields="files(id,size)").execute()
                    df = res2.get("files", [])
                    return "found", ts, len(df)
                except Exception as e:
                    return "error", str(e)

            def _drive_done(result):
                if result[0] == "found":
                    _, ts, fcount = result
                    if ts:
                        self.lbl_drive_status.configure(
                            text=f"Google Drive:  ✓ {fcount} file(s), last backup: {ss.fmt_ts(ts)}",
                            text_color=COL_SUCCESS)
                    else:
                        self.lbl_drive_status.configure(
                            text=f"Google Drive:  ✓ Folder exists, {fcount} file(s), no timestamp recorded",
                            text_color=COL_SUCCESS)
                elif result[0] == "none":
                    self.lbl_drive_status.configure(
                        text="Google Drive:  No backup found (folder will be created on first backup)",
                        text_color=COL_TEXT_DIM)
                else:
                    self.lbl_drive_status.configure(
                        text=f"Google Drive:  ✗ Could not check — {result[1]}",
                        text_color=COL_ERROR)

            def _drive_err(e):
                self.lbl_drive_status.configure(
                    text=f"Google Drive:  ✗ Connection error — {e}",
                    text_color=COL_ERROR)

            run_in_thread(self, _check_drive, _drive_done, _drive_err)
        elif not ss.GDRIVE_AVAILABLE:
            self.lbl_drive_status.configure(
                text="Google Drive:  ✗ Google API libraries not installed",
                text_color=COL_ERROR)
            self.btn_drive.configure(state="disabled")
            self.btn_both.configure(state="disabled")
        else:
            self.lbl_drive_status.configure(
                text="Google Drive:  Not configured for this game",
                text_color=COL_TEXT_DIM)
            self.btn_drive.configure(state="disabled")
            self.btn_both.configure(state="disabled")

    # -----------------------------------------------------------
    # Run backup
    # -----------------------------------------------------------
    def _run(self, mode: str):
        """mode = 'drive', 'local', or 'both'"""
        game = self.game

        # For local backup: ask where to save if no archive_path configured
        local_path = ""
        if mode in ("local", "both"):
            if game.get("archive_path"):
                local_path = game["archive_path"]
            else:
                # Ask user for a save location
                chosen = filedialog.asksaveasfilename(
                    title="Choose where to save the .7z snapshot",
                    defaultextension=".7z",
                    filetypes=[("7z archives", "*.7z"), ("All files", "*.*")],
                    initialfile=f"{game['name'].replace(' ', '_')}.7z",
                    parent=self)
                if not chosen:
                    return  # cancelled
                local_path = chosen
                # Persist the choice into the game config
                cfg = ss.load_config()
                for g in cfg["games"]:
                    if g["name"] == game["name"]:
                        g["archive_path"] = local_path
                        break
                ss.save_config(cfg)
                game["archive_path"] = local_path

        # Show progress area
        self.prog.pack(padx=20, pady=(4, 4))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.prog.configure(mode="indeterminate")
        self.prog.start()

        # Disable buttons
        self.btn_drive.configure(state="disabled")
        self.btn_local.configure(state="disabled")
        self.btn_both.configure(state="disabled")

        self._log_clear()

        do_drive = mode in ("drive", "both")
        do_local = mode in ("local", "both")

        label_parts = []
        if do_drive: label_parts.append("Google Drive")
        if do_local: label_parts.append("local snapshot")
        self.lbl_progress.configure(
            text=f"Backing up to {' + '.join(label_parts)}...",
            text_color=COL_TEXT)

        def _do():
            files = ss.collect_save_files(game)
            if not files:
                raise RuntimeError("No save files found.")

            errors = []
            results = []

            if do_drive and game.get("drive_folder"):
                self.after(0, lambda: self._log_append("→ Uploading to Google Drive..."))
                try:
                    ts = ss.backup_to_drive(game, files, silent=True)
                    if ts:
                        # Update local config with new timestamp
                        local_cfg = ss.load_config()
                        for g in local_cfg["games"]:
                            if g["name"] == game["name"]:
                                g["backup_timestamp"] = ts
                                break
                        ss.save_config(local_cfg)
                        game["backup_timestamp"] = ts
                    results.append("Drive ✓")
                    self.after(0, lambda: self._log_append("  ✓ Drive backup complete."))
                except Exception as e:
                    errors.append(f"Drive: {e}")
                    self.after(0, lambda e=e: self._log_append(f"  ✗ Drive failed: {e}"))

            if do_local and local_path:
                self.after(0, lambda: self._log_append("→ Creating local .7z snapshot..."))
                try:
                    ss.backup_to_7z(game, files, silent=True)
                    results.append("Local .7z ✓")
                    self.after(0, lambda: self._log_append("  ✓ Local snapshot created."))
                except Exception as e:
                    errors.append(f"Local: {e}")
                    self.after(0, lambda e=e: self._log_append(f"  ✗ Local snapshot failed: {e}"))

            return results, errors

        def _done(result):
            results, errors = result
            self.prog.stop()
            self.prog.configure(mode="determinate")
            self.prog.set(1.0 if not errors else 0.5)

            if errors:
                summary = f"Finished with {len(errors)} error(s): {'; '.join(errors)}"
                self.lbl_progress.configure(text=summary, text_color=COL_ERROR)
                self._log_append(f"\n{summary}")
            else:
                summary = f"✓ Backup complete — {', '.join(results)}"
                self.lbl_progress.configure(text=summary, text_color=COL_SUCCESS)
                self._log_append(f"\n{summary}")

            # Re-enable buttons
            self.btn_drive.configure(state="normal")
            self.btn_local.configure(state="normal")
            self.btn_both.configure(state="normal")

            # Refresh status display
            self._load_status()
            self.app._refresh_status()

            # When dialog closes, refresh the games panel
            def _on_close():
                self.destroy()
                if self.app.active_nav == "games":
                    self.app._invalidate_panel("games")
                    self.app.show_panel("games")
            self.protocol("WM_DELETE_WINDOW", _on_close)

        def _err(e):
            self.prog.stop()
            self.prog.configure(mode="determinate")
            self.prog.set(0)
            self.lbl_progress.configure(text=f"✗ Error: {e}", text_color=COL_ERROR)
            self._log_append(f"\n✗ Error: {e}")
            self.btn_drive.configure(state="normal")
            self.btn_local.configure(state="normal")
            self.btn_both.configure(state="normal")

        run_in_thread(self, _do, _done, _err)

    def _log_clear(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _log_append(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")


# ===============================================================
#  EDIT GAME DIALOG
# ===============================================================

class EditGameDialog(ctk.CTkToplevel):
    """Allows the user to edit all fields of an existing game entry.
    On save, updates local config and uploads the updated config
    to the game's Drive folder so it stays synchronized."""

    def __init__(self, master: SaveSyncApp, game: dict):
        super().__init__(master)
        self.app = master
        self.game = game
        self.original_name = game["name"]
        self.title(f"Edit — {game['name']}")
        self.geometry("640x620")
        self.resizable(False, True)
        self.grab_set()

        # ── Scrollable form ──────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(16, 0))

        ctk.CTkLabel(scroll, text=f"Editing: {game['name']}", font=FONT_TITLE).pack(
            anchor="w", pady=(0, 12))

        # --- Game Name ---
        ctk.CTkLabel(scroll, text="Game Name", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        self.entry_name = ctk.CTkEntry(scroll, font=FONT_BODY, width=500)
        self.entry_name.pack(anchor="w", pady=(0, 8))
        self.entry_name.insert(0, game.get("name", ""))

        # --- Save Path ---
        ctk.CTkLabel(scroll, text="Save-File Path", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        row_sp = ctk.CTkFrame(scroll, fg_color="transparent")
        row_sp.pack(fill="x", pady=(0, 8))
        self.entry_save_path = ctk.CTkEntry(row_sp, font=FONT_MONO, width=440)
        self.entry_save_path.pack(side="left", padx=(0, 8))
        self.entry_save_path.insert(0, game.get("save_path", ""))
        ctk.CTkButton(row_sp, text="Browse", width=80, font=FONT_SMALL,
                       command=lambda: self._browse_dir(self.entry_save_path)).pack(side="left")

        # --- Launcher ---
        ctk.CTkLabel(scroll, text="Game Launcher (exe)", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        row_exe = ctk.CTkFrame(scroll, fg_color="transparent")
        row_exe.pack(fill="x", pady=(0, 8))
        self.entry_exe = ctk.CTkEntry(row_exe, font=FONT_MONO, width=440)
        self.entry_exe.pack(side="left", padx=(0, 8))
        self.entry_exe.insert(0, game.get("exe_path", ""))
        ctk.CTkButton(row_exe, text="Browse", width=80, font=FONT_SMALL,
                       command=self._browse_exe).pack(side="left")

        # --- Google Drive Folder ---
        ctk.CTkLabel(scroll, text="Google Drive Folder", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        self.entry_drive = ctk.CTkEntry(scroll, font=FONT_MONO, width=500,
                                         placeholder_text="e.g. SaveSync/MyGame")
        self.entry_drive.pack(anchor="w", pady=(0, 8))
        self.entry_drive.insert(0, game.get("drive_folder", ""))

        # --- Archive Path (.7z) ---
        ctk.CTkLabel(scroll, text="Local .7z Archive Path", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        row_arc = ctk.CTkFrame(scroll, fg_color="transparent")
        row_arc.pack(fill="x", pady=(0, 8))
        self.entry_archive = ctk.CTkEntry(row_arc, font=FONT_MONO, width=440)
        self.entry_archive.pack(side="left", padx=(0, 8))
        self.entry_archive.insert(0, game.get("archive_path", ""))
        ctk.CTkButton(row_arc, text="Browse", width=80, font=FONT_SMALL,
                       command=lambda: self._browse_file(self.entry_archive, "7z")).pack(side="left")

        # --- Local Copy Folder ---
        ctk.CTkLabel(scroll, text="Local Folder Copy", font=FONT_HEAD).pack(anchor="w", pady=(8, 2))
        row_lc = ctk.CTkFrame(scroll, fg_color="transparent")
        row_lc.pack(fill="x", pady=(0, 8))
        self.entry_local = ctk.CTkEntry(row_lc, font=FONT_MONO, width=440)
        self.entry_local.pack(side="left", padx=(0, 8))
        self.entry_local.insert(0, game.get("local_copy", ""))
        ctk.CTkButton(row_lc, text="Browse", width=80, font=FONT_SMALL,
                       command=lambda: self._browse_dir(self.entry_local)).pack(side="left")

        # --- Trigger Settings ---
        ctk.CTkFrame(scroll, height=1, fg_color=COL_TEXT_DIM).pack(fill="x", pady=12)
        ctk.CTkLabel(scroll, text="Watcher Trigger Settings", font=FONT_HEAD).pack(anchor="w", pady=(0, 4))

        self.var_trigger_launch = ctk.BooleanVar(value=game.get("trigger_launch", True))
        ctk.CTkCheckBox(scroll, text="Backup when game launches",
                         font=FONT_BODY, variable=self.var_trigger_launch).pack(anchor="w", pady=2)

        self.var_trigger_close = ctk.BooleanVar(value=game.get("trigger_close", True))
        ctk.CTkCheckBox(scroll, text="Backup when game closes",
                         font=FONT_BODY, variable=self.var_trigger_close).pack(anchor="w", pady=2)

        row_iv = ctk.CTkFrame(scroll, fg_color="transparent")
        row_iv.pack(anchor="w", pady=(6, 2))
        ctk.CTkLabel(row_iv, text="Backup interval (min, 0=off):", font=FONT_BODY).pack(side="left")
        self.entry_interval = ctk.CTkEntry(row_iv, font=FONT_BODY, width=60)
        self.entry_interval.pack(side="left", padx=(8, 0))
        self.entry_interval.insert(0, str(game.get("interval_min", 0)))

        row_mx = ctk.CTkFrame(scroll, fg_color="transparent")
        row_mx.pack(anchor="w", pady=(4, 8))
        ctk.CTkLabel(row_mx, text="Max .7z snapshots to keep:", font=FONT_BODY).pack(side="left")
        self.entry_max_backups = ctk.CTkEntry(row_mx, font=FONT_BODY, width=60)
        self.entry_max_backups.pack(side="left", padx=(8, 0))
        self.entry_max_backups.insert(0, str(game.get("max_backups", 10)))

        # ── Save / Cancel buttons ────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent", height=50)
        btn_frame.pack(fill="x", padx=20, pady=(8, 16))

        ctk.CTkButton(btn_frame, text="Cancel", width=100, font=FONT_BODY,
                       fg_color="gray30", hover_color="gray40",
                       command=self.destroy).pack(side="right")
        ctk.CTkButton(btn_frame, text="Save Changes", width=160, font=FONT_BODY,
                       fg_color=COL_SUCCESS, hover_color="#16a34a",
                       command=self._save).pack(side="right", padx=(0, 8))

    # -----------------------------------------------------------
    # Browse helpers
    # -----------------------------------------------------------
    def _browse_dir(self, entry_widget):
        path = filedialog.askdirectory(title="Select folder", parent=self)
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    def _browse_exe(self):
        path = filedialog.askopenfilename(
            title="Select game launcher",
            filetypes=[("Executables", "*.exe *.bat *.cmd"), ("All files", "*.*")],
            parent=self)
        if path:
            self.entry_exe.delete(0, "end")
            self.entry_exe.insert(0, path)

    def _browse_file(self, entry_widget, ext):
        path = filedialog.asksaveasfilename(
            title="Select archive path",
            defaultextension=f".{ext}",
            filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")],
            parent=self)
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    # -----------------------------------------------------------
    # Save changes
    # -----------------------------------------------------------
    def _save(self):
        new_name = self.entry_name.get().strip()
        new_save_path = self.entry_save_path.get().strip()

        if not new_name:
            messagebox.showwarning("Missing", "Game name cannot be empty.", parent=self)
            return
        if not new_save_path:
            messagebox.showwarning("Missing", "Save path cannot be empty.", parent=self)
            return

        new_exe = ss.strip_path_quotes(self.entry_exe.get().strip())
        new_drive = self.entry_drive.get().strip()
        new_archive = self.entry_archive.get().strip()
        new_local = self.entry_local.get().strip()
        new_trigger_launch = self.var_trigger_launch.get()
        new_trigger_close = self.var_trigger_close.get()
        iv_str = self.entry_interval.get().strip()
        new_interval = int(iv_str) if iv_str.isdigit() else 0
        mx_str = self.entry_max_backups.get().strip()
        new_max_backups = int(mx_str) if mx_str.isdigit() else 10

        if not new_drive and not new_archive and not new_local:
            messagebox.showwarning("Missing",
                                   "At least one backup destination is required.",
                                   parent=self)
            return

        # Check for name conflict if name was changed
        if new_name != self.original_name:
            cfg = ss.load_config()
            existing_names = {g["name"] for g in cfg.get("games", [])}
            if new_name in existing_names:
                messagebox.showwarning("Conflict",
                                       f"A game named '{new_name}' already exists.",
                                       parent=self)
                return

        # Update the config
        cfg = ss.load_config()
        for g in cfg["games"]:
            if g["name"] == self.original_name:
                g["name"] = new_name
                g["save_path"] = new_save_path
                g["exe_path"] = new_exe
                g["exe_name"] = Path(new_exe).name if new_exe else ""
                g["drive_folder"] = new_drive
                g["archive_path"] = new_archive
                g["local_copy"] = new_local
                g["trigger_launch"] = new_trigger_launch
                g["trigger_close"] = new_trigger_close
                g["interval_min"] = new_interval
                g["max_backups"] = new_max_backups
                updated_game = dict(g)
                break
        else:
            messagebox.showerror("Error", "Game not found in config.", parent=self)
            return

        ss.save_config(cfg)
        ss.log.info(f"Updated game config: {new_name}")

        # Re-fetch thumbnail if name changed
        if new_name != self.original_name:
            _thumb_mgr.invalidate(self.original_name)
            threading.Thread(target=_thumb_mgr.fetch_thumbnail,
                             args=(new_name,), daemon=True).start()

        # Restart watcher so it picks up the changes
        _, is_running, wcount = self.app._restart_watcher()
        watcher_msg = ""
        if is_running:
            watcher_msg = f"\nWatcher restarted — monitoring {wcount} game(s)."
        elif wcount == 0:
            watcher_msg = "\nNo games with executables — watcher not needed."

        # Upload updated config to Drive if Drive is configured
        if new_drive and ss.GDRIVE_AVAILABLE:
            self._upload_config_to_drive(updated_game, watcher_msg)
        else:
            messagebox.showinfo("Saved",
                                f"'{new_name}' updated successfully.{watcher_msg}",
                                parent=self)
            self.destroy()
            self.app._invalidate_panel("games")
            self.app.show_panel("games")

    def _upload_config_to_drive(self, game_entry: dict, watcher_msg: str = ""):
        """Upload only the game config JSON to the Drive folder after editing."""
        # Show a small progress indicator
        prog_win = ctk.CTkToplevel(self)
        prog_win.title("Syncing to Drive")
        prog_win.geometry("420x120")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        lbl = ctk.CTkLabel(prog_win, text="Uploading config to Drive...", font=FONT_BODY)
        lbl.pack(pady=(16, 4))
        lbl2 = ctk.CTkLabel(prog_win, text="", font=FONT_SMALL, text_color=COL_TEXT_DIM)
        lbl2.pack(pady=(0, 4))
        prog = ctk.CTkProgressBar(prog_win, width=360)
        prog.pack(pady=(0, 8))
        prog.configure(mode="indeterminate")
        prog.start()

        def _do():
            svc = ss.get_drive_service()
            folder_id = ss.get_or_create_drive_folder(svc, game_entry["drive_folder"])

            # Write temporary config file
            config_tmp = ss.BASE_DIR / "_savesync_game_config.json"
            config_tmp.write_text(
                json.dumps(game_entry, indent=2, ensure_ascii=False),
                encoding="utf-8")
            try:
                ss.upload_file_to_drive(svc, config_tmp, folder_id)
            finally:
                config_tmp.unlink(missing_ok=True)
            return True

        def _done(_):
            prog.stop()
            lbl.configure(text="✓ Config synced to Drive.", text_color=COL_SUCCESS)
            if watcher_msg:
                lbl2.configure(text=watcher_msg.strip(), text_color=COL_SUCCESS)
            prog_win.after(1500, lambda: [prog_win.destroy(), self.destroy(),
                                           self.app._invalidate_panel("games"),
                                           self.app.show_panel("games")])

        def _err(e):
            prog.stop()
            lbl.configure(text=f"⚠ Local saved, Drive sync failed: {e}",
                          text_color=COL_WARNING)
            if watcher_msg:
                lbl2.configure(text=watcher_msg.strip(), text_color=COL_SUCCESS)
            prog_win.after(3000, lambda: [prog_win.destroy(), self.destroy(),
                                           self.app._invalidate_panel("games"),
                                           self.app.show_panel("games")])

        run_in_thread(self, _do, _done, _err)


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

        # Close the wizard and show a post-add status window
        self.destroy()
        PostAddStatusWindow(self.app, self.game)


# ===============================================================
#  POST-ADD STATUS WINDOW
#  Shown after adding a game — restarts watcher, checks exe, etc.
# ===============================================================

class PostAddStatusWindow(ctk.CTkToplevel):
    """Shown after a game is added. Restarts the watcher, verifies
    the exe file exists, and reports the overall status."""

    def __init__(self, master: SaveSyncApp, game: dict):
        super().__init__(master)
        self.app = master
        self.game = game
        self.title(f"Adding — {game['name']}")
        self.geometry("500x340")
        self.resizable(False, False)
        self.grab_set()

        ctk.CTkLabel(self, text=f"Adding: {game['name']}", font=FONT_TITLE).pack(
            anchor="w", padx=20, pady=(16, 8))

        sep = ctk.CTkFrame(self, height=1, fg_color=COL_TEXT_DIM)
        sep.pack(fill="x", padx=20, pady=(0, 12))

        # Status lines
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=20)

        self.lbl_config = ctk.CTkLabel(
            self.status_frame, text="● Config saved...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_config.pack(anchor="w", pady=2)

        self.lbl_exe = ctk.CTkLabel(
            self.status_frame, text="● Checking executable...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_exe.pack(anchor="w", pady=2)

        self.lbl_save_path = ctk.CTkLabel(
            self.status_frame, text="● Checking save path...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_save_path.pack(anchor="w", pady=2)

        self.lbl_watcher = ctk.CTkLabel(
            self.status_frame, text="● Restarting watcher...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_watcher.pack(anchor="w", pady=2)

        self.lbl_thumb = ctk.CTkLabel(
            self.status_frame, text="● Fetching cover art...",
            font=FONT_BODY, text_color=COL_TEXT_DIM)
        self.lbl_thumb.pack(anchor="w", pady=2)

        sep2 = ctk.CTkFrame(self, height=1, fg_color=COL_TEXT_DIM)
        sep2.pack(fill="x", padx=20, pady=12)

        self.lbl_summary = ctk.CTkLabel(
            self, text="", font=FONT_HEAD, wraplength=440, justify="left")
        self.lbl_summary.pack(anchor="w", padx=20)

        self.btn_close = ctk.CTkButton(
            self, text="Done", width=120, font=FONT_BODY,
            fg_color=COL_ACCENT, hover_color=COL_ACCENT_HVR,
            command=self._close)
        self.btn_close.pack(pady=(12, 16))
        self.btn_close.pack_forget()  # hidden until checks complete

        # Run checks after a short delay so the window renders
        self.after(200, self._run_checks)

    def _run_checks(self):
        game = self.game
        all_ok = True

        # 1. Config saved (already done before this window opens)
        self.lbl_config.configure(
            text="✓ Config saved to local list.",
            text_color=COL_SUCCESS)

        # 2. Check executable
        exe_path = game.get("exe_path", "")
        if exe_path:
            exe_exists = Path(exe_path).exists()
            if exe_exists:
                self.lbl_exe.configure(
                    text=f"✓ Executable found: {Path(exe_path).name}",
                    text_color=COL_SUCCESS)
            else:
                self.lbl_exe.configure(
                    text=f"⚠ Executable not found at: {exe_path}\n"
                         f"   The watcher won't detect this game until the path is corrected.",
                    text_color=COL_WARNING)
                all_ok = False
        else:
            self.lbl_exe.configure(
                text="○ No executable set — watcher will not track this game.",
                text_color=COL_TEXT_DIM)

        # 3. Check save path
        save_path = game.get("save_path", "")
        if save_path:
            sp_exists = Path(save_path).exists()
            if sp_exists:
                # Count files
                p = Path(save_path)
                if p.is_dir():
                    file_count = len([f for f in p.rglob("*") if f.is_file()])
                else:
                    file_count = 1 if p.is_file() else 0
                self.lbl_save_path.configure(
                    text=f"✓ Save path found: {file_count} file(s) detected.",
                    text_color=COL_SUCCESS)
            else:
                self.lbl_save_path.configure(
                    text=f"⚠ Save path does not exist yet: {save_path}\n"
                         f"   It will be created when you first run the game.",
                    text_color=COL_WARNING)
        else:
            self.lbl_save_path.configure(
                text="○ No save path set.",
                text_color=COL_TEXT_DIM)
            all_ok = False

        # 4. Restart watcher
        was_running, is_running, watchable_count = self.app._restart_watcher()
        if is_running:
            if was_running:
                self.lbl_watcher.configure(
                    text=f"✓ Watcher restarted — now monitoring {watchable_count} game(s).",
                    text_color=COL_SUCCESS)
            else:
                self.lbl_watcher.configure(
                    text=f"✓ Watcher started — now monitoring {watchable_count} game(s).",
                    text_color=COL_SUCCESS)
        else:
            if watchable_count == 0:
                self.lbl_watcher.configure(
                    text="○ No games with executables — watcher not needed.",
                    text_color=COL_TEXT_DIM)
            else:
                self.lbl_watcher.configure(
                    text="⚠ Watcher could not be started.",
                    text_color=COL_WARNING)
                all_ok = False

        # 5. Fetch thumbnail (async — don't block the UI)
        self._all_ok = all_ok
        self._fetch_thumb(game["name"])

    def _fetch_thumb(self, game_name: str):
        """Fetch thumbnail in background, then show final summary."""
        def _worker():
            ok = _thumb_mgr.fetch_thumbnail(game_name)
            self.after(0, lambda: self._on_thumb_done(ok))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_thumb_done(self, found: bool):
        game = self.game
        if found:
            self.lbl_thumb.configure(
                text="✓ Cover art found and cached.",
                text_color=COL_SUCCESS)
        else:
            self.lbl_thumb.configure(
                text="○ No cover art found — using placeholder.",
                text_color=COL_TEXT_DIM)

        # Summary
        all_ok = self._all_ok
        if all_ok:
            self.lbl_summary.configure(
                text=f"✓ '{game['name']}' added successfully. Everything is as it should be.",
                text_color=COL_SUCCESS)
        else:
            self.lbl_summary.configure(
                text=f"'{game['name']}' added with some notes — review above.",
                text_color=COL_WARNING)

        self.btn_close.pack(pady=(12, 16))

    def _close(self):
        self.destroy()
        self.app._invalidate_panel("games")
        self.app.show_panel("games")


# ===============================================================
#  ENTRY POINT
# ===============================================================
#
#  Normal:      pythonw savesync_gui.py
#               Opens the full GUI window.
#
#  Minimized:   pythonw savesync_gui.py --minimized
#               Starts the full app, auto-starts the watcher,
#               and hides straight to the system tray.
#               Used by the Startup folder .vbs launcher.
#
# ===============================================================

if __name__ == "__main__":
    try:
        app = SaveSyncApp()
        app.mainloop()
    except Exception as _fatal:
        # If pythonw is used, there's no console — write to a crash log
        import traceback as _tb
        _crash_log = Path(__file__).resolve().parent / "savesync_crash.log"
        _crash_text = _tb.format_exc()
        try:
            _crash_log.write_text(
                f"SaveSync GUI crashed at {datetime.datetime.now()}\n\n{_crash_text}",
                encoding="utf-8")
        except Exception:
            pass
        # Also try to show a messagebox (may fail if Tk itself is broken)
        try:
            import tkinter.messagebox as _mbox
            _mbox.showerror("SaveSync — Fatal Error",
                            f"SaveSync failed to start:\n\n{_fatal}\n\n"
                            f"Details written to:\n{_crash_log}")
        except Exception:
            pass
        raise
