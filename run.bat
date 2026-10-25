@echo off
setlocal
title TerraWatch AI
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Virtual environment missing. Double-click setup_and_run.bat first.
 pause
 exit /b 1
)
echo Open http://127.0.0.1:8000 and keep this window open.
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
endlocal
