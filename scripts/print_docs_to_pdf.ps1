# Regenerate docs/*.pdf from the HTML sources using Edge headless (Windows).
# No Python/fpdf2 required. Run from repo root:  pwsh -File scripts/print_docs_to_pdf.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Docs = Join-Path $Root "docs"

$Edge = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Edge) {
    Write-Error "Microsoft Edge not found. Open docs/*.html manually and use Ctrl+P -> Save as PDF."
}

function Print-HtmlToPdf {
    param([string]$HtmlName, [string]$PdfName)
    $htmlPath = Join-Path $Docs $HtmlName
    $pdfPath = Join-Path $Docs $PdfName
    if (-not (Test-Path $htmlPath)) { Write-Error "Missing $htmlPath" }
    $uri = "file:///" + ($htmlPath -replace '\\', '/')
    & $Edge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="$pdfPath" $uri
    Write-Host "Wrote $pdfPath"
}

Print-HtmlToPdf "trailhead-agent-project-report.html" "trailhead-agent-project-report.pdf"
Print-HtmlToPdf "trailhead-agent-engineering-reference.html" "trailhead-agent-engineering-reference.pdf"
