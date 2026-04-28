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

# Bundle the Ludusavi manifest if present so first-run search works without
# requiring the user to download the database manually.
if os.path.exists('ludusavi_manifest.yaml'):
    datas += [('ludusavi_manifest.yaml', '.')]
if os.path.exists('ludusavi_index.json'):
    datas += [('ludusavi_index.json', '.')]

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # GUI
    'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets',
    # PIL / Pillow
    'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageDraw',
    'PIL.ImageFont', 'PIL.ImageQt',
    # Networking
    'requests', 'charset_normalizer',
    # Google Drive
    'google.auth',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.discovery_cache',
    'googleapiclient.http',
    # Archive support — py7zr pulls these C-backed deps that PyInstaller often misses.
    # NOTE: distribution names differ from import names here:
    #   pybcj         → import bcj
    #   pycryptodomex → import Cryptodome
    'py7zr',
    'multivolumefile',
    'pyppmd', 'pyppmd.c', 'pyppmd.c.c_ppmd',
    'bcj', 'bcj._bcj',
    'Cryptodome', 'Cryptodome.Cipher', 'Cryptodome.Cipher.AES',
    'Cryptodome.Util', 'Cryptodome.Random',
    'inflate64',
    'brotli', 'Brotli',
    'texttable',
    # System / utilities
    'psutil', 'schedule', 'yaml',
    # Windows toast notifications (optional, lazy-imported)
    'win11toast',
    'winrt.windows.ui.notifications',
    'winrt.windows.data.xml.dom',
    'winrt.windows.foundation',
]

# ── Collect packages that ship data files ─────────────────────────────────────
# - PyQt6: Qt plugins / DLLs
# - googleapiclient: bundled discovery_cache JSON files
# - py7zr + its native-backed deps: ensure all submodules + binaries are picked up
binaries = []
for pkg in ('PyQt6', 'googleapiclient', 'py7zr',
            'pyppmd', 'bcj', 'Cryptodome', 'inflate64',
            'brotli', 'multivolumefile'):
    try:
        d, b, h = collect_all(pkg)
    except Exception as _e:
        print(f"NOTE: collect_all({pkg!r}) failed: {_e}")
        continue
    datas         += d
    binaries      += b
    hiddenimports += h

# ── Icon ──────────────────────────────────────────────────────────────────────
icon = 'savesync.ico' if os.path.exists('savesync.ico') else None

# ── Windows version resource (CompanyName / FileVersion / Copyright / etc.) ──
# Edit version_info.txt to bump the version or change the developer name.
version_file = 'version_info.txt' if os.path.exists('version_info.txt') else None

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
    version=version_file,
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
