param(
    [string]$Label = 'Games - RM 1v1 - Season 13',
    [string]$Destination = 'data/engine/raw/rm_1v1_s13.json.gz'
)
$ErrorActionPreference = 'Stop'
# Fresh signed link per download, no API history crawling or rotating identities.
$dumpPage = (Invoke-WebRequest 'https://aoe4world.com/dumps' -TimeoutSec 30).Content
$anchor = [regex]::Matches($dumpPage, 'href="([^"]+)"[^>]*>([^<]*)') |
    Where-Object { $_.Groups[2].Value.Trim() -eq $Label } | Select-Object -First 1
if (-not $anchor) { throw "Dump label not found: $Label" }
$dumpUrl = [System.Net.WebUtility]::HtmlDecode($anchor.Groups[1].Value)
$parentPath = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force $parentPath | Out-Null
$partialPath = "$Destination.partial"
Invoke-WebRequest $dumpUrl -OutFile $partialPath -TimeoutSec 1800
Move-Item -LiteralPath $partialPath -Destination $Destination -Force
Write-Output "Downloaded $Label to $Destination"
