@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call install_dependencies.bat
)
".venv\Scripts\pyinstaller.exe" ^
  --noconsole ^
  --onefile ^
  --name "奶龙实时翻译" ^
  --icon "..\..\assets\nailong.ico" ^
  --add-data "..\..\assets;assets" ^
  --add-data "..\..\tessdata;tessdata" ^
  app.py
pause
