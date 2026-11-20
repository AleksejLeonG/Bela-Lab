@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Bela Lab\Bela Lab.exe" (
    start "" "%LOCALAPPDATA%\Programs\Bela Lab\Bela Lab.exe" %*
    exit /b
)
if exist "app\.venv\Scripts\pythonw.exe" (
    start "" "app\.venv\Scripts\pythonw.exe" "app\desktop.py" %*
    exit /b
)
echo Build and install the desktop app using the instructions in docs/DESKTOP_APP.md.
pause
