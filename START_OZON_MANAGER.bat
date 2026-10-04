@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV=%~dp0.venv"
set "PYTHON="

where py.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYTHON=py -3"

if not defined PYTHON (
    where python.exe >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PYTHON=python"
)

if not defined PYTHON (
    echo.
    echo Ozon Manager: Python 3 was not found.
    echo.
    echo Install Python 3 from https://www.python.org/downloads/
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    echo [1/4] Creating local Python environment...
    %PYTHON% -m venv "%VENV%"
    if errorlevel 1 goto :error
)

set "VENV_PY=%VENV%\Scripts\python.exe"

"%VENV_PY%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing project dependencies...
    "%VENV_PY%" -m pip install --upgrade pip
    if errorlevel 1 goto :error
    "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 goto :error
)

echo [3/4] Preparing local data and logs...
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0logs" mkdir "%~dp0logs"


echo [4/4] Starting Ozon Manager...
start "Ozon Manager" /b "%VENV_PY%" -m streamlit run "%~dp0app\ui\streamlit_app.py" --server.headless true --browser.gatherUsageStats false --server.port 8501

rem Wait until Streamlit is actually serving the application before opening the browser.
rem A fixed sleep is not reliable on slower Windows machines and can open a blank page.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 60;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/' -TimeoutSec 1;if($r.StatusCode -eq 200){$ok=$true;break}}catch{};Start-Sleep -Milliseconds 500}; if(-not $ok){exit 1}"
if errorlevel 1 goto :error

start "" "http://127.0.0.1:8501/"
exit /b 0

:error
echo.
echo Ozon Manager could not be started.
echo Check the messages above for the reason.
echo.
pause
exit /b 1
