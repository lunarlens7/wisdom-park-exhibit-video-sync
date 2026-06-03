@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo.
echo Building ExhibitController.exe...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "ExhibitController" ^
  --add-data "config.yaml;." ^
  --add-data ".env;." ^
  gui.py

echo.
echo Done. Executable is at dist\ExhibitController.exe
pause
