@echo off
rem Roda a partir da pasta deste arquivo (funciona em qualquer PC/pasta)
cd /d "%~dp0"

rem Primeira vez: cria o ambiente Python e instala as bibliotecas
if not exist ".venv\Scripts\python.exe" (
    echo Primeira execucao: instalando as bibliotecas, aguarde...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERRO: Python nao encontrado. Instale em https://www.python.org/downloads/
        echo e marque a opcao "Add python.exe to PATH" durante a instalacao.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

.venv\Scripts\python.exe servidor.py
pause
