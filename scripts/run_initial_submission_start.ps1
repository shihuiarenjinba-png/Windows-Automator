param(
  [Parameter(Mandatory=$true)][string]$Input,
  [Parameter(Mandatory=$true)][string]$Job,
  [Parameter(Mandatory=$true)][string]$Output,
  [Parameter(Mandatory=$true)][string]$CdpUrl
)

$ErrorActionPreference = "Stop"
if (-not $IsWindows) { throw "Windows only" }
$inputPath = (Resolve-Path -LiteralPath $Input).Path
$jobPath = (Resolve-Path -LiteralPath $Job).Path
$outPath = [System.IO.Path]::GetFullPath($Output)
$outDir = Split-Path -Parent $outPath
if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

python -m store_manager.cli start-initial-submission `
  --input $inputPath `
  --job $jobPath `
  --output $outPath `
  --cdp-url $CdpUrl `
  --confirm-start-submission

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$receipt = Get-Content -LiteralPath $outPath -Raw | ConvertFrom-Json
if ($receipt.status -ne "INITIAL_SUBMISSION_DRAFT_CREATED") { throw "Initial submission draft was not confirmed." }
if ($receipt.package_uploaded -or $receipt.pricing_changed -or $receipt.submitted -or $receipt.published) { throw "Unexpected write beyond Draft creation." }
Write-Host ("INITIAL_SUBMISSION_DRAFT_PASS draft_id=" + $receipt.draft_id + " receipt=" + $outPath)
