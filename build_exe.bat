@echo off
:: SaveSync — EXE Builder
::
:: Usage:
::   build_exe.bat           Normal build
::   build_exe.bat clean     Wipe dist\SaveSync before building
::
:: Requirements: pip install pyinstaller pyqt6 pillow cairosvg
::
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   SaveSync EXE Builder
echo ============================================================
echo.

:: ── Verify project root ───────────────────────────────────────
if not exist "savesync_gui.py" (
    echo ERROR: savesync_gui.py not found.
    echo        Run this script from the SaveSync project folder.
    echo.
    pause & exit /b 1
)

:: ── Python check ──────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo        Install Python 3.10+ and ensure it is on PATH.
    echo.
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
    echo Python %%v detected.
)

:: ── PyInstaller check / install ───────────────────────────────
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install PyInstaller.
        pause & exit /b 1
    )
    echo.
)
for /f "tokens=*" %%v in ('pyinstaller --version 2^>^&1') do (
    echo PyInstaller %%v ready.
)
echo.

:: ── Convert assets\savesync.svg → savesync.ico ───────────────
echo Converting SVG icon to ICO...
python _make_ico.py

echo.

:: ── Pre-build warnings ────────────────────────────────────────
if not exist "savesync.ico" (
    echo NOTE: savesync.ico not present — exe will use the default icon.
    echo.
)
if not exist "gdrive_credentials.json" (
    echo WARNING: gdrive_credentials.json not found.
    echo          Obtain it from Google Cloud Console and place it here.
    echo          Google Drive features will NOT work without it.
    echo.
)
:: ── Bake Ludusavi database into the build ────────────────────
:: Download manifest + build search index now so they get bundled
:: into the exe and the user has the DB available on first launch.
echo Preparing Ludusavi database for bundling...
python _bake_ludusavi_db.py
if %errorlevel% neq 0 (
    echo WARNING: Could not prepare Ludusavi database — build will continue
    echo          without bundling it. Users will need to download it manually.
    echo.
)
if not exist "ludusavi_manifest.yaml" (
    echo NOTE: ludusavi_manifest.yaml still missing — exe will not include the DB.
    echo.
) else (
    if exist "ludusavi_index.json" (
        echo Ludusavi DB ready ^(manifest + index will be bundled^).
    ) else (
        echo NOTE: ludusavi_index.json missing — only the raw manifest will be bundled.
    )
    echo.
)

:: ── Remove previous dist output ───────────────────────────────
if exist "dist\SaveSync" (
    echo Removing previous dist\SaveSync\ ...
    rmdir /s /q "dist\SaveSync" >nul 2>&1
    if exist "dist\SaveSync" (
        echo.
        echo ERROR: Could not delete dist\SaveSync\.
        echo        Close SaveSync.exe and any Explorer windows showing
        echo        that folder, then run the build again.
        echo.
        pause & exit /b 1
    )
    echo Done.
    echo.
)

:: ── Build ─────────────────────────────────────────────────────
echo Building ...  [started %time%]
echo.

pyinstaller --noconfirm --clean SaveSync.spec

if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo   BUILD FAILED — review the errors above.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo [finished %time%]

:: ── Copy runtime data files ───────────────────────────────────
echo.
echo Copying runtime data files into dist\SaveSync\ ...

set _COPIED=
set _SKIPPED=

if exist "thumbnail_cache\" (
    xcopy /E /I /Y "thumbnail_cache" "dist\SaveSync\thumbnail_cache\" >nul
    set "_COPIED=!_COPIED! thumbnail_cache\"
)

if defined _COPIED  echo   Copied: !_COPIED!

:: ── Done ──────────────────────────────────────────────────────
echo.
echo ============================================================
echo   Build complete!
echo   Executable:  dist\SaveSync\SaveSync.exe
echo ============================================================
echo.
echo savesync_config.json is NOT bundled — written next to
echo the exe on first run and stores your game list.
echo.
pause
