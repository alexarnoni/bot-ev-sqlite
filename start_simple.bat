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
echo BOT_TOKEN_DEFAULT=BOT_TOKEN_DEFAULT_REDACTED
echo BOT_TOKEN_FEED_TEST=BOT_TOKEN_FEED_TEST_REDACTED
echo ODDS_API_KEY=ODDS_API_KEY_REDACTED
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
