@echo off
echo INICIANDO FEEDS SIMPLES
echo =======================

REM Para processos existentes
echo Parando processos existentes...
taskkill /f /im python.exe 2>nul

echo Aguardando 3 segundos...
timeout /t 3 /nobreak >nul

REM Cria arquivo .env
echo Criando arquivo .env...
(
echo BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
echo BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es
echo ODDS_API_KEY=d1ffd194fc054b5c7e9691d6aed713c66ab77bc0c9fbd62f66c0d8b04c6f1bea
echo FEED_ID=default
echo ADMIN_USERS=350780046
) > .env

echo Arquivo .env criado
echo.

echo Iniciando feed DEFAULT...
set FEED_ID=default
start "Feed Default" cmd /k "set FEED_ID=default && python bot_listener.py"

echo Aguardando 10 segundos...
timeout /t 10 /nobreak >nul

echo Iniciando feed TESTE...
set FEED_ID=feed_test
start "Feed Teste" cmd /k "set FEED_ID=feed_test && python bot_listener.py"

echo.
echo FEEDS INICIADOS!
echo ================
echo.
echo Verifique as janelas que abriram:
echo - Feed Default: @ArnoniBot
echo - Feed Teste: @ArnonitesteBot
echo.
echo Para parar: feche as janelas ou execute taskkill /f /im python.exe
