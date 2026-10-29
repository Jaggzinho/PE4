@echo off
setlocal

rem ============================================================================
rem PE3 QC Web Dev Launcher
rem - Starts backend (FastAPI) and frontend (Vite) in 2 separate terminals.
rem - Edit PE3_DB_PATH and PE3_JWT_SECRET before first run.
rem ============================================================================

for %%I in ("%~dp0.") do set "ROOT=%%~fI"

rem ---- Required configuration (EDIT THESE) -----------------------------------
rem You can also pass the DuckDB path as the first argument:
rem   run-dev.cmd C:\path\to\qc.duckdb
set "PE3_DB_PATH=%ROOT%\data\dev.duckdb"
set "PE3_JWT_SECRET=change-me-please-change-me-please-change"
set "PE3_DEV=1"
rem Required to use the first-run setup endpoint (/api/setup/*)
set "PE3_SETUP_TOKEN=dev-setup-token"

if not "%~1"=="" set "PE3_DB_PATH=%~1"

rem ---- Best-effort prerequisite checks ---------------------------------------
where python >nul 2>nul || (echo [ERROR] python not found in PATH.& exit /b 1)
where npm >nul 2>nul || (echo [ERROR] npm not found in PATH.& exit /b 1)

if exist "%PE3_DB_PATH%\NUL" (
  echo [ERROR] PE3_DB_PATH points to a directory, not a .duckdb file: "%PE3_DB_PATH%"
  echo         Pass a file path: run-dev.cmd C:\path\to\qc.duckdb
  exit /b 1
)
if not exist "%PE3_DB_PATH%" (
  echo [INFO] DuckDB will be created at: "%PE3_DB_PATH%"
)

echo.
echo Starting PE3 backend: http://127.0.0.1:8000
echo Starting PE3 frontend: http://127.0.0.1:5173
echo Setup token (for /setup): %PE3_SETUP_TOKEN%
echo.

start "PE3 Backend" cmd /k "cd /d ""%ROOT%"" & python -m pe3_qc_app_web"
start "PE3 Frontend" cmd /k "cd /d ""%ROOT%\web"" & npm install & npm run dev"

endlocal
