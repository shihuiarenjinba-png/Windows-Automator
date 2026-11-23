param(
  [Parameter(Mandatory=$true)][string]$Job,
  [Parameter(Mandatory=$true)][string]$Output,
  [Parameter(Mandatory=$true)][string]$CdpUrl,
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$RunningOnWindows = ($env:OS -eq "Windows_NT") -or ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT)
if (-not $RunningOnWindows) { throw "Windows only" }
$jobPath = (Resolve-Path -LiteralPath $Job).Path
$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = Split-Path -Parent $outPath
if (-not (Test-Path -LiteralPath $outDir)) {
  New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

& $PythonExe -m store_manager.cli verify-existing-identity `
  --job $jobPath `
  --output $outPath `
  --cdp-url $CdpUrl

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$receipt = Get-Content -LiteralPath $outPath -Raw | ConvertFrom-Json
if ($receipt.status -ne "EXISTING_IDENTITY_EXACT_MATCH") {
  throw "Identity reverify did not produce exact-match success."
}
Write-Host ("IDENTITY_REVERIFY_PASS receipt=" + $outPath)
