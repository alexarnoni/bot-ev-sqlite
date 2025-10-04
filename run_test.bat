@echo off
title Bot EV+ SQLite - Teste

echo ========================================
echo    BOT EV+ SQLITE - TESTE
echo ========================================
echo.

REM Ativa ambiente virtual
call venv\Scripts\activate.bat

REM Define feed de teste
set FEED_ID=feed_test
echo Feed: %FEED_ID%
echo Token: BOT_TOKEN_FEED_TEST

REM Cria diretorio se necessario
if not exist "data\%FEED_ID%" mkdir "data\%FEED_ID%"

REM Executa teste
echo.
echo Testando sistema...
set FEED_ID=feed_test
python test_simple.py

echo.
echo Teste concluido!
echo.
echo Deseja iniciar o bot? (s/n)
set /p choice=
if /i "%choice%"=="s" (
    echo.
    echo Iniciando bot...
    echo Pressione Ctrl+C para parar
    echo.
    set FEED_ID=feed_test
    python bot_listener.py
)

echo.
pause
