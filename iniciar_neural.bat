@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (echo Python 3.10+ nao encontrado. & pause & exit /b 1)
python --version
python neural_core.py
pause
