@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not defined NIXLMS_PORT set "NIXLMS_PORT=8765"
where python >nul 2>nul
if errorlevel 1 (echo Python 3.10+ nao encontrado.& pause& exit /b 1)
start "NixLMs Interface" /min cmd /c "python -m nixlms_web.server"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%NIXLMS_PORT%"
echo Interface aberta. Feche a janela do servidor para encerrar.
