@echo off
echo Restaurando arquivo .env completo...

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

echo Arquivo .env restaurado com sucesso!
echo.
echo Conteúdo do arquivo:
type .env
