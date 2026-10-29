@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-web.ps1" %*
exit /b %ERRORLEVEL%
