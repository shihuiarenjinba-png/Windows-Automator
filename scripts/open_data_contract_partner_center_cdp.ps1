#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Url = "https://partner.microsoft.com/en-us/dashboard/products/9PDL4ZWSB45P/identity",
    [int]$Port = 9223
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$EdgeCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
) | Where-Object { Test-Path -LiteralPath $_ }

if (-not $EdgeCandidates) { throw "Microsoft Edge executable was not found." }
$Edge = $EdgeCandidates[0]
$Profile = Join-Path $env:LOCALAPPDATA "StoreAutomationEdge-DataContractAuditor"

& $Edge ("--remote-debugging-port=" + $Port) ("--user-data-dir=" + $Profile) $Url | Out-Null
Start-Sleep -Seconds 1

try {
    $Version = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Port + "/json/version") -TimeoutSec 5
    if (-not $Version.webSocketDebuggerUrl) { throw "CDP endpoint did not expose webSocketDebuggerUrl." }
    Write-Host "PARTNER_CENTER_CDP=READY"
    Write-Host ("CDP_URL=http://127.0.0.1:" + $Port)
    Write-Host ("EDGE_PROFILE=" + $Profile)
    Write-Host "ACTION=Sign in with the Partner Center account that owns Data Contract Auditor, leave this Edge window open, then rerun ReadOnly using this CDP URL."
} catch {
    throw ("PARTNER_CENTER_CDP_UNAVAILABLE: " + $_.Exception.Message)
}
