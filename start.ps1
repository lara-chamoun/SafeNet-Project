param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host 'First install SafeNet using the setup commands in README.md.'
    exit 1
}
& $pythonPath -m safenet.web --port $Port
exit $LASTEXITCODE
