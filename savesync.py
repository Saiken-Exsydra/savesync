"""
SaveSync — Indie Game Save Backup Manager
Terminal UI (TUI) version — navigate with numbers, confirm with y/n.

Dependencies:
    pip install py7zr schedule psutil google-auth google-auth-oauthlib \
                google-api-python-client
"""

import os
import sys
import json
import time
import shutil
import logging
import datetime
import threading
from pathlib import Path

import psutil
import py7zr
import schedule

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

# ---------------------------------------------------------------
# Paths & logging
# ---------------------------------------------------------------

BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "savesync_config.json"
TOKEN_FILE  = BASE_DIR / "gdrive_token.json"
CREDS_FILE  = BASE_DIR / "gdrive_credentials.json"
LOG_FILE    = BASE_DIR / "savesync.log"
SCOPES      = ["https://www.googleapis.com/auth/drive.file"]

MANIFEST_URL   = "https://raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml"
MANIFEST_FILE  = BASE_DIR / "ludusavi_manifest.yaml"
MANIFEST_INDEX = BASE_DIR / "ludusavi_index.json"
MANIFEST_META  = BASE_DIR / "ludusavi_meta.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("savesync")


# ---------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------

def resize_terminal():
    """Resize the terminal window to a comfortable size on Windows."""
    if os.name == "nt":
        os.system("mode con: cols=80 lines=40")

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def hr(char="─", width=54):
    print(char * width)

def header(title=""):
    clear()
    print()
    print("  ░█▀▀░█▀█░█░█░█▀▀░░░█▀▀░█░█░█▀█░█▀▀")
    print("  ░▀▀█░█▀█░▀▄▀░█▀▀░░░▀▀█░░█░░█░█░█░░")
    print("  ░▀▀▀░▀░▀░░▀░░▀▀▀░░░▀▀▀░░▀░░▀░▀░▀▀▀")
    print()
    if title:
        print(f"  {title}")
        print()

def pause(msg="  Press Enter to continue..."):
    input(msg)

def ask(prompt, default=""):
    val = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return val if val else default

def confirm(prompt):
    ans = input(f"  {prompt} [y/n]: ").strip().lower()
    return ans == "y"

def progress(pct: int, msg: str):
    """Print a single progress line. pct is 0-100, message describes current step."""
    bar_total = 20
    filled    = int(bar_total * pct / 100)
    bar       = "█" * filled + "░" * (bar_total - filled)
    print(f"  [{bar}] {pct:>3}%  {msg}")

def now_iso() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def fmt_ts(iso: str) -> str:
    """Format an ISO timestamp for display: '01 Apr 2025 at 14:32 UTC'"""
    try:
        dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%d %b %Y at %H:%M UTC")
    except Exception:
        return iso or "unknown"

def notify(title: str, message: str):
    """Send a Windows 11 toast notification. Silently ignored on non-Windows or if win11toast is not installed."""
    try:
        import platform
        if platform.system() != "Windows":
            return
        from win11toast import notify as _notify
        _notify("SaveSync", message, on_click=None)
    except Exception:
        pass  # Never crash the backup because of a notification failure

def pick(prompt, options, allow_back=True):
    """
    Display a numbered list and return the chosen index (0-based).
    Returns None if user goes back.
    """
    print(f"  {prompt}\n")
    for i, opt in enumerate(options, 1):
        print(f"    {i}.  {opt}")
    if allow_back:
        print(f"\n    0.  ← back")
    print()
    while True:
        raw = input("  > ").strip()
        if raw == "0" and allow_back:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Please enter a number between 1 and {len(options)}.")


# ---------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------

GAME_DEFAULTS = {
    "name":           "",
    "save_path":      "",
    "exe_name":       "",   # process name for watcher (e.g. hollow_knight.exe)
    "exe_path":       "",   # full path to launch the game (e.g. C:/Games/HK/hollow_knight.exe)
    "drive_folder":   "",
    "archive_path":   "",
    "local_copy":     "",
    "trigger_launch": True,
    "trigger_close":  True,
    "interval_min":   0,
    "max_backups":    10,
}

# ---------------------------------------------------------------
# Ludusavi manifest — download, index, search
# ---------------------------------------------------------------

def _win_placeholders() -> dict:
    """Map Ludusavi path placeholders to real Windows paths for this machine."""
    home = Path.home()
    import os
    return {
        "<home>":               str(home).replace("\\", "/"),
        "<winAppData>":         os.environ.get("APPDATA",      str(home / "AppData/Roaming")).replace("\\", "/"),
        "<winLocalAppData>":    os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")).replace("\\", "/"),
        "<winLocalAppDataLow>": str(home / "AppData/LocalLow").replace("\\", "/"),
        "<winDocuments>":       str(home / "Documents").replace("\\", "/"),
        "<winPublic>":          "C:/Users/Public",
        "<winDir>":             os.environ.get("WINDIR", "C:/Windows").replace("\\", "/"),
        "<winProgramData>":     os.environ.get("PROGRAMDATA", "C:/ProgramData").replace("\\", "/"),
    }

# Placeholders we cannot resolve — paths containing these are skipped
_UNRESOLVABLE = {"<base>", "<root>", "<game>", "<xdgData>", "<xdgConfig>",
                 "<xdgCache>", "<osxHome>", "<uid>"}


def _resolve_path(template: str) -> str | None:
    """Replace placeholders in a Ludusavi path template with real paths.
    Returns None if the path contains an unresolvable placeholder."""
    for token in _UNRESOLVABLE:
        if token in template:
            return None
    result = template
    for placeholder, value in _win_placeholders().items():
        result = result.replace(placeholder, value)
    # <storeUserId> becomes a wildcard — user will see a note
    result = result.replace("<storeUserId>", "*")
    return result


def download_manifest(silent=False) -> bool:
    """Download the Ludusavi manifest from GitHub. Returns True on success."""
    try:
        import urllib.request
        if not silent:
            print("  Downloading Ludusavi game database from GitHub...")
            print("  (This is a large file — may take a moment on slow connections)")
            print()
        urllib.request.urlretrieve(MANIFEST_URL, MANIFEST_FILE)
        MANIFEST_META.write_text(
            json.dumps({"downloaded_at": now_iso()}, indent=2),
            encoding="utf-8"
        )
        if not silent:
            size_mb = MANIFEST_FILE.stat().st_size / 1_048_576
            print(f"  Downloaded: {size_mb:.1f} MB")
        return True
    except Exception as e:
        if not silent:
            print(f"  Failed to download: {e}")
        log.error(f"Manifest download failed: {e}")
        return False


def build_manifest_index(silent=False) -> bool:
    """Parse manifest.yaml and build a fast-search JSON index.
    Index format: { "game name lowercase": ["resolved/path1", "resolved/path2"] }
    Only includes save-tagged paths resolvable on Windows."""
    if not MANIFEST_FILE.exists():
        return False
    try:
        import yaml
    except ImportError:
        if not silent:
            print("  PyYAML not installed. Run: pip install pyyaml")
        return False

    if not silent:
        print("  Building search index (this takes a few seconds, only done once)...")

    try:
        with open(MANIFEST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        if not silent:
            print(f"  Failed to parse manifest: {e}")
        return False

    index = {}
    for game_name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        files = entry.get("files", {})
        if not files:
            continue
        resolved_paths = []
        for path_template, meta in files.items():
            # Only include paths tagged as save (skip config-only paths)
            tags = []
            if isinstance(meta, dict):
                tags = meta.get("tags", [])
            if tags and "save" not in tags:
                continue
            resolved = _resolve_path(path_template)
            if resolved:
                resolved_paths.append(resolved)
        if resolved_paths:
            index[game_name.lower()] = {
                "name":  game_name,
                "paths": resolved_paths,
            }

    MANIFEST_INDEX.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    if not silent:
        print(f"  Index built: {len(index):,} games with known save locations.")
    return True


def load_manifest_index() -> dict:
    """Load the pre-built index. Returns {} if not available."""
    if not MANIFEST_INDEX.exists():
        return {}
    try:
        return json.loads(MANIFEST_INDEX.read_text(encoding="utf-8"))
    except Exception:
        return {}


def manifest_db_age() -> str:
    """Return a human-readable age of the downloaded manifest."""
    if not MANIFEST_META.exists():
        return "not downloaded"
    try:
        meta = json.loads(MANIFEST_META.read_text(encoding="utf-8"))
        ts   = meta.get("downloaded_at", "")
        dt   = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
        age  = datetime.datetime.utcnow() - dt
        days = age.days
        if days == 0:
            return "downloaded today"
        elif days == 1:
            return "1 day old"
        else:
            return f"{days} days old"
    except Exception:
        return "unknown age"


def search_manifest(game_name: str) -> list:
    """Search the index for a game. Returns list of (display_name, [paths]) tuples.
    Priority: exact > all words matched > most words matched > partial substring."""
    index = load_manifest_index()
    if not index:
        return []

    query       = game_name.lower().strip()
    query_words = query.split()

    # 1. Exact match — highest priority, return immediately
    if query in index:
        entry = index[query]
        return [(entry["name"], entry["paths"])]

    scored = []
    for key, entry in index.items():
        key_words = key.split()

        # Count how many query words appear in the key
        words_matched = sum(1 for w in query_words if w in key_words)

        # Skip entries that share zero words with the query
        if words_matched == 0:
            continue

        # Bonus: all words matched
        all_matched = words_matched == len(query_words)

        # Penalty: how different the total length is
        length_diff = abs(len(key) - len(query))

        # Score: more words matched = better, fewer length difference = better
        # Multiply words_matched heavily so a 4-word match always beats a 1-word match
        score = (words_matched * 100) - length_diff

        # Extra boost if the full query string is a substring of the key or vice versa
        if query in key or key in query:
            score += 50

        scored.append((score, all_matched, entry["name"], entry["paths"]))

    if not scored:
        return []

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return top 8
    return [(name, paths) for _, _, name, paths in scored[:8]]


def ensure_manifest_ready(silent=False) -> bool:
    """Check if manifest and index are available. Offer to download if not."""
    if MANIFEST_INDEX.exists():
        return True
    if not MANIFEST_FILE.exists():
        if not silent:
            print("  The Ludusavi game database has not been downloaded yet.")
            print()
            if not confirm("Download it now? (~15-50 MB, one-time download)"):
                return False
        if not download_manifest(silent=silent):
            return False
    if not MANIFEST_INDEX.exists():
        if not build_manifest_index(silent=silent):
            return False
    return True


SAVE_LOCATIONS_FILE = BASE_DIR / "save_locations.txt"


def load_save_locations() -> dict:
    """Load save_locations.txt into a dict of {lower_game_name: (original_name, path)}."""
    locations = {}
    if not SAVE_LOCATIONS_FILE.exists():
        return locations
    for line in SAVE_LOCATIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            name = parts[0].strip()
            path = parts[1].strip()
            locations[name.lower()] = (name, path)
    return locations


def lookup_save_location(game_name: str) -> str | None:
    """Return the suggested save path for a game name, or None if not found.
    Does a fuzzy check — the query just needs to appear anywhere in the listed name."""
    locations = load_save_locations()
    query = game_name.lower().strip()
    # Exact match first
    if query in locations:
        return locations[query][1]
    # Partial match — find entries where the query is a substring of the key
    matches = [(k, v) for k, v in locations.items() if query in k or k in query]
    if len(matches) == 1:
        return matches[0][1][1]
    if len(matches) > 1:
        # Return the closest match by length difference
        matches.sort(key=lambda x: abs(len(x[0]) - len(query)))
        return matches[0][1][1]
    return None


def append_save_location(game_name: str, path: str):
    """Add or update an entry in save_locations.txt."""
    locations = load_save_locations()
    key = game_name.lower()
    lines = []
    if SAVE_LOCATIONS_FILE.exists():
        lines = SAVE_LOCATIONS_FILE.read_text(encoding="utf-8").splitlines()

    new_entry = f"{game_name}, {path}"
    # If already exists, update the line in place
    if key in locations:
        updated = []
        for line in lines:
            parts = line.split(",", 1)
            if len(parts) == 2 and parts[0].strip().lower() == key:
                updated.append(new_entry)
            else:
                updated.append(line)
        lines = updated
    else:
        lines.append(new_entry)

    SAVE_LOCATIONS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps({"games": []}, indent=2))
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------

def get_drive_service():
    if not GDRIVE_AVAILABLE:
        raise RuntimeError("Run: pip install google-api-python-client google-auth-oauthlib")
    if not CREDS_FILE.exists():
        raise FileNotFoundError(f"Missing {CREDS_FILE}. See README for setup instructions.")
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)

def get_or_create_drive_folder(service, folder_path: str) -> str:
    parts = [p for p in folder_path.replace("\\", "/").split("/") if p]
    parent_id = "root"
    for part in parts:
        q = (f"name='{part}' and mimeType='application/vnd.google-apps.folder' "
             f"and '{parent_id}' in parents and trashed=false")
        res = service.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        if files:
            parent_id = files[0]["id"]
        else:
            meta = {"name": part, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
            f = service.files().create(body=meta, fields="id").execute()
            parent_id = f["id"]
    return parent_id

def upload_file_to_drive(service, local_path: Path, folder_id: str):
    fname = local_path.name
    q = f"name='{fname}' and '{folder_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id)").execute()
    existing = res.get("files", [])
    media = MediaFileUpload(str(local_path), resumable=True)
    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute()
    else:
        meta = {"name": fname, "parents": [folder_id]}
        service.files().create(body=meta, media_body=media, fields="id").execute()
    log.info(f"Drive <- {local_path.name}")

def backup_to_drive(game: dict, files: list, silent=False):
    if not silent: progress(5, "Connecting to Google Drive...")
    service = get_drive_service()
    if not silent: progress(15, "Locating Drive folder...")
    folder_id = get_or_create_drive_folder(service, game["drive_folder"])
    total = len(files)
    for i, f in enumerate(files):
        pct = 20 + int(70 * (i / max(total, 1)))
        if not silent: progress(pct, f"Uploading {f.name}")
        upload_file_to_drive(service, f, folder_id)
    if not silent: progress(92, "Uploading game config...")
    stamped = dict(game)
    stamped["backup_timestamp"] = now_iso()
    config_tmp = BASE_DIR / "_savesync_game_config.json"
    config_tmp.write_text(json.dumps(stamped, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        upload_file_to_drive(service, config_tmp, folder_id)
    finally:
        config_tmp.unlink()
    if not silent: progress(100, "Done.")
    return stamped["backup_timestamp"]


def list_drive_game_folders(service, root_folder="SaveSync") -> list:
    """Return list of (folder_name, folder_id) inside the SaveSync root on Drive."""
    # Find or confirm root folder exists
    q = (f"name='{root_folder}' and mimeType='application/vnd.google-apps.folder' "
         f"and 'root' in parents and trashed=false")
    res = service.files().list(q=q, fields="files(id,name)").execute()
    roots = res.get("files", [])
    if not roots:
        return []
    root_id = roots[0]["id"]
    # List subfolders (one per game)
    q2 = (f"mimeType='application/vnd.google-apps.folder' "
          f"and '{root_id}' in parents and trashed=false")
    res2 = service.files().list(q=q2, fields="files(id,name)", orderBy="name").execute()
    return [(f["name"], f["id"]) for f in res2.get("files", [])]


def fetch_game_config_from_drive(service, folder_id: str) -> dict | None:
    """Download and parse _savesync_game_config.json from a Drive game folder."""
    q = f"name='_savesync_game_config.json' and '{folder_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id)").execute()
    files = res.get("files", [])
    if not files:
        return None
    file_id = files[0]["id"]
    content = service.files().get_media(fileId=file_id).execute()
    try:
        return json.loads(content.decode("utf-8"))
    except Exception:
        return None


def list_drive_save_files(service, folder_id: str) -> list:
    """List all non-config files in a Drive game folder."""
    q = (f"'{folder_id}' in parents and trashed=false "
         f"and name != '_savesync_game_config.json' "
         f"and mimeType != 'application/vnd.google-apps.folder'")
    res = service.files().list(q=q, fields="files(id,name,size,modifiedTime)").execute()
    return res.get("files", [])


def download_file_from_drive(service, file_id: str, dest_path: Path):
    """Download a single file from Drive to dest_path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    content = service.files().get_media(fileId=file_id).execute()
    dest_path.write_bytes(content)


# ---------------------------------------------------------------
# Archive & local copy
# ---------------------------------------------------------------

def backup_to_7z(game: dict, files: list, silent=False):
    archive_path = Path(game["archive_path"])
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot = archive_path.parent / f"{archive_path.stem}_{ts}.7z"
    if not silent: progress(10, "Creating .7z archive...")
    total = len(files)
    with py7zr.SevenZipFile(snapshot, "w") as zf:
        for i, f in enumerate(files):
            pct = 15 + int(75 * (i / max(total, 1)))
            if not silent: progress(pct, f"Compressing {f.name}")
            zf.write(f, arcname=f.name)
    if not silent: progress(95, "Cleaning up old snapshots...")
    log.info(f"7z <- {snapshot.name}")
    max_b = int(game.get("max_backups", 10))
    all_snaps = sorted(archive_path.parent.glob(archive_path.stem + "_*.7z"))
    while len(all_snaps) > max_b:
        all_snaps[0].unlink()
        all_snaps = all_snaps[1:]
    if not silent: progress(100, "Done.")

def backup_to_local(game: dict, files: list, silent=False):
    dest = Path(game["local_copy"])
    dest.mkdir(parents=True, exist_ok=True)
    total = len(files)
    if not silent: progress(5, "Copying files to local folder...")
    for i, f in enumerate(files):
        pct = 10 + int(85 * (i / max(total, 1)))
        if not silent: progress(pct, f"Copying {f.name}")
        shutil.copy2(f, dest / f.name)
    log.info(f"local copy -> {dest}")
    if not silent: progress(100, "Done.")


# ---------------------------------------------------------------
# Core backup
# ---------------------------------------------------------------

def collect_save_files(game: dict) -> list:
    p = Path(game["save_path"])
    if not p.exists():
        return []
    if p.is_file():
        return [p]
    return [f for f in p.rglob("*") if f.is_file()]

def run_backup(game: dict, reason="manual", silent=False):
    name = game["name"]
    log.info(f"[{name}] backup triggered — {reason}")

    if not silent: print(f"\n  Scanning save files...")
    files = collect_save_files(game)
    if not files:
        if not silent:
            print(f"  Error: no save files found at: {game['save_path']}")
        return False
    if not silent: print(f"  Found {len(files)} file(s). Starting backup...\n")

    errors = []

    if game.get("drive_folder"):
        if not silent:
            # Check what is already on Drive before uploading
            try:
                _svc = get_drive_service()
                _existing = fetch_game_config_from_drive(
                    _svc,
                    get_or_create_drive_folder(_svc, game["drive_folder"])
                )
                if _existing and _existing.get("backup_timestamp"):
                    print(f"  Drive backup found — last saved {fmt_ts(_existing['backup_timestamp'])}")
                    print(f"  Updating now...")
                else:
                    print("  No previous Drive backup found — creating first backup.")
            except Exception:
                pass
            print("  → Backing up to Google Drive")
        try:
            ts = backup_to_drive(game, files, silent=silent)
            # Write timestamp into the local config entry so we can compare on next run
            if ts:
                local_cfg = load_config()
                for g in local_cfg["games"]:
                    if g["name"] == game["name"]:
                        g["backup_timestamp"] = ts
                        break
                save_config(local_cfg)
                game["backup_timestamp"] = ts
        except Exception as e:
            msg = f"Drive upload failed: {e}"
            errors.append(msg)
            if not silent: print(f"  ✗ {msg}")
            log.error(f"[{name}] {msg}")

    if game.get("archive_path"):
        if not silent: print("\n  → Creating .7z archive")
        try:
            backup_to_7z(game, files, silent=silent)
        except Exception as e:
            msg = f".7z archive failed: {e}"
            errors.append(msg)
            if not silent: print(f"  ✗ {msg}")
            log.error(f"[{name}] {msg}")

    if game.get("local_copy"):
        if not silent: print("\n  → Copying to local folder")
        try:
            backup_to_local(game, files, silent=silent)
        except Exception as e:
            msg = f"Local copy failed: {e}"
            errors.append(msg)
            if not silent: print(f"  ✗ {msg}")
            log.error(f"[{name}] {msg}")

    if not silent:
        print()
        if errors:
            print(f"  Backup finished with {len(errors)} error(s). Check savesync.log.")
        else:
            print(f"  ✓ Backup complete — {len(files)} file(s)")

    log.info(f"[{name}] backup complete — {len(files)} file(s)")
    return len(errors) == 0


# ---------------------------------------------------------------
# Process watcher
# ---------------------------------------------------------------

def _notify_after_backup(game: dict):
    """Run backup on close, then notify success or failure."""
    time.sleep(2)  # small delay to let the game fully release file locks
    ok = run_backup(game, reason="game closed", silent=True)
    if ok:
        notify(
            "Backup complete",
            f"{game['name']} — save files backed up successfully."
        )
    else:
        notify(
            "Backup failed",
            f"{game['name']} — something went wrong during backup. "
            f"Check your internet connection and open SaveSync to diagnose."
        )


class GameWatcher(threading.Thread):
    def __init__(self, games):
        super().__init__(daemon=True)
        # Support old entries that only have exe_path — derive exe_name from it
        for g in games:
            if not g.get("exe_name") and g.get("exe_path"):
                g["exe_name"] = Path(g["exe_path"]).name
        self.games = {g["exe_name"].lower(): g for g in games if g.get("exe_name")}
        self.running_pids = {}
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        while not self._stop.is_set():
            current = {}
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = proc.info["name"].lower()
                    if pname in self.games:
                        current[pname] = proc.info["pid"]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            for exe, pid in current.items():
                if exe not in self.running_pids:
                    self.running_pids[exe] = pid
                    g = self.games[exe]
                    # Instant notification the moment the process is seen —
                    # fires before backup so user knows immediately SaveSync caught it
                    notify(
                        "SaveSync — Watcher online",
                        f"{g['name']} detected. Saves are being watched."
                    )
                    log.info(f"[{g['name']}] process detected: {exe}")
                    if g.get("trigger_launch"):
                        threading.Thread(
                            target=run_backup, args=(g, "game launched", True), daemon=True
                        ).start()
            for exe in list(self.running_pids):
                if exe not in current:
                    g = self.games[exe]
                    del self.running_pids[exe]
                    if g.get("trigger_close"):
                        # Instant notification — fires the moment the process disappears
                        notify(
                            "Game closed — backup starting",
                            f"{g['name']} closed. Backing up your save files now..."
                        )
                        log.info(f"[{g['name']}] process closed, backup starting")
                        threading.Thread(
                            target=_notify_after_backup, args=(g,), daemon=True
                        ).start()
            time.sleep(3)


# ---------------------------------------------------------------
# Launcher .bat writer
# ---------------------------------------------------------------

def write_launcher(game: dict):
    if not game.get("exe_path"):
        return
    name     = game["name"]
    exe_path = game["exe_path"]
    ext      = Path(exe_path).suffix.lower()
    bat      = BASE_DIR / f"Launch {name}.bat"

    # .bat files must be called with `call` so the launcher waits for them to finish.
    # .exe and everything else uses `start /wait` which also blocks until closed.
    if ext == ".bat":
        launch_cmd = f'call "{exe_path}"'
    else:
        launch_cmd = f'start /wait "" "{exe_path}"'

    lines = [
        "@echo off",
        f'echo [SaveSync] Backing up {name} before launch...',
        f'python "{BASE_DIR / "savesync.py"}" --backup "{name}"',
        f'echo [SaveSync] Starting {name}...',
        launch_cmd,
        f'echo [SaveSync] {name} closed. Backing up...',
        f'python "{BASE_DIR / "savesync.py"}" --backup "{name}"',
        'echo [SaveSync] Done. Press any key to close.',
        'pause >nul',
    ]
    bat.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Launcher written: {bat.name}")


# ---------------------------------------------------------------
# TUI screens
# ---------------------------------------------------------------

def screen_main():
    while True:
        header()
        print("    1.  Add a game")
        print("    2.  My games")
        print("    3.  Remove a game")
        print("    4.  Health check")
        print()
        print("    5.  Backup now")
        print("    6.  Restore from Drive")
        print()
        print("    7.  Watcher")
        print("    8.  Settings")
        print()
        print("    0.  Exit")
        print()
        choice = input("  > ").strip()

        if choice == "1":
            screen_add_game()
        elif choice == "2":
            screen_list_games()
        elif choice == "3":
            screen_remove_game()
        elif choice == "4":
            screen_integrity_check()
        elif choice == "5":
            screen_backup_now()
        elif choice == "6":
            screen_restore_from_drive()
        elif choice == "7":
            screen_watcher_setup()
        elif choice == "8":
            screen_settings()
        elif choice == "0":
            clear()
            print("\n  Goodbye!\n")
            sys.exit(0)
        else:
            print("\n  Invalid option. Try again.")
            time.sleep(1)





# ---------------------------------------------------------------

def screen_watcher_setup():
    while True:
        header("Watcher")

        import subprocess
        check = subprocess.run(
            ["schtasks", "/query", "/tn", "SaveSyncWatcher"],
            capture_output=True
        )
        task_installed = check.returncode == 0

        print("  The watcher runs silently in the background and monitors")
        print("  your registered games. The moment it sees a game open,")
        print("  it backs up your saves. When the game closes, it backs")
        print("  up again. You never have to do anything manually.")
        print()
        if task_installed:
            print("  Status  Windows startup task is installed and active.")
        else:
            print("  Status  Not running at startup.")
        print()
        print("    1.  Start now")
        print("        Runs in this window. Stops when you close it.")
        print()
        print("    2.  Install on Windows startup")
        print("        Starts silently every time you log into Windows.")
        print("        No window. No manual steps. Fully automatic.")
        print()
        print("    3.  Remove from Windows startup")
        print("        Uninstalls the startup task if you no longer")
        print("        want the watcher running automatically.")
        print()
        print("    0.  Back")
        print()
        choice = input("  > ").strip()

        if choice == "1":
            screen_watch()
        elif choice == "2":
            screen_install_startup(mode="install")
        elif choice == "3":
            screen_install_startup(mode="remove")
        elif choice == "0":
            return
        else:
            print("\n  Invalid option.")
            time.sleep(1)



# ---------------------------------------------------------------

def _install_startup_task():
    import platform
    import subprocess

    header("Install Windows Startup Task")
    print("  This registers SaveSync's watcher as a Windows Task Scheduler task.")
    print()
    print("  Once installed:")
    print("  · SaveSync starts silently every time you log into Windows")
    print("  · No terminal window appears — it runs completely in the background")
    print("  · Your registered games are monitored automatically")
    print("  · You will receive Windows notifications when saves are backed up")
    print()

    if platform.system() != "Windows":
        print("  This option is only available on Windows.")
        print()
        pause()
        return

    py_path     = Path(sys.executable)
    pythonw     = py_path.parent / "pythonw.exe"
    script_path = Path(__file__).resolve()
    task_name   = "SaveSyncWatcher"

    print(f"  Script  : {script_path}")
    print(f"  Runtime : {pythonw}")
    print()

    if not pythonw.exists():
        print("  Note: pythonw.exe not found — falling back to python.exe.")
        print("  A terminal window will briefly appear at startup.")
        print("  To fix, reinstall Python with the tcl/tk component included.")
        print()
        pythonw = py_path

    check = subprocess.run(
        ["schtasks", "/query", "/tn", task_name], capture_output=True
    )
    if check.returncode == 0:
        print("  A startup task already exists and will be updated.")
        print()
        subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True
        )

    if not confirm("Install startup task now?"):
        print("\n  Cancelled.")
        pause()
        return

    cmd = [
        "schtasks", "/create",
        "/tn",  task_name,
        "/tr",  f'"{pythonw}" "{script_path}" --watch',
        "/sc",  "ONLOGON",
        "/rl",  "HIGHEST",
        "/f",
    ]

    print()
    print("  Registering task... (a UAC prompt may appear)")
    print()
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("  ✓ Startup task installed.")
        print()
        print("  SaveSync will now start automatically every time you")
        print("  log into Windows. To start it right now without rebooting,")
        print("  go back and choose option 1 (Start watcher now).")
    else:
        print("  ✗ Failed to install task.")
        err = result.stderr.strip() or result.stdout.strip()
        if err:
            print(f"  Error: {err}")
        print()
        print("  Try running SaveSync as Administrator:")
        print("  Right-click SaveSync.bat → Run as administrator")
    print()
    pause()


# ---------------------------------------------------------------

def _remove_startup_task():
    import platform
    import subprocess

    header("Remove Windows Startup Task")
    print("  This will stop SaveSync from starting automatically with Windows.")
    print()
    print("  Your games, config and backup files are not affected.")
    print("  You can reinstall the task at any time from Watcher Setup.")
    print()

    if platform.system() != "Windows":
        print("  This option is only available on Windows.")
        print()
        pause()
        return

    task_name = "SaveSyncWatcher"
    check = subprocess.run(
        ["schtasks", "/query", "/tn", task_name], capture_output=True
    )

    if check.returncode != 0:
        print("  No startup task is currently installed. Nothing to remove.")
        print()
        pause()
        return

    if not confirm("Remove the SaveSync startup task?"):
        print("\n  Cancelled. Nothing was changed.")
        pause()
        return

    result = subprocess.run(
        ["schtasks", "/delete", "/tn", task_name, "/f"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("\n  ✓ Startup task removed.")
        print("  SaveSync will no longer start with Windows.")
    else:
        print(f"\n  ✗ Failed: {result.stderr.strip()}")
    print()
    pause()


# ---------------------------------------------------------------

def screen_add_game():
    header("Add a Game")

    g = dict(GAME_DEFAULTS)

    g["name"] = ask("Game name")
    if not g["name"]:
        print("\n  Name cannot be empty.")
        pause()
        return

    print()
    hr("·")
    print("  Searching for save location...\n")

    # --- 1. Check save_locations.txt first (personal overrides) ---
    manual_suggestion = lookup_save_location(g["name"])

    # --- 2. Check Ludusavi manifest ---
    manifest_results = []
    if ensure_manifest_ready(silent=True):
        manifest_results = search_manifest(g["name"])

    chosen_path = None

    if manual_suggestion:
        print(f"  Found in your personal list (save_locations.txt):")
        print(f"  → {manual_suggestion}")
        print()
        if manifest_results and manifest_results[0][0].lower() != g["name"].lower():
            # Also found in manifest — show both
            pass
        if confirm("Use this path?"):
            chosen_path = manual_suggestion

    if not chosen_path and manifest_results:
        if len(manifest_results) == 1:
            game_match, paths = manifest_results[0]
            print(f"  Found in Ludusavi database: {game_match}")
            print()
            if len(paths) == 1:
                print(f"  Save location: {paths[0]}")
                print()
                if "<storeUserId>" in paths[0] or "*" in paths[0]:
                    print("  Note: this path contains a wildcard (*) where your user ID")
                    print("  would go. Check the folder in Explorer to find the right one.")
                    print()
                if confirm("Use this path?"):
                    chosen_path = paths[0]
            else:
                print("  Multiple save paths found for this game:\n")
                for i, p in enumerate(paths, 1):
                    print(f"    {i}.  {p}")
                print(f"    0.  None of these — enter manually")
                print()
                while True:
                    raw = input("  > ").strip()
                    if raw == "0":
                        break
                    if raw.isdigit() and 1 <= int(raw) <= len(paths):
                        chosen_path = paths[int(raw) - 1]
                        break
                    print(f"  Enter a number between 0 and {len(paths)}.")
        else:
            print("  Found multiple games in the Ludusavi database:\n")
            for i, (gname, paths) in enumerate(manifest_results, 1):
                print(f"    {i}.  {gname}")
                for p in paths[:2]:
                    print(f"         {p}")
                if len(paths) > 2:
                    print(f"         ... and {len(paths)-2} more path(s)")
            print(f"    0.  None of these — enter manually")
            print()
            while True:
                raw = input("  > ").strip()
                if raw == "0":
                    break
                if raw.isdigit() and 1 <= int(raw) <= len(manifest_results):
                    _, paths = manifest_results[int(raw) - 1]
                    if len(paths) == 1:
                        chosen_path = paths[0]
                    else:
                        print("\n  Paths for that game:\n")
                        for j, p in enumerate(paths, 1):
                            print(f"    {j}.  {p}")
                        print(f"    0.  Enter manually")
                        print()
                        while True:
                            raw2 = input("  > ").strip()
                            if raw2 == "0":
                                break
                            if raw2.isdigit() and 1 <= int(raw2) <= len(paths):
                                chosen_path = paths[int(raw2) - 1]
                                break
                    break
                print(f"  Enter a number between 0 and {len(manifest_results)}.")

    if not chosen_path and not manual_suggestion and not manifest_results:
        print("  No suggestions found in database or personal list.")

    if not chosen_path:
        print()
        print("  Tip: point to the FOLDER that contains your saves.")
        print("  The entire folder (and subfolders) will be backed up.")
        print("  You can also point to a single file if needed.")
        print()
        g["save_path"] = ask("Save path (folder or file)")
    else:
        print()
        print(f"  Selected: {chosen_path}")
        print()
        override = confirm("Use a different path instead?")
        if override:
            print()
            g["save_path"] = ask("Save path (folder or file)")
        else:
            g["save_path"] = chosen_path

    print()
    hr("·")
    print("  Game launcher path\n")
    print("  Provide the full path to the file that opens your game.")
    print("  This can be a .exe, a .bat, or any other file that launches it.")
    print("  SaveSync will use this to:")
    print("    · Detect when the game is running (watcher)")
    print("    · Create a launcher shortcut (.bat) that backs up on open and close")
    print()
    print("  Leave blank to skip — you can still back up manually.")
    print()
    g["exe_path"] = ask("Full path to game launcher (or leave blank)")

    if g["exe_path"]:
        # Derive exe_name automatically from the path
        g["exe_name"] = Path(g["exe_path"]).name
        print()
        print(f"  Watcher will look for process: {g['exe_name']}")
        print("  Open Task Manager while the game runs to confirm this name appears there.")
        print("  If it differs, you can edit savesync_config.json to correct it.")

    print()
    hr("·")
    print("  Backup destinations — leave blank to skip\n")
    g["drive_folder"] = ask("Google Drive folder (e.g. SaveSync/MyGame)", "")
    g["archive_path"] = ask("Local .7z archive path (e.g. D:/Backups/mygame.7z)", "")
    g["local_copy"]   = ask("Local folder copy path", "")

    if not g["drive_folder"] and not g["archive_path"] and not g["local_copy"]:
        print("\n  At least one backup destination is required.")
        pause()
        return

    print()
    hr("·")
    print("  Trigger settings\n")

    if g["exe_path"]:
        g["trigger_launch"] = confirm("Backup when game LAUNCHES?")
        g["trigger_close"]  = confirm("Backup when game CLOSES?")
        iv = ask("Backup every N minutes while running (0 = off)", "0")
        g["interval_min"] = int(iv) if iv.isdigit() else 0

    mx = ask("Max .7z snapshots to keep", "10")
    g["max_backups"] = int(mx) if mx.isdigit() else 10

    # Summary
    print()
    hr()
    print("  Summary\n")
    print(f"    Name       : {g['name']}")
    print(f"    Save path  : {g['save_path']}")
    print(f"    Launcher   : {g['exe_path'] or '(not set)'}")
    if g.get("exe_name"):
        print(f"    Watches for: {g['exe_name']}")
    print(f"    Drive      : {g['drive_folder'] or '(skip)'}")
    print(f"    Archive    : {g['archive_path'] or '(skip)'}")
    print(f"    Local copy : {g['local_copy'] or '(skip)'}")
    print()

    if not confirm("Save this game?"):
        print("\n  Cancelled.")
        pause()
        return

    cfg = load_config()
    cfg["games"].append(g)
    save_config(cfg)
    log.info(f"Added game: {g['name']}")

    if g["exe_path"]:
        write_launcher(g)

    print(f"\n  '{g['name']}' added successfully.")

    # Offer to save the path to save_locations.txt
    existing = lookup_save_location(g["name"])
    if g.get("save_path") and g["save_path"] != existing:
        print()
        if existing:
            print(f"  The internal list has a different path for this game:")
            print(f"    Listed  : {existing}")
            print(f"    You used: {g['save_path']}")
            print()
            if confirm("Update the internal list with your path?"):
                append_save_location(g["name"], g["save_path"])
                print("  Internal list updated.")
        else:
            print("  This game is not in the internal locations list.")
            if confirm("Add it for future use?"):
                append_save_location(g["name"], g["save_path"])
                print("  Added to save_locations.txt.")

    pause()


# ---------------------------------------------------------------

def screen_list_games():
    header("Game List")
    cfg = load_config()
    games = cfg.get("games", [])

    if not games:
        print("  No games configured yet.")
        print("  Go back and choose option 1 to add a game.\n")
        pause()
        return

    for i, g in enumerate(games, 1):
        destinations = []
        if g.get("drive_folder"): destinations.append("Google Drive")
        if g.get("archive_path"): destinations.append(".7z archive")
        if g.get("local_copy"):   destinations.append("local folder")
        dest_str = " + ".join(destinations) if destinations else "no destination set!"

        triggers = []
        if g.get("trigger_launch"): triggers.append("on launch")
        if g.get("trigger_close"):  triggers.append("on close")
        if g.get("interval_min", 0) > 0:
            triggers.append(f"every {g['interval_min']} min")
        trig_str = ", ".join(triggers) if triggers else "manual only"

        print(f"  {i}.  {g['name']}")
        print(f"       path     : {g['save_path']}")
        print(f"       backs up : {dest_str}")
        print(f"       triggers : {trig_str}")
        if g.get("exe_path"):
            print(f"       launcher : {g['exe_path']}")
            exe_display = g.get("exe_name") or Path(g.get("exe_path","")).name
            print(f"       watching : {exe_display}")
        print()

    pause()


# ---------------------------------------------------------------

def screen_remove_game():
    header("Remove a Game")
    cfg = load_config()
    games = cfg.get("games", [])

    if not games:
        print("  No games configured.")
        pause()
        return

    names = [g["name"] for g in games]
    idx = pick("Which game do you want to remove?", names)
    if idx is None:
        return

    chosen = games[idx]
    print()
    print(f"  You selected: {chosen['name']}")
    print()
    print("  Note: this only removes the game from SaveSync.")
    print("  Your actual save files will NOT be deleted.")
    print()

    if confirm(f"Remove '{chosen['name']}' from SaveSync?"):
        cfg["games"].pop(idx)
        save_config(cfg)
        log.info(f"Removed game: {chosen['name']}")
        print(f"\n  '{chosen['name']}' removed.")
    else:
        print("\n  Cancelled. Nothing was changed.")

    pause()


# ---------------------------------------------------------------

def screen_backup_now():
    header("Backup Now")
    cfg = load_config()
    games = cfg.get("games", [])

    if not games:
        print("  No games configured.")
        pause()
        return

    names = [g["name"] for g in games]
    idx = pick("Which game do you want to back up?", names)
    if idx is None:
        return

    game = games[idx]
    print()
    print(f"  Backing up '{game['name']}'...")
    print()

    ok = run_backup(game, reason="manual")
    if ok:
        print(f"\n  Backup complete.")
    else:
        print(f"\n  Backup failed or no files found.")
        print(f"  Check savesync.log for details.")

    pause()


# ---------------------------------------------------------------

def screen_watch():
    header("Background Watcher")
    cfg = load_config()
    games = cfg.get("games", [])

    watchable = [g for g in games if g.get("exe_name")]
    if not watchable:
        print("  No games have an .exe name set.")
        print("  Edit your game entries and add the .exe name to enable auto-watch.\n")
        pause()
        return

    print("  The watcher will run in this window.")
    print("  It checks every 3 seconds for your configured game processes.")
    print("  Backups happen automatically when games launch or close.")
    print()
    print("  Press Ctrl+C at any time to stop.\n")
    print("  Watching for:\n")
    for g in watchable:
        exe_display = g.get("exe_name") or Path(g.get("exe_path","")).name
        print(f"    · {g['name']}  ({exe_display})")

    for g in games:
        iv = int(g.get("interval_min", 0))
        if iv > 0:
            schedule.every(iv).minutes.do(run_backup, game=g, reason="interval", silent=True)

    print()
    hr()
    print()

    watcher = GameWatcher(games)
    watcher.start()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        print("\n\n  Watcher stopped.")
        pause()


# ---------------------------------------------------------------

def screen_drive_setup():
    header("Google Drive Setup")

    if not GDRIVE_AVAILABLE:
        print("  Google API libraries not installed.")
        print()
        print("  Run this in your terminal first:\n")
        print("    pip install google-auth google-auth-oauthlib google-api-python-client")
        print()
        print("  Also recommended for Windows 11 notifications:")
        print("    pip install win11toast")
        print()
        pause()
        return

    if not CREDS_FILE.exists():
        print(f"  credentials file not found: {CREDS_FILE}\n")
        print("  To get it:\n")
        print("  1.  Go to https://console.cloud.google.com/")
        print("  2.  Create a project")
        print("  3.  APIs & Services  →  Enable 'Google Drive API'")
        print("  4.  Credentials  →  Create  →  OAuth 2.0 Client ID  →  Desktop App")
        print("  5.  Download the JSON file")
        print(f"  6.  Rename and save it as:")
        print(f"        {CREDS_FILE}")
        print()
        print("  Then come back here and run this option again.")
        print()
        pause()
        return

    print("  Credentials file found. Opening browser to authenticate...\n")
    try:
        service = get_drive_service()
        about = service.about().get(fields="user").execute()
        email = about["user"]["emailAddress"]
        print(f"  Authenticated as: {email}")
        print()
        print("  Google Drive backups are ready to use.")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")

    pause()




# ---------------------------------------------------------------

def screen_restore_from_drive():
    header("Restore Saves from Drive")

    if not GDRIVE_AVAILABLE:
        print("  SaveSync could not find the Google Drive libraries on this machine.")
        print()
        print("  To fix this, open a terminal and run:")
        print()
        print("    pip install google-auth google-auth-oauthlib google-api-python-client")
        print()
        print("  Then restart SaveSync and try again.")
        print()
        pause()
        return

    # Check if credentials file exists before even trying to connect
    if not CREDS_FILE.exists():
        print("  Google Drive has not been set up yet.")
        print()
        print("  SaveSync needs to be connected to your Google account")
        print("  before it can access any files on Drive.")
        print()
        print("  Here is what to do:")
        print()
        print("    1.  Go to Settings  →  Google Drive setup")
        print("    2.  Follow the steps shown there to authenticate")
        print("    3.  Come back here and try again")
        print()
        print("  If you get stuck, open the README.md file that came")
        print("  with SaveSync — it has step by step instructions")
        print("  with screenshots for the Google Drive setup process.")
        print()
        pause()
        return

    print("  Connecting to Google Drive...")
    try:
        service = get_drive_service()
    except Exception as e:
        print()
        print("  Could not connect to Google Drive.")
        print()
        # Give specific guidance based on the error type
        err = str(e).lower()
        if "token" in err or "credential" in err or "oauth" in err or "auth" in err:
            print("  This looks like an authentication problem.")
            print()
            print("  Here is what to do:")
            print()
            print("    1.  Go to Settings  →  Google Drive setup")
            print("    2.  Re-authenticate your Google account")
            print("    3.  Come back here and try again")
        elif "connection" in err or "network" in err or "timeout" in err or "ssl" in err:
            print("  This looks like a network problem.")
            print()
            print("  Here is what to do:")
            print()
            print("    1.  Check that your internet connection is working")
            print("    2.  Try again in a moment")
        else:
            print(f"  Error detail: {e}")
            print()
            print("  Here is what to do:")
            print()
            print("    1.  Go to Settings  →  Google Drive setup and re-authenticate")
            print("    2.  If that does not help, check the README.md file")
            print("        that came with SaveSync for troubleshooting steps")
        print()
        pause()
        return

    print("  Scanning SaveSync folder on Drive...\n")
    try:
        folders = list_drive_game_folders(service)
    except Exception as e:
        print(f"  Error reading Drive: {e}")
        print()
        pause()
        return

    if not folders:
        print("  No games were found in the SaveSync folder on Drive.")
        print()
        print("  This means either:")
        print()
        print("    · No backups have been made yet")
        print("      Back up at least one game first using option 5")
        print("      from the main menu, then come back here.")
        print()
        print("    · The backup was made under a different Google account")
        print("      Go to Settings  →  Google Drive setup to check")
        print("      which account SaveSync is connected to.")
        print()
        pause()
        return

    names = [name for name, _ in folders]
    idx = pick("Which game do you want to restore?", names)
    if idx is None:
        return

    folder_name, folder_id = folders[idx]
    print()
    print(f"  Reading config for '{folder_name}' from Drive...")

    drive_config = fetch_game_config_from_drive(service, folder_id)
    save_files   = list_drive_save_files(service, folder_id)

    if not save_files:
        print("  No save files found in that Drive folder.")
        print()
        pause()
        return

    # --- Determine local restore path ---
    local_cfg     = load_config()
    local_games   = local_cfg.get("games", [])
    matched_local = next((g for g in local_games if g["name"] == folder_name), None)

    # --- Timestamp comparison ----------------------------------------
    drive_ts = drive_config.get("backup_timestamp") if drive_config else None
    local_ts = matched_local.get("backup_timestamp") if matched_local else None

    print()
    hr("·")
    print("  Backup timestamps\n")

    if drive_ts:
        print(f"    Drive backup : {fmt_ts(drive_ts)}")
    else:
        print(f"    Drive backup : no timestamp recorded (first backup)")

    if local_ts:
        print(f"    Local record : {fmt_ts(local_ts)}")
    else:
        print(f"    Local record : no timestamp recorded")

    print()

    # Parse for comparison
    local_is_newer = False
    if drive_ts and local_ts:
        try:
            dt_drive = datetime.datetime.strptime(drive_ts, "%Y-%m-%dT%H:%M:%SZ")
            dt_local = datetime.datetime.strptime(local_ts, "%Y-%m-%dT%H:%M:%SZ")
            local_is_newer = dt_local > dt_drive
        except Exception:
            pass

    if local_is_newer:
        hr("·")
        print("  ⚠  Your local saves are NEWER than the Drive backup.")
        print("     Restoring from Drive will overwrite more recent progress.")
        print()
        print("    1.  Back up local saves to Drive instead (recommended)")
        print("    2.  Restore from Drive anyway")
        print("    0.  Cancel")
        print()
        choice = input("  > ").strip()
        if choice == "0":
            print("\n  Cancelled. Nothing was changed.")
            pause()
            return
        elif choice == "1":
            # Run backup for this game right now
            game_to_backup = matched_local or drive_config
            if not game_to_backup:
                print("  No local config found — cannot back up.")
                pause()
                return
            print()
            run_backup(game_to_backup, reason="manual — chosen over restore")
            pause()
            return
        # choice == "2" falls through to restore
    else:
        if drive_ts and local_ts:
            print("  Drive backup is more recent than your local record.")
            print("  Safe to restore.")
        elif drive_ts and not local_ts:
            print("  No local timestamp found — Drive backup will be restored.")
        print()

    # --- Determine restore path ----------------------------------------
    hr("·")
    if matched_local:
        default_path = matched_local["save_path"]
        print(f"  This game is already configured locally.")
        print(f"  Local save path: {default_path}")
        print()
        change = confirm("Use this path? (n = enter a different one)")
        restore_path = default_path if change else ask("Enter restore path")
    elif drive_config and drive_config.get("save_path"):
        default_path = drive_config["save_path"]
        print(f"  Config found on Drive.")
        print(f"  Original save path: {default_path}")
        print()
        print("  This path is from the machine that made the backup.")
        print("  Confirm it is correct for THIS machine, or enter a new one.")
        print()
        use_default = confirm(f"Restore to '{default_path}'?")
        restore_path = default_path if use_default else ask("Enter restore path")
    else:
        print("  No config found on Drive for this game.")
        print("  Please enter the local path where saves should be restored.")
        print()
        restore_path = ask("Restore path (folder)")

    if not restore_path:
        print("  No path entered. Cancelled.")
        pause()
        return

    print()
    hr("·")
    print("  Safe restore: your current local saves will be archived")
    print("  to a .7z snapshot before anything is overwritten.")
    print()
    print(f"  Restore path : {restore_path}")
    print(f"  Files        : {len(save_files)} file(s) from Drive")
    if drive_ts:
        print(f"  Backup date  : {fmt_ts(drive_ts)}")
    print()

    if not confirm("Proceed with restore?"):
        print("\n  Cancelled. Nothing was changed.")
        pause()
        return

    # --- Safe snapshot of current local saves first ---
    local_save_path = Path(restore_path)
    if local_save_path.exists():
        existing_files = [f for f in local_save_path.rglob("*") if f.is_file()]
        if existing_files:
            ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            snap_dir = BASE_DIR / "restore_snapshots"
            snap_dir.mkdir(exist_ok=True)
            safe_name = folder_name.replace(" ", "_")
            snapshot  = snap_dir / f"{safe_name}_before_restore_{ts}.7z"
            print(f"\n  Snapshotting current saves -> {snapshot.name}...")
            with py7zr.SevenZipFile(snapshot, "w") as zf:
                for f in existing_files:
                    zf.write(f, arcname=f.name)
            log.info(f"Safe restore snapshot: {snapshot}")

    # --- Download files from Drive ---
    print(f"\n  → Downloading {len(save_files)} file(s) from Drive")
    errors = []
    total_dl = len(save_files)
    for i, f in enumerate(save_files):
        pct = int(100 * (i / max(total_dl, 1)))
        progress(pct, f"Downloading {f['name']}")
        try:
            dest = local_save_path / f["name"]
            download_file_from_drive(service, f["id"], dest)
        except Exception as e:
            errors.append(f["name"])
            print(f"  ✗ Error downloading {f['name']}: {e}")
            log.error(f"Restore error [{f['name']}]: {e}")
    if not errors:
        progress(100, "Download complete.")

    # --- Auto-import into local config if not already there ---
    if not matched_local and drive_config:
        drive_config["save_path"] = restore_path  # use the confirmed local path
        local_cfg["games"].append(drive_config)
        save_config(local_cfg)
        print(f"\n  '{folder_name}' added to your local SaveSync config.")
        if drive_config.get("exe_path"):
            write_launcher(drive_config)

    print()
    if errors:
        print(f"  Restore finished with {len(errors)} error(s): {', '.join(errors)}")
        print("  Check savesync.log for details.")
    else:
        print(f"  Restore complete. {len(save_files)} file(s) written to:")
        print(f"  {restore_path}")

    log.info(f"Restore complete: {folder_name} -> {restore_path}")
    print()
    pause()


# ---------------------------------------------------------------

def screen_create_launcher():
    header("Create Launcher")
    cfg   = load_config()
    games = cfg.get("games", [])

    if not games:
        print("  No games configured.")
        print("  Go back and choose option 1 to add a game first.")
        print()
        pause()
        return

    # Only show games that have a launch path set
    eligible = [g for g in games if g.get("exe_path")]
    no_path  = [g for g in games if not g.get("exe_path")]

    if no_path:
        print(f"  Note: {len(no_path)} game(s) have no launch path set and are not listed.")
        print(f"  To fix this, remove and re-add the game, or edit savesync_config.json.")
        print()

    if not eligible:
        print("  No games have a launch path configured.")
        print("  A launch path is required to create a launcher.")
        print()
        pause()
        return

    names = [g["name"] for g in eligible]
    idx   = pick("Which game do you want to create a launcher for?", names)
    if idx is None:
        return

    game    = eligible[idx]
    bat     = BASE_DIR / f"Launch {game['name']}.bat"

    print()
    if bat.exists():
        print(f"  A launcher already exists: {bat.name}")
        print()
        if not confirm("Overwrite it?"):
            print("\n  Cancelled.")
            pause()
            return

    print()
    print(f"  Game        : {game['name']}")
    print(f"  Launches    : {game['exe_path']}")
    print(f"  Output file : {bat.name}")
    print()

    write_launcher(game)
    print(f"  ✓ Launcher created: {bat}")
    print()
    print("  You can move or copy this file anywhere — your desktop,")
    print("  a launcher app, or pin it to your taskbar.")
    print()
    pause()


# ---------------------------------------------------------------

def screen_install_startup(mode=None):
    header("Install Watcher as Windows Startup Task")

    import platform
    if platform.system() != "Windows":
        print("  This option is only available on Windows.")
        print()
        pause()
        return

    import shutil
    import subprocess

    py_path     = Path(sys.executable)
    pythonw     = py_path.parent / "pythonw.exe"
    script_path = Path(__file__).resolve()
    task_name   = "SaveSyncWatcher"

    print("  This will register SaveSync as a Windows Task Scheduler task.")
    print("  The watcher will start automatically every time Windows boots,")
    print("  running silently in the background with no terminal window.")
    print()
    print(f"  Script  : {script_path}")
    print(f"  Runtime : {pythonw}")
    print()

    if not pythonw.exists():
        print("  Warning: pythonw.exe not found next to your Python installation.")
        print(f"  Expected at: {pythonw}")
        print()
        print("  Falling back to python.exe — a terminal window will be")
        print("  briefly visible at startup. To fix this, reinstall Python")
        print("  and make sure the 'tcl/tk and IDLE' component is included.")
        print()
        pythonw = py_path

    # Check if task already exists
    check = subprocess.run(
        ["schtasks", "/query", "/tn", task_name],
        capture_output=True
    )
    already_exists = check.returncode == 0

    # If called from watcher submenu with explicit mode, skip the menu
    if mode == "remove":
        if not already_exists:
            print("  No startup task is currently installed.")
            print()
            pause()
            return
        if confirm("Remove the SaveSync startup task?"):
            result = subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print("\n  ✓ Startup task removed.")
                print("  SaveSync will no longer start automatically with Windows.")
            else:
                print(f"\n  ✗ Failed to remove: {result.stderr.strip()}")
        else:
            print("\n  Cancelled.")
        print()
        pause()
        return

    if already_exists:
        print("  A startup task named 'SaveSyncWatcher' is already installed.")
        print("  This will update it with the current file paths.")
        print()
        if not confirm("Update the existing task?"):
            print("\n  Cancelled.")
            pause()
            return
        subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], capture_output=True)

    if not confirm("Install startup task?"):
        print("\n  Cancelled.")
        pause()
        return

    # Build the schtasks command
    # /sc ONLOGON  — runs when any user logs in (more reliable than ONSTART for pythonw)
    # /rl HIGHEST  — run with elevated privileges so file access works
    # /f           — force create (overwrite if exists)
    cmd = [
        "schtasks", "/create",
        "/tn",  task_name,
        "/tr",  f'"{pythonw}" "{script_path}" --watch',
        "/sc",  "ONLOGON",
        "/rl",  "HIGHEST",
        "/f",
    ]

    print()
    print("  Registering task... (a UAC prompt may appear)")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("  ✓ Startup task installed successfully.")
        print()
        print("  The watcher will now start automatically every time")
        print("  you log into Windows. To start it right now without")
        print("  rebooting, go to Main Menu → option 5.")
        print()
        print("  To remove it later, come back to this option and choose Remove.")
    else:
        print(f"  ✗ Failed to install task.")
        print()
        err = result.stderr.strip() or result.stdout.strip()
        if err:
            print(f"  Error: {err}")
        print()
        print("  Try running SaveSync as Administrator:")
        print("  Right-click SaveSync.bat → Run as administrator")

    print()
    pause()


# ---------------------------------------------------------------

def screen_integrity_check():
    header("Health Check")
    cfg   = load_config()
    games = cfg.get("games", [])

    if not games:
        print("  No games configured yet.")
        print("  Go to the main menu and add a game first.")
        print()
        pause()
        return

    print("  Scans each registered game and checks that SaveSync can")
    print("  still find the save files locally and on Google Drive.")
    print("  Run this occasionally to make sure everything is still")
    print("  pointing to the right place.")
    print()
    print("    1.  Check all games")
    print("    2.  Check a specific game")
    print("    0.  Back")
    print()
    choice = input("  > ").strip()

    if choice == "0":
        return
    elif choice == "2":
        names = [g["name"] for g in games]
        idx   = pick("Which game?", names)
        if idx is None:
            return
        games_to_check = [games[idx]]
    elif choice == "1":
        games_to_check = games
    else:
        print("  Invalid option.")
        pause()
        return

    # Connect to Drive once if any game uses it
    drive_service = None
    any_uses_drive = any(g.get("drive_folder") for g in games_to_check)
    if any_uses_drive and GDRIVE_AVAILABLE:
        print()
        print("  Connecting to Google Drive...")
        try:
            drive_service = get_drive_service()
        except Exception as e:
            print(f"  Could not connect to Drive: {e}")
            print("  Drive checks will be skipped.")

    print()
    hr()

    all_ok = True

    for game in games_to_check:
        name = game["name"]
        print(f"  {name}")
        hr("·")

        # ── Local check ──────────────────────────────────────────
        local_path = Path(game.get("save_path", ""))
        print("  Local saves")

        if not game.get("save_path"):
            print("    ✗  No save path configured.")
            all_ok = False
        elif not local_path.exists():
            print(f"    ✗  Path not found: {local_path}")
            print("       The folder may have moved, or the game has never been launched yet.")
            all_ok = False
        else:
            files = [f for f in local_path.rglob("*") if f.is_file()] if local_path.is_dir() else [local_path]
            if not files:
                print(f"    ⚠  Folder exists but is empty: {local_path}")
                print("       The game may not have created save files yet.")
                all_ok = False
            else:
                total_kb = sum(f.stat().st_size for f in files) // 1024
                print(f"    ✓  Found {len(files)} file(s)  ({total_kb} KB)")
                print(f"       Path: {local_path}")

        # ── Google Drive check ────────────────────────────────────
        if game.get("drive_folder"):
            print("  Google Drive")
            if not GDRIVE_AVAILABLE:
                print("    ✗  Google API libraries not installed.")
                all_ok = False
            elif drive_service is None:
                print("    ✗  Could not connect to Drive (see error above).")
                all_ok = False
            else:
                try:
                    # Navigate to the folder without creating it
                    parts     = [p for p in game["drive_folder"].replace("\\", "/").split("/") if p]
                    parent_id = "root"
                    folder_found = True
                    for part in parts:
                        q   = (f"name=\'{part}\' and mimeType=\'application/vnd.google-apps.folder\' "
                               f"and \'{parent_id}\' in parents and trashed=false")
                        res = drive_service.files().list(q=q, fields="files(id)").execute()
                        hits = res.get("files", [])
                        if not hits:
                            folder_found = False
                            break
                        parent_id = hits[0]["id"]

                    if not folder_found:
                        print(f"    ⚠  Folder not found on Drive: {game['drive_folder']}")
                        print("       No backup has been made yet, or the folder was deleted.")
                        all_ok = False
                    else:
                        # Count non-config files in the folder
                        q2    = (f"\'{parent_id}\' in parents and trashed=false "
                                 f"and name != \'_savesync_game_config.json\' "
                                 f"and mimeType != \'application/vnd.google-apps.folder\'")
                        res2  = drive_service.files().list(q=q2, fields="files(id,name,size,modifiedTime)").execute()
                        drive_files = res2.get("files", [])
                        if not drive_files:
                            print(f"    ⚠  Folder exists on Drive but is empty: {game['drive_folder']}")
                            print("       A backup has not been completed yet.")
                            all_ok = False
                        else:
                            latest = max(drive_files, key=lambda f: f.get("modifiedTime", ""))
                            total_kb = sum(int(f.get("size", 0)) for f in drive_files) // 1024
                            print(f"    ✓  Found {len(drive_files)} file(s)  ({total_kb} KB)")
                            print(f"       Last backup: {latest['modifiedTime'][:10]}")
                            print(f"       Drive path : {game['drive_folder']}")
                except Exception as e:
                    print(f"    ✗  Error reading Drive: {e}")
                    all_ok = False
        else:
            print("  Google Drive")
            print("    –  Not configured for this game.")

        # ── .7z archive check ─────────────────────────────────────
        if game.get("archive_path"):
            print("  Local .7z archive")
            archive_dir  = Path(game["archive_path"]).parent
            archive_stem = Path(game["archive_path"]).stem
            if not archive_dir.exists():
                print(f"    ✗  Archive folder not found: {archive_dir}")
                all_ok = False
            else:
                snaps = sorted(archive_dir.glob(archive_stem + "_*.7z"))
                if not snaps:
                    print(f"    ⚠  No snapshots found in: {archive_dir}")
                    print("       A backup has not been completed yet.")
                    all_ok = False
                else:
                    latest_snap = snaps[-1]
                    print(f"    ✓  {len(snaps)} snapshot(s) found")
                    print(f"       Latest: {latest_snap.name}")

        print()

    hr()
    if all_ok:
        print("  All checks passed.")
    else:
        print("  One or more issues were found — review the details above.")
        print("  Check savesync.log for additional error information.")
    print()
    pause()


# ---------------------------------------------------------------

def screen_game_database():
    header("Game Database")

    index_count = 0
    if MANIFEST_INDEX.exists():
        try:
            idx = json.loads(MANIFEST_INDEX.read_text(encoding="utf-8"))
            index_count = len(idx)
        except Exception:
            pass

    age = manifest_db_age()

    print("  Ludusavi community database")
    print("  Covers tens of thousands of PC games with known save locations.")
    print()
    if MANIFEST_INDEX.exists():
        print(f"  Status  : Downloaded and indexed")
        print(f"  Games   : {index_count:,}")
        print(f"  Age     : {age}")
    else:
        print("  Status  : Not downloaded yet")
    print()
    hr("·")
    print()
    print("    1.  Download / update database")
    print("    2.  Search database manually")
    print("    0.  Back")
    print()
    choice = input("  > ").strip()

    if choice == "1":
        print()
        ok = download_manifest(silent=False)
        if ok:
            print()
            build_manifest_index(silent=False)
            print()
            print("  Database is ready.")
        print()
        pause()

    elif choice == "2":
        print()
        query = ask("Game name to search")
        if not query:
            return
        if not ensure_manifest_ready():
            pause()
            return
        print()
        results = search_manifest(query)
        if not results:
            print(f"  No results found for '{query}'.")
            # Also check personal list
            manual = lookup_save_location(query)
            if manual:
                print(f"  Found in your personal list: {manual}")
        else:
            print(f"  Results for '{query}':\n")
            for gname, paths in results:
                print(f"  {gname}")
                for p in paths:
                    has_wildcard = "*" in p
                    note = "  [contains wildcard — check in Explorer]" if has_wildcard else ""
                    print(f"    → {p}{note}")
                print()
        pause()


# ---------------------------------------------------------------

def screen_settings():
    while True:
        header("Settings")
        print("    1.  Google Drive setup")
        print("        Connect SaveSync to your Google account.")
        print()
        print("    2.  Game database")
        print("        Download and search the Ludusavi save location database.")
        print("        Contains tens of thousands of known game save paths.")
        print()
        print("    3.  Create game launcher")
        print("        Generate a shortcut file for a game that backs up")
        print("        your saves on open and close automatically.")
        print()
        print("    0.  Back")
        print()
        choice = input("  > ").strip()
        if choice == "1":
            screen_drive_setup()
        elif choice == "2":
            screen_game_database()
        elif choice == "3":
            screen_create_launcher()
        elif choice == "0":
            return
        else:
            print("\n  Invalid option.")
            time.sleep(1)

# ---------------------------------------------------------------
# CLI fallback — used by .bat launchers silently
# ---------------------------------------------------------------

def cli_backup(name: str):
    cfg = load_config()
    matches = [g for g in cfg["games"] if g["name"].lower() == name.lower()]
    if not matches:
        print(f"Game '{name}' not found in config.")
        sys.exit(1)
    ok = run_backup(matches[0], reason="launcher", silent=True)
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--backup":
        cli_backup(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == "--watch":
        cfg = load_config()
        games = cfg.get("games", [])
        watcher = GameWatcher(games)
        watcher.start()
        print("SaveSync watcher running. Press Ctrl+C to stop.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
    else:
        resize_terminal()
        screen_main()
