@echo off
setlocal

cd /d "%~dp0"

set PLAYWRIGHT_BROWSERS_PATH=0

python -m pip install -r requirements.txt
python -m playwright install chromium
python -m PyInstaller --noconfirm --windowed --name Bot.ee --icon "assets\app_icon.ico" --add-data "assets;assets" app.py

echo.
echo Aplicativo gerado em: dist\Bot.ee\Bot.ee.exe
pause
