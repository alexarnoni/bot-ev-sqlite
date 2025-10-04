@echo off
title Debug Bot EV+ SQLite

echo ========================================
echo    DEBUG BOT EV+ SQLITE
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
echo Abrindo janelas de debug...
echo.

REM Janela 1: Bot principal
echo Abrindo janela do Bot...
start "Bot EV+ - Principal" cmd /k "call venv\Scripts\activate.bat && set FEED_ID=feed_test && echo ======================================== && echo    BOT EV+ SQLITE - PRINCIPAL && echo ======================================== && echo. && echo Iniciando bot... && echo Pressione Ctrl+C para parar && echo. && python bot_listener.py"

REM Aguarda um pouco
timeout /t 3 /nobreak >nul

REM Janela 2: Logs em tempo real
echo Abrindo janela de Logs...
start "Bot EV+ - Logs" cmd /k "echo ======================================== && echo    LOGS EM TEMPO REAL && echo ======================================== && echo. && echo Monitorando logs... && echo. && if exist \"logs\feed_test\bot.log\" (powershell -Command \"Get-Content 'logs\feed_test\bot.log' -Wait -Tail 20\") else (echo Arquivo de log nao encontrado. Aguardando... && timeout /t 5 /nobreak >nul && goto :eof)"

REM Aguarda um pouco
timeout /t 2 /nobreak >nul

REM Janela 3: Status do sistema
echo Abrindo janela de Status...
start "Bot EV+ - Status" cmd /k "call venv\Scripts\activate.bat && echo ======================================== && echo    STATUS DO SISTEMA && echo ======================================== && echo. && echo Monitorando status... && echo. && :loop && echo Testando sistema... && set FEED_ID=feed_test && python test_simple.py && echo. && timeout /t 30 /nobreak >nul && goto loop"

REM Aguarda um pouco
timeout /t 2 /nobreak >nul

REM Janela 4: Banco de dados
echo Abrindo janela do Banco...
start "Bot EV+ - Banco" cmd /k "echo ======================================== && echo    BANCO DE DADOS && echo ======================================== && echo. && echo Banco: data\feed_test\bot.db && echo. && if exist \"data\feed_test\bot.db\" (echo Banco encontrado! && dir \"data\feed_test\bot.db\") else (echo Banco nao encontrado - sera criado automaticamente) && echo. && echo Pressione qualquer tecla para sair... && pause >nul"

echo.
echo ========================================
echo    JANELAS ABERTAS
echo ========================================
echo.
echo 1. Bot Principal - O bot em execucao
echo 2. Logs - Logs em tempo real
echo 3. Status - Status do sistema (atualiza a cada 30s)
echo 4. Banco - Informacoes do banco de dados
echo.
echo Feche as janelas individuais para parar o debug
echo.
echo Pressione qualquer tecla para sair...
pause >nul
