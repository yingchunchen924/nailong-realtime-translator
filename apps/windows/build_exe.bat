@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call install_dependencies.bat
)
if not exist "..\..\dist\windows" (
  mkdir "..\..\dist\windows"
)
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
