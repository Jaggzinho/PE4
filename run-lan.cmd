@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-lan.ps1" %*
exit /b %ERRORLEVEL%
