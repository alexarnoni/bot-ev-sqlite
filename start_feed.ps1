Param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$FeedId
)

# Inicia um único feed no Windows/PowerShell (duas janelas)
# Uso:
#   .\start_feed.ps1 feed_test
# Ou sem argumento (usa FEED_ID do ambiente ou 'default')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Carrega variáveis do .env (se existir)
$envPath = Join-Path $PSScriptRoot '.env'
if (Test-Path $envPath) {
    Get-Content $envPath | Where-Object { $_ -and ($_ -notmatch '^\s*#') } | ForEach-Object {
        $k, $v = $_.Split('=', 2)
        if ($k -and $v) { [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim()) }
    }
}

if (-not $FeedId -or [string]::IsNullOrWhiteSpace($FeedId)) {
    $FeedId = if ($env:FEED_ID) { $env:FEED_ID } else { 'default' }
}

Write-Host "🚀 Iniciando feed: $FeedId"

# Garante diretórios
$dataDir = Join-Path $PSScriptRoot "data/$FeedId"
$logsDir = Join-Path $PSScriptRoot "logs/$FeedId"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# Define FEED_ID para os processos filhos
$env:FEED_ID = $FeedId

# Abre duas janelas PowerShell: listener e scheduler
Start-Process PowerShell -ArgumentList '-NoExit','-Command',"`$env:FEED_ID='$FeedId'; python bot_listener.py"
Start-Process PowerShell -ArgumentList '-NoExit','-Command',"`$env:FEED_ID='$FeedId'; python main_scheduler.py"

Write-Host "✅ Feed $FeedId iniciado em duas janelas (listener e scheduler)."
Write-Host "🛑 Para parar, feche as janelas ou use Ctrl+C nelas."


