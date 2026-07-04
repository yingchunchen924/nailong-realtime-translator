@echo off
cd /d "%~dp0\..\.."
if exist "gradlew.bat" (
  call gradlew.bat :apps:android:assembleDebug
) else (
  gradle :apps:android:assembleDebug
)
pause
