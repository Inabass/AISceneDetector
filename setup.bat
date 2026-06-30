@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo Python 3.12 or newer was not found.
    echo Install Python 3.12+ or ensure it is available through py or python.
    exit /b 1
)

%PYTHON_CMD% --version

%PYTHON_CMD% -m venv .venv
if errorlevel 1 exit /b 1

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

if "%AISD_SKIP_TORCH_INSTALL%"=="" (
    set "AISD_PYTORCH_INDEX_URL=%AISD_PYTORCH_INDEX_URL%"
    if "%AISD_PYTORCH_INDEX_URL%"=="" set "AISD_PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128"
    python -m pip install torch torchvision --index-url %AISD_PYTORCH_INDEX_URL%
    if errorlevel 1 exit /b 1
)

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
