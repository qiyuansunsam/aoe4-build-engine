param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -X utf8 site/build.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    python -X utf8 server/app.py --port $Port
} finally { Pop-Location }
