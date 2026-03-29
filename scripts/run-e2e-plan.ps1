# Full plan run with video + JSON saved under artifacts/e2e-<timestamp>/ (uses .env for URL, intent, API keys).
# Run from repo root, or adjust paths below.
# -WalkRanked N: after ranking, visit first N ranked URLs in the browser (clearer .webm). Use 0 to skip.

param(
    [int]$WalkRanked = 5
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$OutDir = Join-Path (Join-Path $Root "artifacts") "e2e-$ts"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$abs = (Resolve-Path $OutDir).Path

Write-Host "E2E artifacts -> $abs"

$venvTrailhead = Join-Path $Root ".venv\Scripts\trailhead-agent.exe"
$trailhead = if (Test-Path $venvTrailhead) { $venvTrailhead } else { "trailhead-agent" }

$extra = @()
if ($WalkRanked -gt 0) {
    $extra = @("--walk-ranked", "$WalkRanked")
}
& $trailhead plan --json --artifacts-dir $abs @extra
$code = $LASTEXITCODE
Write-Host "Exit code: $code"
Write-Host "Open: $abs (e2e-plan-latest.json + *.webm)"
exit $code
