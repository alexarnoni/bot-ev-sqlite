@echo off
title Bot EV+ SQLite - Simples

echo ========================================
echo    BOT EV+ SQLITE - SIMPLES
echo ========================================
echo.

REM Ativa ambiente virtual
call venv\Scripts\activate.bat

REM Define feed de teste
set FEED_ID=feed_test
echo Feed: %FEED_ID%

REM Cria diretorio se necessario
if not exist "data\%FEED_ID%" mkdir "data\%FEED_ID%"
if not exist "logs\%FEED_ID%" mkdir "logs\%FEED_ID%"

echo.
echo Iniciando bot...
echo Pressione Ctrl+C para parar
echo.

REM Inicia o bot
python bot_listener.py

echo.
echo Bot parado.
pause
