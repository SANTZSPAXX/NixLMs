@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo AVISO: iniciando o prototipo legado NixLMs 0.1 (nixlms.py).
echo Para a versao neural atual, execute iniciar.bat ou iniciar_interface.bat.
where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado. Instale Python 3.10 ou superior.
    pause
    exit /b 1
)
python nixlms.py
pause
