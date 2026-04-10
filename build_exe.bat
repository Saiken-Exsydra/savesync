@echo off
:: SaveSync — Build standalone .exe with PyInstaller
:: Run this once to produce dist\SaveSync\SaveSync.exe
::
:: Requirements:
::   pip install pyinstaller
::
echo ============================================
echo  SaveSync EXE Builder
echo ============================================
echo.

cd /d "%~dp0"

:: Check PyInstaller is available
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    echo.
)

echo Building SaveSync.exe ...
echo.

pyinstaller ^
    --noconfirm ^
    --windowed ^
    --name "SaveSync" ^
    --icon "icon.ico" ^
    --add-data "savesync.py;." ^
    --add-data "savesync_config.json;." ^
    --hidden-import "customtkinter" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "requests" ^
    --hidden-import "google.auth" ^
    --hidden-import "google.oauth2" ^
    --hidden-import "googleapiclient" ^
    --hidden-import "py7zr" ^
    --hidden-import "psutil" ^
    --hidden-import "schedule" ^
    --collect-all "customtkinter" ^
    savesync_gui.py

if %errorlevel% neq 0 (
    echo.
    echo === Build FAILED. See errors above. ===
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Executable: dist\SaveSync\SaveSync.exe
echo ============================================
echo.
echo NOTE: On first run, copy these files next to SaveSync.exe if they exist:
echo   - savesync_config.json   (your game list)
echo   - thumbnail_cache\       (cached cover art)
echo   - token.json             (Google Drive auth token)
echo   - credentials.json       (Google Drive credentials)
echo.
pause
