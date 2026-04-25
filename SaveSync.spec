# -*- mode: python ; coding: utf-8 -*-
# SaveSync — PyInstaller spec file
import os
from PyInstaller.utils.hooks import collect_all

# ── Data files ────────────────────────────────────────────────────────────────
datas = [
    ('assets', 'assets'),   # SVG icons used at runtime by QSvgRenderer
]
if os.path.exists('gdrive_credentials.json'):
    datas += [('gdrive_credentials.json', '.')]
else:
    print("WARNING: gdrive_credentials.json not found — Google Drive auth will be unavailable.")

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # GUI
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
    # PIL / Pillow
    'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageDraw',
    'PIL.ImageFont', 'PIL.ImageQt',
    # System tray
    'pystray',
    # Networking
    'requests', 'charset_normalizer',
    # Google Drive
    'google.auth',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.http',
    # Archive support
    'py7zr',
    # System / utilities
    'psutil', 'schedule', 'yaml',
    # Windows toast notifications (optional, lazy-imported)
    'win11toast',
    'winrt.windows.ui.notifications',
    'winrt.windows.data.xml.dom',
    'winrt.windows.foundation',
]

# ── Collect packages that ship data files ─────────────────────────────────────
binaries = []
for pkg in ('PyQt6', 'pystray'):
    d, b, h = collect_all(pkg)
    datas         += d
    binaries      += b
    hiddenimports += h

# ── Icon ──────────────────────────────────────────────────────────────────────
icon = 'savesync.ico' if os.path.exists('savesync.ico') else None

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['savesync_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tkinter.test', 'lib2to3', 'pydoc', 'doctest',
        'xmlrpc', 'ftplib', 'imaplib', 'nntplib', 'poplib', 'smtplib', 'telnetlib',
        'customtkinter',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, optimize=1)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SaveSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SaveSync',
)
