param(
  [Parameter(Mandatory=$true)][string]$Input,
  [Parameter(Mandatory=$true)][string]$Output,
  [Parameter(Mandatory=$true)][string]$CdpUrl
)

$ErrorActionPreference = "Stop"
if (-not $IsWindows) { throw "Windows only" }
$inputPath = (Resolve-Path -LiteralPath $Input).Path
$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = Split-Path -Parent $outPath
if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

python -m store_manager.cli reconcile-initial-submission-attempt `
  --input $inputPath `
  --output $outPath `
  --cdp-url $CdpUrl

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$receipt = Get-Content -LiteralPath $outPath -Raw | ConvertFrom-Json
if ($receipt.write_performed) { throw "Reconciliation must remain read-only." }
Write-Host ("INITIAL_SUBMISSION_RECONCILE status=" + $receipt.status + " receipt=" + $outPath)
