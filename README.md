# SaveSync

**Indie game save file backup manager for Windows.**

Automatically backs up your save files to Google Drive and local archives whenever you open or close a game — with a clean terminal interface, Windows 11 notifications, and a database of tens of thousands of known save locations powered by the [Ludusavi community manifest](https://github.com/mtkennerly/ludusavi-manifest).

---

## Features

- **Automatic backups** — detects when a game opens or closes and backs up silently in the background
- **Google Drive sync** — uploads saves to a dedicated Drive folder, accessible from any machine
- **Local .7z archives** — timestamped snapshots with automatic rotation so you never run out of space
- **Ludusavi database** — search tens of thousands of games to find save locations automatically
- **Personal save locations list** — add your own entries that take priority over the database
- **Smart restore** — compares backup timestamps before restoring, warns if local saves are newer than Drive
- **Safe restore** — always snapshots your current saves before overwriting anything
- **Windows 11 notifications** — toast alerts when saves are backed up or if something goes wrong
- **Startup watcher** — installs as a Windows Task Scheduler task so it runs silently at every login
- **Launcher files** — generates a `.bat` per game that backs up before launch and after close
- **Integrity check** — scans local paths and Google Drive to confirm saves are where they should be
- **Terminal UI** — clean numbered menus, no GUI required

---

## Requirements

- Windows 10 or 11
- Python 3.10 or newer — [python.org](https://www.python.org/downloads/)

---

## Installation

**1. Download SaveSync**

Clone the repository or download the ZIP from the releases page and extract it anywhere you like.

```bash
git clone https://github.com/YourUsername/SaveSync.git
```

**2. Install dependencies**

Open a terminal in the SaveSync folder and run:

```bash
pip install py7zr schedule psutil pyyaml google-auth google-auth-oauthlib google-api-python-client win11toast
```

**3. Run SaveSync**

Double-click `SaveSync.bat` or run:

```bash
python savesync.py
```

---

## Google Drive Setup (optional)

Only needed if you want Drive backups. Local `.7z` archives work without any account.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Create a project
3. **APIs & Services** → Enable **Google Drive API**
4. **Credentials** → Create → **OAuth 2.0 Client ID** → Desktop App
5. Download the JSON file and save it as `gdrive_credentials.json` in the SaveSync folder
6. Open SaveSync → option **6. Google Drive setup** — a browser window will open to authenticate

---

## Usage

Run SaveSync and navigate with numbers:

```
  Main Menu

    1.  Add a game
    2.  List games
    3.  Remove a game
    4.  Backup a game now
    5.  Start background watcher
    6.  Google Drive setup
    7.  Restore saves from Drive
    8.  Create launcher for a game
    9.  Install watcher as Windows startup task
   10.  Integrity check
   11.  Game database

    0.  Exit
```

### Adding a game

When you add a game, SaveSync automatically searches the Ludusavi database for the game's known save location. If found, it suggests the path. You can accept it, pick from multiple options, or enter your own. After confirming, you can save the path to your personal list for future use.

### Auto-backup on game launch and close

Each game can have a process name (e.g. `hollow_knight.exe`) which the background watcher monitors. When the process appears, SaveSync backs up before play. When it disappears, it backs up again.

Use option **9** to install the watcher as a Windows startup task so it runs silently every time you log into Windows with no terminal window visible.

### Launcher files

Option **8** generates a `Launch GameName.bat` file for any game. Double-clicking it backs up your saves, launches the game, then backs up again when the game closes. Works with `.exe`, `.bat`, and other file types.

### Restoring from Drive

Option **7** lists all games backed up in your Google Drive `SaveSync/` folder. Before restoring, it compares timestamps. If your local saves are newer than the Drive backup, it warns you and offers to back up to Drive instead. A `.7z` snapshot of your current saves is always created before any restore.

---

## File structure

```
SaveSync/
├── savesync.py              # Main script
├── SaveSync.bat             # Double-click to open
├── save_locations.txt       # Your personal save path overrides
├── .gitignore
├── README.md
│
│   The following are generated automatically and not included in the repo:
├── savesync_config.json     # Your game list and settings
├── gdrive_credentials.json  # Google OAuth credentials (keep private)
├── gdrive_token.json        # Google auth token (keep private)
├── ludusavi_manifest.yaml   # Ludusavi database (downloaded on first use)
├── ludusavi_index.json      # Search index built from manifest
├── savesync.log             # Activity log
└── restore_snapshots/       # Safe snapshots created before restores
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
