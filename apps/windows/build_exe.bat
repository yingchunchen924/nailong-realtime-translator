@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call install_dependencies.bat
)
if not exist "..\..\dist\windows" (
  mkdir "..\..\dist\windows"
)
if not exist "build\home" (
  mkdir "build\home"
)
if not exist "build\resources" (
  mkdir "build\resources"
)
set "USERPROFILE=%CD%\build\home"
set "HOME=%CD%\build\home"
set "PYINSTALLER_CONFIG_DIR=%CD%\build\resources"
".venv\Scripts\pyinstaller.exe" ^
  --noconsole ^
  --onefile ^
  --clean ^
  --distpath "..\..\dist\windows" ^
  --workpath "build" ^
  --name "奶龙实时翻译" ^
  --icon "..\..\assets\nailong.ico" ^
  --add-data "..\..\assets;assets" ^
  --add-data "..\..\tessdata;tessdata" ^
  app.py
pause
