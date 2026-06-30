@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3.12"
) else (
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.12 or newer was not found.
    exit /b 1
)

%PYTHON_CMD% -m venv .venv
if errorlevel 1 exit /b 1

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist data mkdir data
if not exist data\uploads mkdir data\uploads
if not exist data\training mkdir data\training
if not exist data\features mkdir data\features
if not exist data\models mkdir data\models
if not exist data\outputs mkdir data\outputs
if not exist data\previews mkdir data\previews
if not exist data\thumbnails mkdir data\thumbnails
if not exist data\logs mkdir data\logs
if not exist data\temp mkdir data\temp

python -m app.db.init_db
if errorlevel 1 exit /b 1

python -m app.db.migrate
if errorlevel 1 exit /b 1

echo Setup completed.
endlocal
