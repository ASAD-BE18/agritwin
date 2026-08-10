<#
.SYNOPSIS
    Launches the full AgriTwin dev stack for local testing: backend, a mock data
    feed, and the chat UI, each in its own window so you can watch logs live.

.DESCRIPTION
    Starts three processes:
      1. FastAPI backend        (backend/app/main.py)      -> http://localhost:8000
      2. Mock data replay       (bridge/mock_source.py)     -> feeds the backend
      3. Chat UI                (chat/chat_app.py)          -> http://127.0.0.1:8001

    Defaults to stub mode for the chat UI (no API key needed). Pass -RealAgent
    with -AnthropicApiKey to have it actually call Claude through mcp/mcp_server.py
    (mcp_server.py is spawned by chat_app.py itself -- you don't start it separately).

    Each service opens in its own PowerShell window; close a window (or Ctrl+C
    inside it) to stop that piece independently. Ports 8000 and 8001 must be free.

.PARAMETER ApiKey
    AGRITWIN_API_KEY -- must match the backend's. Defaults to the repo's documented
    dev key (backend/app/config.py's default).

.PARAMETER MockSpeedup
    How much faster than real-time to replay the 30-minute mock dataset.
    Default 30 (~1 minute total instead of 30).

.PARAMETER RealAgent
    Switch. When set, starts the chat UI with USE_REAL_AGENT=true. Requires
    -AnthropicApiKey.

.PARAMETER AnthropicApiKey
    Your Anthropic API key. Required (and only used) when -RealAgent is set.

.EXAMPLE
    .\scripts\run-dev-stack.ps1
    Everything in stub mode against the mock data replay.

.EXAMPLE
    .\scripts\run-dev-stack.ps1 -RealAgent -AnthropicApiKey sk-ant-...
    Same, but the chat UI actually calls Claude via mcp_server.py.
#>

param(
    [string]$ApiKey = "dev-only-key-change-me",
    [int]$MockSpeedup = 30,
    [switch]$RealAgent,
    [string]$AnthropicApiKey = ""
)

$ErrorActionPreference = "Stop"

if ($RealAgent -and -not $AnthropicApiKey) {
    Write-Error "-RealAgent requires -AnthropicApiKey <your key>"
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

# --- 1. Backend ---
Write-Host "Starting backend on http://localhost:8000 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$RepoRoot\backend'; `$env:AGRITWIN_API_KEY='$ApiKey'; & '$VenvPython' -m uvicorn app.main:app --reload"
)
Start-Sleep -Seconds 3

# --- 2. Mock data feed ---
Write-Host "Starting mock data replay (speedup=${MockSpeedup}x) ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$RepoRoot\bridge'; `$env:MODE='mock'; `$env:AGRITWIN_API_KEY='$ApiKey'; `$env:AGRITWIN_BACKEND_URL='http://127.0.0.1:8000'; `$env:MOCK_SPEEDUP='$MockSpeedup'; & '$VenvPython' mock_source.py"
)
Start-Sleep -Seconds 2

# --- 3. Chat UI ---
$ChatEnv = "`$env:AGRITWIN_API_KEY='$ApiKey'; `$env:AGRITWIN_BACKEND_URL='http://127.0.0.1:8000';"
if ($RealAgent) {
    Write-Host "Starting chat UI in REAL mode on http://127.0.0.1:8001 (will call Claude) ..."
    $ChatEnv += " `$env:USE_REAL_AGENT='true'; `$env:ANTHROPIC_API_KEY='$AnthropicApiKey';"
} else {
    Write-Host "Starting chat UI in STUB mode on http://127.0.0.1:8001 ..."
}
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$RepoRoot\chat'; $ChatEnv & '$VenvPython' -m uvicorn chat_app:app --reload --port 8001"
)
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "All three windows are up:"
Write-Host "  Backend state: http://localhost:8000/api/v1/state"
Write-Host "  Chat UI:       http://127.0.0.1:8001"
Write-Host ""
Write-Host "Close a window (or Ctrl+C inside it) to stop that piece independently."

Start-Process "http://127.0.0.1:8001"
