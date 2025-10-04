@echo off
echo 🔧 CORRIGINDO CONFLITO DE TOKENS DO TELEGRAM
echo =============================================
echo.

REM Para todos os feeds ativos
echo 🛑 Parando todos os feeds ativos...
tmux kill-session -t listener_default 2>nul
tmux kill-session -t listener_feed_test 2>nul
tmux kill-session -t main_default 2>nul
tmux kill-session -t main_feed_test 2>nul

echo ✅ Feeds parados
echo.

REM Aguarda um pouco para garantir que as conexões foram fechadas
echo ⏳ Aguardando 5 segundos para fechar conexões...
timeout /t 5 /nobreak >nul

REM Cria arquivo .env com tokens corretos
echo 📝 Criando arquivo .env com tokens corretos...
(
echo # Bot EV+ - Configuração de Ambiente
echo # Tokens diferentes para cada feed
echo.
echo # ===========================================
echo # TOKENS DOS BOTS ^(um por feed^)
echo # ===========================================
echo BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
echo BOT_TOKEN_FEED1=8047370953:AAG0sh1sjVqyW7NnmrGqBVJypmRcPYHb9hM
echo BOT_TOKEN_FEED2=8435178186:AAGQx2F-i9pNjZ4XXkQvMpazPMwjFiW9HfY
echo BOT_TOKEN_FEED3=7812298685:AAHpClDOP4hxGgGXw5H29wyqBJRvfvg5JxM
echo BOT_TOKEN_FEED4=8222396387:AAF8G1gljEDZ8DvrH0HQA9s3ogJgw6Lubr8
echo BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es
echo.
echo # ===========================================
echo # API ODDS
echo # ===========================================
echo ODDS_API_KEY=d1ffd194fc054b5c7e9691d6aed713c66ab77bc0c9fbd62f66c0d8b04c6f1bea
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

echo ✅ Arquivo .env criado com tokens corretos
echo.

REM Inicia apenas o feed default com seu token específico
echo 🚀 Iniciando feed DEFAULT com token específico...
set FEED_ID=default
set BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
tmux new-session -d -s listener_default "set FEED_ID=default && python bot_listener.py"
tmux new-session -d -s main_default "set FEED_ID=default && python main_scheduler.py"

echo ✅ Feed DEFAULT iniciado
echo.

REM Aguarda um pouco antes de iniciar o segundo feed
echo ⏳ Aguardando 10 segundos antes de iniciar feed_test...
timeout /t 10 /nobreak >nul

REM Inicia o feed_test com seu token específico
echo 🚀 Iniciando feed FEED_TEST com token específico...
set FEED_ID=feed_test
set BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es
tmux new-session -d -s listener_feed_test "set FEED_ID=feed_test && python bot_listener.py"
tmux new-session -d -s main_feed_test "set FEED_ID=feed_test && python main_scheduler.py"

echo ✅ Feed FEED_TEST iniciado
echo.

echo 🎉 CORREÇÃO CONCLUÍDA!
echo ======================
echo.
echo 📋 Status dos feeds:
echo • DEFAULT: tmux attach -t listener_default
echo • FEED_TEST: tmux attach -t listener_feed_test
echo.
echo 🔍 Para verificar se está funcionando:
echo tmux list-sessions
echo.
echo 📊 Para ver logs:
echo tail -f logs/listener_default.log
echo tail -f logs/listener_feed_test.log
