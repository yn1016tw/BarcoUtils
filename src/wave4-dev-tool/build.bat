@echo off
cd /d "%~dp0"
pip install -r requirements.txt
pyinstaller --onefile --add-data "ui;ui" --name wave4-dev-tool app.py
echo.
echo Build complete: dist\wave4-dev-tool.exe
pause
