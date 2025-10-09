Param(
    [Parameter(Position=0, Mandatory=$false)]
    [string]$FeedId = 'feed_test'
)

# Stop listener and scheduler processes started from this repo (ASCII-only output)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "Stopping feed: $FeedId"

# Find python processes running bot_listener.py or main_scheduler.py
$procs = Get-CimInstance Win32_Process |
    Where-Object {
        ($_.CommandLine -match 'python(\.exe)?\s+bot_listener\.py') -or
        ($_.CommandLine -match 'python(\.exe)?\s+main_scheduler\.py')
    }

if (-not $procs) {
    Write-Host "No listener/scheduler processes found."
    exit 0
}

foreach ($p in $procs) {
    try {
        Write-Host (" - Killing PID {0}: {1}" -f $p.ProcessId, $p.CommandLine)
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
    } catch {
        Write-Warning ("Failed to kill PID {0}: {1}" -f $p.ProcessId, $_.Exception.Message)
    }
}

Write-Host "Done. Feed processes stopped."


