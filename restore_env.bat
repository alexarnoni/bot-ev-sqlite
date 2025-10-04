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
echo BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI
echo.
echo # feed1 = Feed 1 ^(@ArnoniFeed1Bot^)
echo BOT_TOKEN_FEED1=8047370953:AAG0sh1sjVqyW7NnmrGqBVJypmRcPYHb9hM
echo.
echo # feed2 = Feed 2 ^(@ArnoniFeed2Bot^)
echo BOT_TOKEN_FEED2=8435178186:AAGQx2F-i9pNjZ4XXkQvMpazPMwjFiW9HfY
echo.
echo # feed3 = Feed 3 ^(@ArnoniFeed3Bot^)
echo BOT_TOKEN_FEED3=7812298685:AAHpClDOP4hxGgGXw5H29wyqBJRvfvg5JxM
echo.
echo # feed4 = Feed 4 ^(@ArnoniFeed4Bot^)
echo BOT_TOKEN_FEED4=8222396387:AAF8G1gljEDZ8DvrH0HQA9s3ogJgw6Lubr8
echo.
echo # feed_test = teste ^(@ArnonitesteBot^)
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

echo Arquivo .env restaurado com sucesso!
echo.
echo Conteúdo do arquivo:
type .env
