@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-ml-cpu.ps1" %*
if errorlevel 1 (
  echo Falha na instalacao opcional de frameworks da NixLMs.
  exit /b 1
)
endlocal
