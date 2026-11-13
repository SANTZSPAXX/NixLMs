@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado. Instale Python 3.10 ou superior.
    pause
    exit /b 1
)
python nixlms.py
pause
