@echo off
chcp 65001 >nul
title Bot EV+ SQLite - Limpo

echo ========================================
echo    BOT EV+ SQLITE - INICIO LIMPO
echo ========================================
echo.

REM Para todos os processos Python
echo [1/6] Parando processos Python...
taskkill /F /IM python.exe /T >nul 2>&1
ping localhost -n 3 >nul

REM Remove ambientes virtuais antigos
echo [2/6] Removendo ambientes virtuais antigos...
rd /s /q venv 2>nul
rd /s /q venv_new 2>nul
ping localhost -n 2 >nul

REM Cria novo ambiente virtual
echo [3/6] Criando novo ambiente virtual...
python -m venv venv
if errorlevel 1 (
    echo ERRO: Falha ao criar ambiente virtual
    pause
    exit /b 1
)

REM Ativa ambiente virtual
echo [4/6] Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Instala dependências
echo [5/6] Instalando dependencias...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

REM Cria diretórios
echo [6/6] Criando diretorios...
if not exist "data\feed_test" mkdir "data\feed_test"
if not exist "logs\feed_test" mkdir "logs\feed_test"

echo.
echo ========================================
echo    INICIANDO BOT
echo ========================================
echo.
set FEED_ID=feed_test
echo Feed: %FEED_ID%
echo.

python bot_listener.py

echo.
pause
