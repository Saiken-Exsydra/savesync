# SaveSync

**Game save file backup manager for Windows — with a modern GUI, Google Drive sync, and automatic background protection.**

SaveSync watches your games, detects when they open or close, and silently backs up your save files to Google Drive and local `.7z` archives. It comes with a dark-themed GUI built on CustomTkinter, minimizes to the system tray, and starts with Windows so your saves are always protected. A built-in database powered by the [Ludusavi community manifest](https://github.com/mtkennerly/ludusavi-manifest) covers tens of thousands of known save locations.

---

## Features

### Backup & Sync

- **Automatic backups** — detects when a game opens or closes and backs up silently in the background.
- **Google Drive sync** — uploads saves to a dedicated Drive folder per game, accessible from any machine.
- **Local .7z archives** — timestamped snapshots with configurable rotation so you never run out of space.
- **Bidirectional sync** — per-game Sync button compares local and Drive timestamps. If local is newer, it pushes to Drive. If Drive is newer, it pulls and overwrites locally. Existing saves are always snapshot before being overwritten.
- **Safe restores** — before any restore or sync that overwrites local files, a `.7z` snapshot is created in an organized per-game subfolder under `restore_snapshots/`.

### GUI

- **Modern dark-themed interface** — two-panel layout with sidebar navigation (Games, Restore, Watcher, Settings).
- **Game cards** — each game shows its backup destinations, last backup time, save path, and watcher triggers, with Sync, Backup, Edit, and Remove buttons.
- **Add Game wizard** — 6-step guided flow: name → save path (with database search) → launcher exe → backup destinations → trigger settings → review and confirm. After adding, a status window verifies the executable exists, checks the save path, and restarts the watcher automatically.
- **Edit Game dialog** — modify any field of an existing game (name, save path, exe, Drive folder, archive path, triggers). Changes are saved locally and the updated config is automatically uploaded to the game's Drive folder.
- **Backup dialog** — per-game dialog showing current Drive status, local snapshot count, and save file count. Choose to backup to Drive, create a local `.7z` snapshot, or both.
- **Add from Drive** — lists all games on your Drive. Games not in the local list get an Add button, and an "Add All Missing" button lets you batch-restore everything at once.
- **System tray** — closing the window minimizes to the tray instead of quitting. Double-click the tray icon to reopen. Right-click for Show/Quit.
- **Health Check** — scans all games and verifies save paths exist, Drive folders are populated, and files are accounted for.

### Background Protection

- **Background watcher** — monitors registered game processes. Automatically backs up on launch, on close, and/or at configurable intervals.
- **Watcher auto-restart** — adding, editing, or removing a game automatically stops and restarts the watcher with the updated game list.
- **Start with Windows** — installs a `.vbs` launcher in the Windows Startup folder. SaveSync starts minimized in the system tray with the watcher running — no visible window.
- **Startup health check** — when starting with Windows, SaveSync runs a background integrity check across all games, comparing local and Drive timestamps and verifying save paths. A Windows notification reports the result: either "fully synchronized" or a list of games with issues.
- **Windows notifications** — toast alerts via win11toast when saves are backed up, when issues are found, or when the startup health check completes.

### Database & Search

- **Ludusavi database** — tens of thousands of PC game save locations, downloaded from GitHub and indexed locally.
- **Smart download dialog** — checks if the database exists, whether an update is available, and walks through download and indexing step by step.
- **Search** — look up any game's save location in the database directly from Settings.
- **Personal save locations** — `save_locations.txt` lets you define your own paths that override the database.

### Terminal Interface

- **TUI still available** — `savesync.py` runs independently as a full terminal interface with numbered menus for all operations. The GUI is an optional frontend that imports from it.

---

## Requirements

- Windows 10 or 11
- Python 3.10 or newer — [python.org](https://www.python.org/downloads/)

---

## Installation

**1. Download SaveSync**

Clone the repository or download the ZIP and extract it anywhere.

```bash
git clone https://github.com/YourUsername/SaveSync.git
```

**2. Install dependencies**

Open a terminal in the SaveSync folder and run:

```bash
pip install py7zr schedule psutil pyyaml google-auth google-auth-oauthlib google-api-python-client win11toast customtkinter pystray Pillow
```

**3. Run SaveSync**

For the GUI (recommended):

```bash
SaveSyncGUI.bat
```

Or directly:

```bash
pythonw savesync_gui.py
```

For the terminal interface:

```bash
python savesync.py
```

---

## Google Drive Setup (optional)

Only needed if you want cloud backups. Local `.7z` archives work without any account.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/).
2. Create a project.
3. **APIs & Services** → Enable **Google Drive API**.
4. **Credentials** → Create → **OAuth 2.0 Client ID** → Desktop App.
5. Download the JSON file and save it as `gdrive_credentials.json` in the SaveSync folder.
6. Open SaveSync → Settings → **Connect / Authenticate** — a browser window will open for sign-in.

---

## Usage

### Adding a game

Click **+ Add Game** in the Games panel. The 6-step wizard walks you through:

1. **Game name** — type the name of your game.
2. **Save path** — SaveSync searches the Ludusavi database automatically. If it finds a match, click the suggested path. Otherwise, browse manually.
3. **Launcher** — point to the `.exe` that launches the game. This enables the watcher to detect when the game runs. Optional.
4. **Destinations** — choose where backups go: Google Drive folder, local `.7z` archive path, local folder copy, or any combination.
5. **Triggers** — configure when to backup: on game launch, on close, at a time interval, and how many snapshots to keep.
6. **Confirm** — review everything and save.

After saving, a status window shows you what happened: config saved, executable found (or not), save path verified, and watcher restarted with the new game included.

### Syncing a game

Each game card with a Drive folder has a **Sync** button. It compares the local `backup_timestamp` against the Drive timestamp:

- If local is newer → automatically uploads to Drive.
- If Drive is newer → snapshots your local saves first, then downloads from Drive.
- If timestamps match → tells you everything is already in sync.

### Editing a game

Click **Edit** on any game card to change its name, save path, exe, Drive folder, archive path, or trigger settings. When you save, the watcher restarts automatically and the updated config is uploaded to the game's Drive folder.

### Adding games from Drive

Click **Add from Drive** in the Games panel header. SaveSync lists every game folder on your Drive, showing which ones are already in your local list. You can add games individually or click **Add All Missing** to batch-add everything at once.

### Backup dialog

Click **Backup** on a game card to see the current status (Drive file count, local snapshots, save file count) and choose: backup to Drive, create a local `.7z` snapshot, or both.

### Watcher

The Watcher panel lets you start and stop the background process monitor. When running, it watches for registered game executables and triggers backups according to each game's settings.

Use **Add to Startup** to install SaveSync in the Windows Startup folder. It will start minimized in the system tray every time you log in, with the watcher running and a health check that sends a notification when done.

### Restore from Drive

The Restore panel lists all game folders on Drive and lets you download saves to a local path. Before overwriting anything, a `.7z` snapshot is created. If the game isn't in your local list, it's added automatically.

---

## File Structure

```
SaveSync/
├── savesync.py              # Core logic (TUI + all backup/restore functions)
├── savesync_gui.py          # GUI frontend (imports from savesync.py)
├── SaveSync.bat             # Launches the terminal interface
├── SaveSyncGUI.bat          # Launches the GUI with admin elevation
├── save_locations.txt       # Personal save path overrides
├── .gitignore
├── README.md
│
│   Generated automatically (not in the repo):
├── savesync_config.json     # Your game list and settings
├── gdrive_credentials.json  # Google OAuth credentials (keep private)
├── gdrive_token.json        # Google auth token (keep private)
├── ludusavi_manifest.yaml   # Ludusavi database (downloaded on first use)
├── ludusavi_index.json      # Search index built from manifest
├── ludusavi_meta.json       # Database metadata (version, update status)
├── savesync.log             # Activity log
├── restore_snapshots/       # Pre-restore/sync snapshots, organized per game
│   ├── Game_Name/
│   │   ├── before_restore_20260407_143000.7z
│   │   └── before_sync_20260407_150000.7z
│   └── Another_Game/
│       └── ...
└── Launch GameName.bat      # Auto-generated launcher per game
```

---

## save_locations.txt format

One game per line, name and path separated by a comma:

```
Hollow Knight, C:/Users/YourName/AppData/LocalLow/Team Cherry/Hollow Knight
Celeste, C:/Users/YourName/AppData/Local/Celeste/Saves
Stardew Valley, C:/Users/YourName/AppData/Roaming/StardewValley/Saves
```

Entries here take priority over the Ludusavi database.

---

## Credits

Save location data provided by the [Ludusavi manifest](https://github.com/mtkennerly/ludusavi-manifest) — a community-maintained database of PC game save locations built from PCGamingWiki and the Steam API. Thank you to [mtkennerly](https://github.com/mtkennerly) and all contributors.

---

## License

MIT License — free to use, modify, and share.
