@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Iniciando a interface neural da NixLMs...
call iniciar_interface.bat
