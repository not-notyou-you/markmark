@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Python 3.10+ is required: https://www.python.org/downloads/
    pause
    exit /b 1
  )
  .venv\Scripts\python -m pip install --quiet .
)
.venv\Scripts\python -m markmark
pause
