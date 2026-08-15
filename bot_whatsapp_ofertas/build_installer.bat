@echo off
setlocal

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_installer.ps1"
if errorlevel 1 goto erro

echo.
echo Instalador gerado em: installer\Bot.eeSetup.exe
pause
exit /b 0

:erro
echo.
echo O processo falhou. Veja as linhas acima para identificar o erro.
pause
exit /b 1
