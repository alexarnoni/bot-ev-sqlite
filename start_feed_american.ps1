# ===========================================
# Script: start_feed_american.ps1
# Objetivo: Iniciar o feed americano (Windows PowerShell)
# ===========================================

$ErrorActionPreference = 'Stop'

Write-Host "Iniciando American Sports Feed..."

# 1) Ativar ambiente virtual
$venv = Join-Path $PSScriptRoot 'venv\Scripts\Activate.ps1'
if (Test-Path $venv) {
    & $venv
} else {
    Write-Host "ERRO: venv nao encontrado em $venv" -ForegroundColor Red
    Write-Host "Crie com: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# 2) Carregar .env para variaveis de ambiente desta sessao
$dotenv = Join-Path $PSScriptRoot '.env'
if (Test-Path $dotenv) {
    Write-Host "Carregando variaveis do .env..."
    Get-Content $dotenv | ForEach-Object {
        if ($_ -match '^\s*#') { return }     # ignora comentarios
        if ($_ -match '^\s*$') { return }     # ignora linhas vazias
        $pair = $_ -split '=', 2
        if ($pair.Length -eq 2) {
            $name  = $pair[0].Trim()
            $value = $pair[1].Trim('" ')
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

# 3) Definir o feed
$env:FEED_ID = 'feed_american'

# 4) Validacoes
if (-not $env:BOT_TOKEN_FEED_AMERICAN) {
    Write-Host "ERRO: BOT_TOKEN_FEED_AMERICAN nao configurado!" -ForegroundColor Red
    Write-Host "Defina no .env ou nesta sessao: `$env:BOT_TOKEN_FEED_AMERICAN = 'seu_token'" -ForegroundColor Yellow
    exit 1
}
if (-not $env:ODDS_API_KEY) {
    Write-Host "ERRO: ODDS_API_KEY nao configurada!" -ForegroundColor Red
    Write-Host "Defina no .env ou nesta sessao: `$env:ODDS_API_KEY = 'sua_key'" -ForegroundColor Yellow
    exit 1
}

Write-Host ("FEED_ID: {0}" -f $env:FEED_ID)
Write-Host ("Token: {0}..." -f $env:BOT_TOKEN_FEED_AMERICAN.Substring(0,8))

# 5) Iniciar o listener (Telegram UI do feed)
Write-Host "Iniciando bot_listener.py..."
python bot_listener.py
