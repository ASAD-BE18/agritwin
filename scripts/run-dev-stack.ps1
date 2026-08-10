<#
.SYNOPSIS
    Launches the full AgriTwin dev stack for local testing: backend, a mock data
    feed, and the chat UI, all as background jobs streaming into this one window.

.DESCRIPTION
    Starts three processes as PowerShell background jobs:
      1. FastAPI backend        (backend/app/main.py)      -> http://localhost:8000
      2. Mock data replay       (bridge/mock_source.py)     -> feeds the backend
      3. Chat UI                (chat/chat_app.py)          -> http://127.0.0.1:8001

    Defaults to stub mode for the chat UI (no API key needed). Pass -RealAgent
    with -OpenRouterApiKey to have it actually call the model (OpenRouter's free
    router, "openrouter/free") through mcp/mcp_server.py (mcp_server.py is
    spawned by chat_app.py itself -- you don't start it separately).

    All three services' output streams into this single window, each line
    prefixed with [backend]/[mock]/[chat]. Press Ctrl+C to stop all three at
    once. Ports 8000 and 8001 must be free.

.PARAMETER ApiKey
    AGRITWIN_API_KEY -- must match the backend's. Defaults to the repo's documented
    dev key (backend/app/config.py's default).

.PARAMETER MockSpeedup
    How much faster than real-time to replay the 30-minute mock dataset.
    Default 30 (~1 minute total instead of 30).

.PARAMETER RealAgent
    Switch. When set, starts the chat UI with USE_REAL_AGENT=true. Requires
    -OpenRouterApiKey.

.PARAMETER OpenRouterApiKey
    Your OpenRouter API key. Required (and only used) when -RealAgent is set.

.EXAMPLE
    .\scripts\run-dev-stack.ps1
    Everything in stub mode against the mock data replay.

.EXAMPLE
    .\scripts\run-dev-stack.ps1 -RealAgent -OpenRouterApiKey sk-or-...
    Same, but the chat UI actually calls the model via OpenRouter + mcp_server.py.
#>

param(
    [string]$ApiKey = "dev-only-key-change-me",
    [int]$MockSpeedup = 30,
    [switch]$RealAgent,
    [string]$OpenRouterApiKey = ""
)

$ErrorActionPreference = "Stop"

if ($RealAgent -and -not $OpenRouterApiKey) {
    Write-Error "-RealAgent requires -OpenRouterApiKey <your key>"
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtualenv not found at $VenvPython -- create it and install each service's dependencies first (see each folder's README)."
    exit 1
}

Write-Host "Repo root: $RepoRoot"
Write-Host "Python:    $VenvPython"
Write-Host ""

$jobs = @()

# --- 1. Backend ---
$jobs += Start-Job -Name "backend" -ScriptBlock {
    param($RepoRoot, $VenvPython, $ApiKey)
    Set-Location "$RepoRoot\backend"
    $env:AGRITWIN_API_KEY = $ApiKey
    & $VenvPython -m uvicorn app.main:app --reload 2>&1
} -ArgumentList $RepoRoot, $VenvPython, $ApiKey
Start-Sleep -Seconds 3

# --- 2. Mock data feed ---
$jobs += Start-Job -Name "mock" -ScriptBlock {
    param($RepoRoot, $VenvPython, $ApiKey, $MockSpeedup)
    Set-Location "$RepoRoot\bridge"
    $env:MODE = "mock"
    $env:AGRITWIN_API_KEY = $ApiKey
    $env:AGRITWIN_BACKEND_URL = "http://127.0.0.1:8000"
    $env:MOCK_SPEEDUP = "$MockSpeedup"
    & $VenvPython mock_source.py 2>&1
} -ArgumentList $RepoRoot, $VenvPython, $ApiKey, $MockSpeedup
Start-Sleep -Seconds 2

# --- 3. Chat UI ---
if ($RealAgent) {
    Write-Host "Chat UI will start in REAL mode (calls Claude) ..."
} else {
    Write-Host "Chat UI will start in STUB mode ..."
}
$jobs += Start-Job -Name "chat" -ScriptBlock {
    param($RepoRoot, $VenvPython, $ApiKey, $RealAgent, $OpenRouterApiKey)
    Set-Location "$RepoRoot\chat"
    $env:AGRITWIN_API_KEY = $ApiKey
    $env:AGRITWIN_BACKEND_URL = "http://127.0.0.1:8000"
    if ($RealAgent) {
        $env:USE_REAL_AGENT = "true"
        $env:OPENROUTER_API_KEY = $OpenRouterApiKey
    }
    & $VenvPython -m uvicorn chat_app:app --reload --port 8001 2>&1
} -ArgumentList $RepoRoot, $VenvPython, $ApiKey, $RealAgent, $OpenRouterApiKey
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Backend state: http://localhost:8000/api/v1/state"
Write-Host "Chat UI:       http://127.0.0.1:8001"
Write-Host ""
Write-Host "Streaming logs below, prefixed [backend]/[mock]/[chat]. Ctrl+C stops all three."
Write-Host ""

Start-Process "http://127.0.0.1:8001"

try {
    while ($jobs | Where-Object { $_.State -eq "Running" }) {
        foreach ($job in $jobs) {
            Receive-Job -Job $job | ForEach-Object { Write-Host "[$($job.Name)] $_" }
        }
        Start-Sleep -Milliseconds 300
    }
    # Drain anything left after a job exits on its own.
    foreach ($job in $jobs) {
        Receive-Job -Job $job | ForEach-Object { Write-Host "[$($job.Name)] $_" }
    }
}
finally {
    Write-Host ""
    Write-Host "Stopping all jobs..."
    $jobs | Stop-Job -ErrorAction SilentlyContinue
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
}
