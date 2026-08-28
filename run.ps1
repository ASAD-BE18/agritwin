if (-not $env:OPENROUTER_API_KEY) {
	Write-Error "Set OPENROUTER_API_KEY before starting real-agent mode."
	exit 1
}

.\scripts\run-dev-stack.ps1 -RealAgent -OpenRouterApiKey $env:OPENROUTER_API_KEY