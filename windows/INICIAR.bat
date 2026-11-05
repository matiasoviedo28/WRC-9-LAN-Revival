@echo off
rem Abre el servidor KtOS local de WRC 9 con permisos de administrador.
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
title WRC 9 LAN Revival
where py >nul 2>&1
if not errorlevel 1 (
    py -3 wrc9-ktos.py
    goto fin
)
python --version >nul 2>&1
if not errorlevel 1 (
    python wrc9-ktos.py
    goto fin
)
echo.
echo  Falta Python. Instalalo desde https://www.python.org/downloads/
echo  y volve a abrir INICIAR.bat.
echo.
:fin
pause
