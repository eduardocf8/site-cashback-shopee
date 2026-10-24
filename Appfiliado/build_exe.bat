@echo off
setlocal

cd /d "%~dp0"

set PLAYWRIGHT_BROWSERS_PATH=0

python -m pip install -r requirements.txt
python -m playwright install chromium

rem Trocado de PyInstaller para Nuitka: o PyInstaller empacota um
rem interpretador Python + bytecode e se "auto-extrai" ao rodar, um padrao
rem que antivirus com heuristica costumam marcar como suspeito (falso
rem positivo). O Nuitka compila o Python de verdade para codigo de
rem maquina nativo, resultando em muito menos deteccoes.
rem --assume-yes-for-downloads: se nao houver compilador C instalado, o
rem Nuitka baixa sozinho um MinGW64 portatil na primeira vez (so acontece
rem uma vez por maquina).
python -m nuitka --standalone --assume-yes-for-downloads --enable-plugins=pyside6 --windows-console-mode=disable --windows-icon-from-ico="assets\app_icon.ico" --include-data-dir="assets=assets" --output-dir=dist --output-filename=Appfiliado.exe app.py

echo.
echo Aplicativo gerado em: dist\app.dist\Appfiliado.exe
pause
