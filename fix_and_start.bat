@echo off
title Corrigir e Iniciar Bot EV+

echo ========================================
echo    CORRIGIR E INICIAR BOT EV+
echo ========================================
echo.

echo Parando processos do Python...
taskkill /F /IM python.exe /T >nul 2>&1

echo Aguardando...
timeout /t 3 /nobreak >nul

echo.
echo Excluindo ambiente virtual antigo...
if exist "venv" (
    rmdir /s /q "venv" 2>nul
    if exist "venv" (
        echo AVISO: Nao foi possivel excluir completamente o venv antigo
    )
)

if exist "venv_new" (
    rmdir /s /q "venv_new" 2>nul
)

echo.
echo Criando novo ambiente virtual...
python -m venv venv

echo.
echo Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo.
echo Atualizando pip...
python -m pip install --upgrade pip --quiet

echo.
echo Instalando dependencias (isso pode levar alguns minutos)...
pip install -r requirements.txt --quiet

echo.
echo Criando diretorios...
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
echo Bot iniciado! Pressione Ctrl+C para parar
echo.

python bot_listener.py

echo.
echo Bot parado.
pause
