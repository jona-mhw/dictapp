@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "MARKER=%VENV%\.deps_marker"
set "NEEDS_INSTALL="

if not exist "%PY%" (
    echo [DictarApp] Primera ejecucion: creando entorno virtual...
    where py >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python no esta instalado o no esta en PATH.
        echo Descargalo desde https://www.python.org/downloads/  ^(version 3.10 o superior^)
        pause
        exit /b 1
    )
    py -3 -m venv "%VENV%"
    if errorlevel 1 (
        echo ERROR: no se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    "%PY%" -m pip install --upgrade pip
    set "NEEDS_INSTALL=1"
)

if not exist "%MARKER%" (
    set "NEEDS_INSTALL=1"
) else (
    powershell -NoProfile -Command "if ((Get-Item 'requirements.txt').LastWriteTime -gt (Get-Item '%MARKER%').LastWriteTime) { exit 1 } else { exit 0 }"
    if errorlevel 1 set "NEEDS_INSTALL=1"
)

if defined NEEDS_INSTALL (
    echo [DictarApp] Instalando/actualizando dependencias...
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
    echo Instalado %DATE% %TIME% > "%MARKER%"
)

echo === DictarApp ^(modo debug, consola visible^) ===
echo.
"%PY%" DictarApp.py
echo.
echo === App finalizada ^(codigo de salida: %errorlevel%^) ===
pause
