@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Rode primeiro o iniciar_servidor.bat uma vez para instalar as bibliotecas.
    pause
    exit /b 1
)
.venv\Scripts\python.exe configurar_login.py
pause
