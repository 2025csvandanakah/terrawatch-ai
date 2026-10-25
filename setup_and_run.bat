@echo off
setlocal
title TerraWatch AI - First Setup
cd /d "%~dp0"
echo ============================================
echo       TerraWatch AI - First Setup
echo ============================================
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON_LAUNCHER=py") else (set "PYTHON_LAUNCHER=python")
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  %PYTHON_LAUNCHER% -m venv .venv
  if errorlevel 1 goto error
)
echo Installing requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Setup finished. Open http://127.0.0.1:8000 in a browser.
echo Keep this window open. This server does not use --reload.
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
if errorlevel 1 (echo Server stopped or could not start. See the error above.& pause)
goto end
:error
echo Setup failed. Check Python installation and internet access.
pause
:end
endlocal
