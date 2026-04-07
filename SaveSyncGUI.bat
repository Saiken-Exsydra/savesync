@echo off
:: Self-elevate to Administrator if not already running elevated
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
start "" pythonw savesync_gui.py
