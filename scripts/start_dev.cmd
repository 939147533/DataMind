@echo off
rem ============================================================
rem  DataMind dev startup script (cmd version)
rem    Backend FastAPI (uvicorn)  http://127.0.0.1:8000
rem    Frontend Vite              http://127.0.0.1:<Port> (default 5174)
rem  Usage:
rem    scripts\start_dev.cmd [port]
rem    scripts\start_dev.cmd 5175
rem ============================================================
setlocal

set "PORT=%~1"
if "%PORT%"=="" set "PORT=5174"

set "Root=%~dp0.."
cd /d "%Root%"

set "Py=%Root%\backend\.venv\Scripts\python.exe"
set "BackendLog=%Root%\backend\uvicorn.dev.log"

rem ---- [1/4] backend venv ----
if exist "%Py%" (
    echo [1/4] backend venv ready
) else (
    echo [1/4] creating backend venv and installing dependencies...
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] python not found. Install Python 3.11+ and add it to PATH.
        exit /b 1
    )
    python -m venv "%Root%\backend\.venv"
    if errorlevel 1 exit /b 1
    "%Py%" -m pip install --upgrade pip
    if errorlevel 1 exit /b 1
    "%Py%" -m pip install -r "%Root%\backend\requirements.txt"
    if errorlevel 1 exit /b 1
)

rem ---- [2/4] frontend deps ----
if exist "%Root%\frontend\node_modules" (
    echo [2/4] frontend deps ready
) else (
    echo [2/4] installing frontend deps via npm ci...
    pushd "%Root%\frontend"
    call npm.cmd ci
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

rem ---- [3/4] backend ----
netstat -ano | findstr /C:":8000" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [3/4] port 8000 in use, skip backend start - maybe already running
) else (
    echo [3/4] starting backend uvicorn  http://127.0.0.1:8000
    pushd "%Root%\backend"
    start "" /b "%Py%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 1>>"%BackendLog%" 2>>"%BackendLog%.err"
    popd
)

rem ---- [4/4] frontend ----
echo [4/4] starting frontend Vite  http://127.0.0.1:%PORT%  - Ctrl+C stops frontend, backend keeps running
pushd "%Root%\frontend"
call npm.cmd run dev -- --port %PORT% --strictPort --host 127.0.0.1
set "FRONTEND_ERR=%errorlevel%"
popd
exit /b %FRONTEND_ERR%
