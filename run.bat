@echo off
setlocal

cd /d "%~dp0"

if not exist .venv\Scripts\activate.bat (
    echo Virtual environment was not found. Run setup.bat first.
    exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

set "AISD_HOST=%AISD_HOST%"
if "%AISD_HOST%"=="" set "AISD_HOST=127.0.0.1"

set "AISD_PORT=%AISD_PORT%"
if "%AISD_PORT%"=="" set "AISD_PORT=8000"

python -m uvicorn app.main:app --host %AISD_HOST% --port %AISD_PORT%

endlocal
