@echo off
echo 🔧 CONFIGURANDO FEEDS CORRETOS
echo ==============================
echo.

echo 📋 Mapeamento dos feeds:
echo • feed_default = Feed principal (@ArnoniBot)
echo • feed1 = Feed 1 (@ArnoniFeed1Bot)
echo • feed2 = Feed 2 (@ArnoniFeed2Bot)
echo • feed3 = Feed 3 (@ArnoniFeed3Bot)
echo • feed4 = Feed 4 (@ArnoniFeed4Bot)
echo • feed_test = teste (@ArnonitesteBot)
echo.

REM Para todos os feeds ativos primeiro
echo 🛑 Parando todos os feeds ativos...
tmux kill-session -t listener_default 2>nul
tmux kill-session -t listener_feed_test 2>nul
tmux kill-session -t main_default 2>nul
tmux kill-session -t main_feed_test 2>nul

echo ✅ Feeds parados
echo.

REM Aguarda para fechar conexões
echo ⏳ Aguardando 5 segundos...
timeout /t 5 /nobreak >nul

REM Cria arquivo .env com configuração correta
echo 📝 Criando arquivo .env com configuração correta...
(
echo # Bot EV+ - Configuração de Ambiente
echo # Mapeamento correto dos feeds baseado nos bots do Telegram
echo.
echo # ===========================================
echo # TOKENS DOS BOTS ^(um por feed^)
echo # ===========================================
echo # feed_default = Feed principal ^(@ArnoniBot^)
echo BOT_TOKEN_DEFAULT=BOT_TOKEN_DEFAULT_REDACTED
echo.
echo # feed1 = Feed 1 ^(@ArnoniFeed1Bot^)
echo BOT_TOKEN_FEED1=BOT_TOKEN_FEED1_REDACTED
echo.
echo # feed2 = Feed 2 ^(@ArnoniFeed2Bot^)
echo BOT_TOKEN_FEED2=BOT_TOKEN_FEED2_REDACTED
echo.
echo # feed3 = Feed 3 ^(@ArnoniFeed3Bot^)
echo BOT_TOKEN_FEED3=BOT_TOKEN_FEED3_REDACTED
echo.
echo # feed4 = Feed 4 ^(@ArnoniFeed4Bot^)
echo BOT_TOKEN_FEED4=BOT_TOKEN_FEED4_REDACTED
echo.
echo # feed_test = teste ^(@ArnonitesteBot^)
echo BOT_TOKEN_FEED_TEST=BOT_TOKEN_FEED_TEST_REDACTED
echo.
echo # ===========================================
echo # API ODDS
echo # ===========================================
echo ODDS_API_KEY=ODDS_API_KEY_REDACTED
echo.
echo # ===========================================
echo # CONFIGURAÇÃO DE FEEDS
echo # ===========================================
echo FEEDS=default feed1 feed2 feed3 feed4 feed_test
echo FEED_ID=default
echo.
echo # ===========================================
echo # USUÁRIOS ADMINISTRADORES
echo # ===========================================
echo ADMIN_USERS=350780046
echo.
echo # ===========================================
echo # CONFIGURAÇÕES DO SISTEMA
echo # ===========================================
echo LOG_LEVEL=INFO
echo DASHBOARD_PORT=8080
echo RATE_LIMIT_REQUESTS_PER_HOUR=4800
echo MAX_CONCURRENT_SCANS=3
echo CACHE_CLEANUP_DAYS=30
echo REQUEST_LOG_CLEANUP_HOURS=2
) > .env

echo ✅ Arquivo .env criado com configuração correta
echo.

echo 🚀 Iniciando feeds com tokens corretos...
echo.

REM Inicia feed_default (Feed principal)
echo 📱 Iniciando feed_default (Feed principal)...
set FEED_ID=default
tmux new-session -d -s "listener_default" "set FEED_ID=default && python bot_listener.py"
tmux new-session -d -s "main_default" "set FEED_ID=default && python main_scheduler.py"
echo ✅ Feed principal iniciado
echo.

REM Aguarda antes de iniciar o próximo
echo ⏳ Aguardando 10 segundos...
timeout /t 10 /nobreak >nul

REM Inicia feed_test (teste)
echo 📱 Iniciando feed_test (teste)...
set FEED_ID=feed_test
tmux new-session -d -s "listener_feed_test" "set FEED_ID=feed_test && python bot_listener.py"
tmux new-session -d -s "main_feed_test" "set FEED_ID=feed_test && python main_scheduler.py"
echo ✅ Feed teste iniciado
echo.

echo 🎉 CONFIGURAÇÃO CONCLUÍDA!
echo ==========================
echo.
echo 📋 Status dos feeds:
echo • Feed Principal: tmux attach -t listener_default
echo • Feed Teste: tmux attach -t listener_feed_test
echo.
echo 🔍 Para verificar:
echo tmux list-sessions
echo.
echo 📊 Para ver logs:
echo tail -f logs/listener_default.log
echo tail -f logs/listener_feed_test.log
echo.
echo 💡 Para iniciar outros feeds:
echo set FEED_ID=feed1 && python bot_listener.py
echo set FEED_ID=feed2 && python bot_listener.py
echo set FEED_ID=feed3 && python bot_listener.py
echo set FEED_ID=feed4 && python bot_listener.py
