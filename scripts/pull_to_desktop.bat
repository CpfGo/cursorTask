@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pull_to_desktop.ps1" %*
if errorlevel 1 exit /b 1
endlocal
