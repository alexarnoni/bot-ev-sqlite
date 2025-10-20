# Script para iniciar o feed americano no Windows
# Define o feed_id e inicia o bot

Write-Host "Iniciando American Sports Feed..." -ForegroundColor Green

# Define variáveis de ambiente
$env:FEED_ID = "feed_american"

# Verifica se o token está configurado
if (-not $env:BOT_TOKEN_FEED_AMERICAN) {
    Write-Host "ERRO: BOT_TOKEN_FEED_AMERICAN nao configurado!" -ForegroundColor Red
    Write-Host "Configure a variavel de ambiente BOT_TOKEN_FEED_AMERICAN" -ForegroundColor Yellow
    Write-Host "Exemplo: `$env:BOT_TOKEN_FEED_AMERICAN = 'seu_token_aqui'" -ForegroundColor Yellow
    exit 1
}

# Verifica se a API key está configurada
if (-not $env:ODDS_API_KEY) {
    Write-Host "ERRO: ODDS_API_KEY nao configurada!" -ForegroundColor Red
    Write-Host "Configure a variavel de ambiente ODDS_API_KEY" -ForegroundColor Yellow
    exit 1
}

Write-Host "OK: Variaveis de ambiente configuradas" -ForegroundColor Green
Write-Host "Feed ID: $env:FEED_ID" -ForegroundColor Cyan
Write-Host "Token: $($env:BOT_TOKEN_FEED_AMERICAN.Substring(0,8))..." -ForegroundColor Cyan

# Inicia o bot
Write-Host "Iniciando bot..." -ForegroundColor Green
python bot_listener.py
