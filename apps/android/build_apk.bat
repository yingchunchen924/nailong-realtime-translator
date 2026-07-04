@echo off
cd /d "%~dp0\..\.."

powershell -ExecutionPolicy Bypass -File scripts\build_android_apk.ps1
if errorlevel 1 pause & exit /b 1
pause
