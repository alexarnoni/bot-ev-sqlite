@echo off
if "%1"=="" (
    echo ❌ Uso: start_feed.bat [feed_id]
    echo.
    echo Feeds disponíveis:
    echo • default (Feed principal - @ArnoniBot)
    echo • feed1 (Feed 1 - @ArnoniFeed1Bot)
    echo • feed2 (Feed 2 - @ArnoniFeed2Bot)
    echo • feed3 (Feed 3 - @ArnoniFeed3Bot)
    echo • feed4 (Feed 4 - @ArnoniFeed4Bot)
    echo • feed_test (teste - @ArnonitesteBot)
    echo.
    echo Exemplo: start_feed.bat feed1
    exit /b 1
)

set FEED_ID=%1
echo 🚀 Iniciando feed: %FEED_ID%

REM Para o feed se já estiver rodando
echo 🛑 Parando feed %FEED_ID% se estiver rodando...
tmux kill-session -t listener_%FEED_ID% 2>nul
tmux kill-session -t main_%FEED_ID% 2>nul

REM Aguarda um pouco
timeout /t 3 /nobreak >nul

REM Inicia o feed
echo 📱 Iniciando listener para %FEED_ID%...
tmux new-session -d -s "listener_%FEED_ID%" "set FEED_ID=%FEED_ID% && python bot_listener.py"

echo ⏰ Iniciando scheduler para %FEED_ID%...
tmux new-session -d -s "main_%FEED_ID%" "set FEED_ID=%FEED_ID% && python main_scheduler.py"

echo ✅ Feed %FEED_ID% iniciado com sucesso!
echo.
echo 📋 Para ver o feed:
echo tmux attach -t listener_%FEED_ID%
echo.
echo 📊 Para ver logs:
echo tail -f logs/listener_%FEED_ID%.log
