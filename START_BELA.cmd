@echo off
setlocal
cd /d "%~dp0"
if exist "app\.venv\Scripts\python.exe" (
    "app\.venv\Scripts\python.exe" "app\run.py" %*
    goto :finished
)
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "app\run.py" %*
    goto :finished
)
python "app\run.py" %*
:finished
if errorlevel 1 pause
endlocal
