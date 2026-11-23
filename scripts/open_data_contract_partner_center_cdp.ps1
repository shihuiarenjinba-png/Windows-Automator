#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Url = "https://partner.microsoft.com/en-us/dashboard/products/9PDL4ZWSB45P/identity",
    [int]$Port = 9223
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$EdgeCandidates = @(
    @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
        (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ }
)

if (-not $EdgeCandidates) { throw "Microsoft Edge executable was not found." }
$Edge = [string]$EdgeCandidates[0]
$Profile = Join-Path $env:LOCALAPPDATA "StoreAutomationEdge-DataContractAuditor"

$Args = @(
    ("--remote-debugging-port=" + $Port),
    ("--user-data-dir=" + $Profile),
    "--no-first-run",
    "--no-default-browser-check",
    "--new-window",
    $Url
)

$Process = Start-Process -FilePath $Edge -ArgumentList $Args -PassThru

$Version = $null
$LastError = $null
for ($Attempt = 1; $Attempt -le 20; $Attempt++) {
    try {
        $Version = Invoke-RestMethod -Uri ("http://127.0.0.1:" + $Port + "/json/version") -TimeoutSec 2
        if ($Version.webSocketDebuggerUrl) { break }
    } catch {
        $LastError = $_.Exception.Message
    }

    if ($Process.HasExited) {
        throw ("PARTNER_CENTER_EDGE_EXITED code=" + $Process.ExitCode)
    }
    Start-Sleep -Milliseconds 500
}

if (-not $Version -or -not $Version.webSocketDebuggerUrl) {
    throw ("PARTNER_CENTER_CDP_UNAVAILABLE after retry: " + [string]$LastError)
}

Write-Host "PARTNER_CENTER_CDP=READY"
Write-Host ("CDP_URL=http://127.0.0.1:" + $Port)
Write-Host ("EDGE_PROFILE=" + $Profile)
Write-Host "ACTION=Do NOT sign into Edge itself. On the Partner Center webpage, sign in with the Microsoft account that owns Data Contract Auditor. Leave this Edge window open, then rerun ReadOnly using this CDP URL."
